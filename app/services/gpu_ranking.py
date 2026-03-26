from __future__ import annotations

from dataclasses import dataclass
from math import inf
from typing import Protocol

from app.services.benchmark_ranking import BenchmarkRanking


@dataclass(frozen=True, slots=True)
class GpuRankingEntry:
    identifier: str
    name: str
    benchmark_score: float | None
    tomshardware_score: float | None


@dataclass(frozen=True, slots=True)
class GpuRankingContext:
    anchors: tuple[GpuRankingEntry, ...]


class GpuRankingStrategy(Protocol):
    def build(
        self,
        *,
        entry: GpuRankingEntry,
        context: GpuRankingContext,
    ) -> BenchmarkRanking | None: ...


class DirectTomsHardwareGpuRankingStrategy:
    def build(
        self,
        *,
        entry: GpuRankingEntry,
        context: GpuRankingContext,
    ) -> BenchmarkRanking | None:
        del context

        if entry.tomshardware_score is None:
            return None

        score = entry.benchmark_score if entry.benchmark_score is not None else entry.tomshardware_score
        return BenchmarkRanking(
            game_score=score,
            game_percentile=entry.tomshardware_score,
            performance_tier=gpu_tier_for_relative_performance(entry.tomshardware_score),
        )


class BenchmarkAnchoredGpuRankingStrategy:
    def build(
        self,
        *,
        entry: GpuRankingEntry,
        context: GpuRankingContext,
    ) -> BenchmarkRanking | None:
        if entry.tomshardware_score is not None:
            return None
        if entry.benchmark_score is None:
            return None
        if not context.anchors:
            return None

        anchor = min(
            context.anchors,
            key=lambda candidate: _benchmark_distance(candidate.benchmark_score, entry.benchmark_score),
        )

        if anchor.benchmark_score is None or anchor.tomshardware_score is None:
            return None

        estimated_relative_performance = round(
            anchor.tomshardware_score * (entry.benchmark_score / anchor.benchmark_score),
            2,
        )
        return BenchmarkRanking(
            game_score=entry.benchmark_score,
            game_percentile=estimated_relative_performance,
            performance_tier=gpu_tier_for_relative_performance(estimated_relative_performance),
        )


class GpuRankingService:
    def __init__(self, strategies: list[GpuRankingStrategy] | None = None):
        self.strategies = strategies or [
            DirectTomsHardwareGpuRankingStrategy(),
            BenchmarkAnchoredGpuRankingStrategy(),
        ]

    def build_rankings(self, entries: list[GpuRankingEntry]) -> dict[str, BenchmarkRanking]:
        context = GpuRankingContext(
            anchors=tuple(
                entry
                for entry in entries
                if entry.benchmark_score is not None and entry.tomshardware_score is not None
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

        return rankings


def gpu_tier_for_relative_performance(score: float) -> str:
    if score >= 90:
        return "S"
    if score >= 80:
        return "A"
    if score >= 65:
        return "B"
    if score >= 45:
        return "C"
    return "D"


def _benchmark_distance(anchor_score: float | None, benchmark_score: float) -> float:
    if anchor_score is None or anchor_score == 0:
        return inf

    return abs((benchmark_score - anchor_score) / anchor_score)
