from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from math import inf
from typing import Protocol

from app.services.benchmark_ranking import BenchmarkRanking


@dataclass(frozen=True, slots=True)
class CpuRankingEntry:
    identifier: str
    name: str
    benchmark_score: float | None
    techpowerup_score: float | None


@dataclass(frozen=True, slots=True)
class CpuRankingContext:
    anchors: tuple[CpuRankingEntry, ...]


@dataclass(frozen=True, slots=True)
class RyzenCpuInfo:
    tier: int
    generation: int
    family_model: int
    variant: str


@dataclass(frozen=True, slots=True)
class RyzenX3DGuardrailConfig:
    comparable_benchmark_delta: float = 0.12
    superiority_margin: float = 0.01


class CpuRankingStrategy(Protocol):
    def build(
        self,
        *,
        entry: CpuRankingEntry,
        context: CpuRankingContext,
    ) -> BenchmarkRanking | None: ...


class DirectTechPowerUpCpuRankingStrategy:
    def build(
        self,
        *,
        entry: CpuRankingEntry,
        context: CpuRankingContext,
    ) -> BenchmarkRanking | None:
        del context

        if entry.techpowerup_score is None:
            return None

        relative_performance = _apply_gaming_profile(
            entry=entry,
            base_relative_performance=entry.techpowerup_score,
        )
        score = entry.benchmark_score if entry.benchmark_score is not None else relative_performance
        return BenchmarkRanking(
            game_score=score,
            game_percentile=relative_performance,
            performance_tier=cpu_tier_for_relative_performance(relative_performance),
        )


class BenchmarkAnchoredCpuRankingStrategy:
    def build(
        self,
        *,
        entry: CpuRankingEntry,
        context: CpuRankingContext,
    ) -> BenchmarkRanking | None:
        if entry.techpowerup_score is not None:
            return None
        if entry.benchmark_score is None:
            return None
        if not context.anchors:
            return None

        anchor = min(
            context.anchors,
            key=lambda candidate: _anchor_sort_key(
                candidate=candidate,
                entry=entry,
            ),
        )

        if anchor.benchmark_score is None or anchor.techpowerup_score is None:
            return None

        estimated_relative_performance = _apply_gaming_profile(
            entry=entry,
            base_relative_performance=anchor.techpowerup_score * (entry.benchmark_score / anchor.benchmark_score),
        )
        return BenchmarkRanking(
            game_score=entry.benchmark_score,
            game_percentile=estimated_relative_performance,
            performance_tier=cpu_tier_for_relative_performance(estimated_relative_performance),
        )


class CpuRankingService:
    def __init__(self, strategies: list[CpuRankingStrategy] | None = None):
        self.strategies = strategies or [
            DirectTechPowerUpCpuRankingStrategy(),
            BenchmarkAnchoredCpuRankingStrategy(),
        ]

    def build_rankings(self, entries: list[CpuRankingEntry]) -> dict[str, BenchmarkRanking]:
        context = CpuRankingContext(
            anchors=tuple(
                entry
                for entry in entries
                if entry.benchmark_score is not None and entry.techpowerup_score is not None
            )
        )
        rankings: dict[str, BenchmarkRanking] = {}

        for entry in entries:
            for strategy in self.strategies:
                ranking = strategy.build(entry=entry, context=context)
                if ranking is None:
                    continue

                rankings[entry.identifier] = ranking
                break

        rankings = _apply_ryzen_family_constraints(entries=entries, rankings=rankings)
        return _apply_ryzen_x3d_generation_guardrails(entries=entries, rankings=rankings)


def cpu_tier_for_relative_performance(score: float) -> str:
    if score >= 110:
        return "S"
    if score >= 95:
        return "A"
    if score >= 80:
        return "B"
    if score >= 65:
        return "C"
    return "D"


def _benchmark_distance(anchor_score: float | None, benchmark_score: float) -> float:
    if anchor_score is None or anchor_score == 0:
        return inf

    return abs((benchmark_score - anchor_score) / anchor_score)


def _apply_gaming_profile(*, entry: CpuRankingEntry, base_relative_performance: float) -> float:
    adjusted = float(base_relative_performance)
    ryzen_info = _parse_ryzen_cpu_info(entry.name)
    if ryzen_info is None:
        return round(adjusted, 2)

    adjusted *= 1 + _ryzen_generation_bonus(ryzen_info.generation)
    adjusted *= 1 + _ryzen_variant_bonus(ryzen_info)
    return round(adjusted, 2)


def _parse_ryzen_cpu_info(name: str) -> RyzenCpuInfo | None:
    normalized = name.lower()
    match = re.search(r"amd ryzen (?P<tier>[3579]) (?P<model>\d{4,5})(?P<suffix>[a-z0-9]*)", normalized)
    if match is None:
        return None

    tier = int(match.group("tier"))
    family_model = int(match.group("model"))
    generation = int(str(family_model)[0]) * 1000
    suffix = match.group("suffix").lower()

    if "x3d" in suffix:
        variant = "x3d"
    elif suffix.endswith("x"):
        variant = "x"
    elif suffix.endswith("g"):
        variant = "g"
    else:
        variant = "plain"

    return RyzenCpuInfo(
        tier=tier,
        generation=generation,
        family_model=family_model,
        variant=variant,
    )


