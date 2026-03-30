from __future__ import annotations

from dataclasses import dataclass

from app.services.benchmark_ranking import BenchmarkRanking


@dataclass(frozen=True, slots=True)
class SsdRankingEntry:
    identifier: str
    name: str
    ssd_tester_score: float | None


class SsdRankingService:
    def build_rankings(self, entries: list[SsdRankingEntry]) -> dict[str, BenchmarkRanking]:
        valid_entries = [entry for entry in entries if entry.ssd_tester_score is not None]
        if not valid_entries:
            return {}

        top_score = max(entry.ssd_tester_score or 0.0 for entry in valid_entries)
        if top_score <= 0:
            return {}

        rankings: dict[str, BenchmarkRanking] = {}

        for entry in valid_entries:
            score = float(entry.ssd_tester_score or 0.0)
            relative_performance = round((score / top_score) * 100, 2)
            rankings[entry.identifier] = BenchmarkRanking(
                game_score=score,
                game_percentile=relative_performance,
                performance_tier=ssd_tier_for_relative_performance(relative_performance),
            )

        return rankings


def ssd_tier_for_relative_performance(score: float) -> str:
    if score >= 90:
        return "S"
    if score >= 80:
        return "A"
    if score >= 65:
        return "B"
    if score >= 50:
        return "C"
    return "D"
