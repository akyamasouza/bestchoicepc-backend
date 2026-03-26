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


def test_build_rankings_supports_custom_tier_resolver() -> None:
    service = BenchmarkRankingService()

    rankings = service.build_rankings(
        [
            ("cpu-1", 64.9),
            ("cpu-2", 95.6),
            ("cpu-3", 121.0),
        ],
        tier_resolver=lambda score, _percentile: "S" if score >= 110 else "A" if score >= 95 else "D",
    )

    assert rankings["cpu-1"].performance_tier == "D"
    assert rankings["cpu-2"].performance_tier == "A"
    assert rankings["cpu-3"].performance_tier == "S"
