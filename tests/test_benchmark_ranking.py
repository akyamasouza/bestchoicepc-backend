from __future__ import annotations

from app.services.benchmark_ranking import BenchmarkRankingService


def test_build_rankings_assigns_percentiles_and_tiers() -> None:
    service = BenchmarkRankingService()

    rankings = service.build_rankings(
        [
            ("gpu-3060", 16993),
            ("gpu-4070", 26921),
            ("gpu-5090", 38975),
        ]
    )

    assert rankings["gpu-3060"].game_percentile == 0.0
    assert rankings["gpu-3060"].performance_tier == "D"
    assert rankings["gpu-4070"].game_percentile == 50.0
    assert rankings["gpu-4070"].performance_tier == "C"
    assert rankings["gpu-5090"].game_percentile == 100.0
    assert rankings["gpu-5090"].performance_tier == "S"


def test_build_rankings_handles_single_entry() -> None:
    service = BenchmarkRankingService()

    rankings = service.build_rankings([("gpu-5090", 38975)])

    assert rankings["gpu-5090"].game_percentile == 100.0
    assert rankings["gpu-5090"].performance_tier == "S"
