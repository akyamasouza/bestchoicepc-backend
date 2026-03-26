from app.services.gpu_ranking import GpuRankingEntry, GpuRankingService, gpu_tier_for_relative_performance


def test_gpu_ranking_uses_direct_tomshardware_score_when_available() -> None:
    rankings = GpuRankingService().build_rankings(
        [
            GpuRankingEntry(
                identifier="gpu-1",
                name="GeForce RTX 5090",
                benchmark_score=38975,
                tomshardware_score=100.0,
            )
        ]
    )

    assert rankings["gpu-1"].game_score == 38975
    assert rankings["gpu-1"].game_percentile == 100.0
    assert rankings["gpu-1"].performance_tier == "S"


def test_gpu_ranking_estimates_missing_tomshardware_score_from_nearest_anchor() -> None:
    rankings = GpuRankingService().build_rankings(
        [
            GpuRankingEntry(
                identifier="rtx-5090",
                name="GeForce RTX 5090",
                benchmark_score=38975,
                tomshardware_score=100.0,
            ),
            GpuRankingEntry(
                identifier="rtx-4090",
                name="GeForce RTX 4090",
                benchmark_score=38071,
                tomshardware_score=None,
            ),
        ]
    )

    assert rankings["rtx-4090"].game_score == 38071
    assert rankings["rtx-4090"].game_percentile == 97.68
    assert rankings["rtx-4090"].performance_tier == "S"


def test_gpu_tier_is_based_on_relative_performance_score() -> None:
    assert gpu_tier_for_relative_performance(90.0) == "S"
    assert gpu_tier_for_relative_performance(80.0) == "A"
    assert gpu_tier_for_relative_performance(65.0) == "B"
    assert gpu_tier_for_relative_performance(45.0) == "C"
    assert gpu_tier_for_relative_performance(44.99) == "D"
