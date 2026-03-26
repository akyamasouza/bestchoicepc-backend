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

        return _apply_ryzen_family_constraints(entries=entries, rankings=rankings)


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
    if generation >= 9000:
        return 0.04
    if generation >= 7000:
        return 0.02
    return 0.0


def _ryzen_variant_bonus(info: RyzenCpuInfo) -> float:
    if info.variant == "x3d":
        return {
            5: 0.18,
            7: 0.15,
            9: 0.10,
        }.get(info.tier, 0.12)

    if info.variant == "x":
        return 0.03
    if info.variant == "g":
        return -0.05
    return 0.0


def _anchor_sort_key(*, candidate: CpuRankingEntry, entry: CpuRankingEntry) -> tuple[int, float]:
    candidate_info = _parse_ryzen_cpu_info(candidate.name)
    entry_info = _parse_ryzen_cpu_info(entry.name)

    architecture_penalty = 3
    if candidate_info is not None and entry_info is not None:
        if candidate_info.tier == entry_info.tier and candidate_info.generation == entry_info.generation:
            architecture_penalty = 0
        elif candidate_info.tier == entry_info.tier:
            architecture_penalty = 1
        else:
            architecture_penalty = 2

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
