from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class BenchmarkRanking:
    game_score: float
    game_percentile: float
    performance_tier: str


class BenchmarkRankingService:
    def build_rankings(
        self,
        entries: list[tuple[str, float]],
        *,
        tier_resolver: Callable[[float, float], str] | None = None,
    ) -> dict[str, BenchmarkRanking]:
        if not entries:
            return {}

        sorted_entries = sorted(entries, key=lambda entry: entry[1])
        last_index = len(sorted_entries) - 1
        rankings: dict[str, BenchmarkRanking] = {}
        resolver = tier_resolver or self._tier_for_percentile_score

        for index, (identifier, score) in enumerate(sorted_entries):
            percentile = 100.0 if last_index == 0 else round((index / last_index) * 100, 2)
            rankings[identifier] = BenchmarkRanking(
                game_score=score,
                game_percentile=percentile,
                performance_tier=resolver(score, percentile),
            )

        return rankings

    @staticmethod
    def _tier_for_percentile_score(_score: float, percentile: float) -> str:
        if percentile >= 90:
            return "S"
        if percentile >= 75:
            return "A"
        if percentile >= 55:
            return "B"
        if percentile >= 35:
            return "C"
        return "D"
