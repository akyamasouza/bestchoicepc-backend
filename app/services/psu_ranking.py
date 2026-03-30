from __future__ import annotations

from dataclasses import dataclass

from app.services.benchmark_ranking import BenchmarkRanking


@dataclass(frozen=True, slots=True)
class PsuRankingEntry:
    identifier: str
    name: str
    cybenetics_score: float | None


class PsuRankingService:
    def build_rankings(self, entries: list[PsuRankingEntry]) -> dict[str, BenchmarkRanking]:
        valid_entries = [entry for entry in entries if entry.cybenetics_score is not None]
        if not valid_entries:
            return {}

        top_score = max(entry.cybenetics_score or 0.0 for entry in valid_entries)
        if top_score <= 0:
            return {}

        rankings: dict[str, BenchmarkRanking] = {}

        for entry in valid_entries:
            score = float(entry.cybenetics_score or 0.0)
            relative_performance = round((score / top_score) * 100, 2)
            rankings[entry.identifier] = BenchmarkRanking(
                game_score=score,
                game_percentile=relative_performance,
                performance_tier=psu_tier_for_relative_performance(relative_performance),
            )

        return rankings


def psu_tier_for_relative_performance(score: float) -> str:
    if score >= 90:
        return "S"
    if score >= 80:
        return "A"
    if score >= 65:
        return "B"
    if score >= 50:
        return "C"
    return "D"