def _ryzen_generation_bonus(generation: int) -> float:
    return 0.0


def _ryzen_variant_bonus(info: RyzenCpuInfo) -> float:
    if info.variant == "x3d":
        return 0.07

    if info.variant == "x":
        return 0.01
    if info.variant == "g":
        return -0.02
    return 0.0


def _anchor_sort_key(*, candidate: CpuRankingEntry, entry: CpuRankingEntry) -> tuple[int, float]:
    candidate_info = _parse_ryzen_cpu_info(candidate.name)
    entry_info = _parse_ryzen_cpu_info(entry.name)

    architecture_penalty = 4
    if candidate_info is not None and entry_info is not None:
        if (
            candidate_info.variant == entry_info.variant
            and candidate_info.tier == entry_info.tier
            and candidate_info.generation == entry_info.generation
        ):
            architecture_penalty = 0
        elif candidate_info.variant == entry_info.variant and candidate_info.generation == entry_info.generation:
            architecture_penalty = 1
        elif candidate_info.tier == entry_info.tier and candidate_info.generation == entry_info.generation:
            architecture_penalty = 2
        elif candidate_info.generation == entry_info.generation:
            architecture_penalty = 3

    return (
        architecture_penalty,
        _benchmark_distance(candidate.benchmark_score, entry.benchmark_score or 0),
    )


def _apply_ryzen_family_constraints(
    *,
    entries: list[CpuRankingEntry],
    rankings: dict[str, BenchmarkRanking],
) -> dict[str, BenchmarkRanking]:
    family_groups: dict[tuple[int, int], dict[str, tuple[str, BenchmarkRanking]]] = defaultdict(dict)

    for entry in entries:
        ranking = rankings.get(entry.identifier)
        if ranking is None:
            continue

        info = _parse_ryzen_cpu_info(entry.name)
        if info is None:
            continue

        family_groups[(info.tier, info.family_model)][info.variant] = (entry.identifier, ranking)

    adjusted_rankings = dict(rankings)
    rules = (
        ("g", "plain", 1.01),
        ("plain", "x", 1.02),
        ("x", "x3d", 1.06),
        ("plain", "x3d", 1.08),
        ("g", "x3d", 1.10),
    )

    for family in family_groups.values():
        for lower_variant, higher_variant, multiplier in rules:
            lower = family.get(lower_variant)
            higher = family.get(higher_variant)
            if lower is None or higher is None:
                continue

            lower_identifier, lower_ranking = lower
            higher_identifier, higher_ranking = higher
            minimum_score = round(lower_ranking.game_percentile * multiplier, 2)
            if higher_ranking.game_percentile >= minimum_score:
                continue

            family[higher_variant] = (
                higher_identifier,
                BenchmarkRanking(
                    game_score=higher_ranking.game_score,
                    game_percentile=minimum_score,
                    performance_tier=cpu_tier_for_relative_performance(minimum_score),
                ),
            )
            adjusted_rankings[higher_identifier] = family[higher_variant][1]
            adjusted_rankings[lower_identifier] = lower_ranking

    return adjusted_rankings


def _apply_ryzen_x3d_generation_guardrails(
    *,
    entries: list[CpuRankingEntry],
    rankings: dict[str, BenchmarkRanking],
    config: RyzenX3DGuardrailConfig = RyzenX3DGuardrailConfig(),
) -> dict[str, BenchmarkRanking]:
    adjusted_rankings = dict(rankings)
    parsed_entries: dict[str, RyzenCpuInfo] = {}

    for entry in entries:
        info = _parse_ryzen_cpu_info(entry.name)
        if info is not None:
            parsed_entries[entry.identifier] = info

    for entry in entries:
        ranking = adjusted_rankings.get(entry.identifier)
        if ranking is None or entry.benchmark_score is None:
            continue

        info = parsed_entries.get(entry.identifier)
        if info is None or info.variant != "x3d":
            continue

        comparable_scores: list[float] = []
        maximum_comparable_benchmark = entry.benchmark_score * (1 + config.comparable_benchmark_delta)

        for candidate in entries:
            if candidate.identifier == entry.identifier or candidate.benchmark_score is None:
                continue

            candidate_info = parsed_entries.get(candidate.identifier)
            candidate_ranking = adjusted_rankings.get(candidate.identifier)
            if (
                candidate_info is None
                or candidate_ranking is None
                or candidate_info.generation != info.generation
                or candidate_info.variant == "x3d"
                or candidate.benchmark_score < entry.benchmark_score
                or candidate.benchmark_score > maximum_comparable_benchmark
            ):
                continue

            comparable_scores.append(candidate_ranking.game_percentile)

        if not comparable_scores:
            continue

        minimum_score = round(max(comparable_scores) * (1 + config.superiority_margin), 2)
        if ranking.game_percentile >= minimum_score:
            continue

        adjusted_rankings[entry.identifier] = BenchmarkRanking(
            game_score=ranking.game_score,
            game_percentile=minimum_score,
            performance_tier=cpu_tier_for_relative_performance(minimum_score),
        )

    return adjusted_rankings
