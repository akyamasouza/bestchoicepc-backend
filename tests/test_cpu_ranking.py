from app.services.cpu_ranking import CpuRankingEntry, CpuRankingService, cpu_tier_for_relative_performance


def test_cpu_ranking_uses_direct_techpowerup_score_when_available() -> None:
    rankings = CpuRankingService().build_rankings(
        [
            CpuRankingEntry(
                identifier="cpu-1",
                name="Intel Core i5-13400F",
                benchmark_score=3714,
                techpowerup_score=67.6,
            )
        ]
    )

    assert rankings["cpu-1"].game_score == 3714
    assert rankings["cpu-1"].game_percentile == 67.6
    assert rankings["cpu-1"].performance_tier == "C"


def test_cpu_ranking_estimates_missing_techpowerup_score_from_nearest_anchor() -> None:
    rankings = CpuRankingService().build_rankings(
        [
            CpuRankingEntry(
                identifier="i5-13400f",
                name="Intel Core i5-13400F",
                benchmark_score=3714,
                techpowerup_score=67.6,
            ),
            CpuRankingEntry(
                identifier="i5-12400f",
                name="Intel Core i5-12400F",
                benchmark_score=3489,
                techpowerup_score=None,
            ),
        ]
    )

    assert rankings["i5-12400f"].game_score == 3489
    assert rankings["i5-12400f"].game_percentile == 63.5
    assert rankings["i5-12400f"].performance_tier == "D"


def test_cpu_ranking_enforces_ryzen_x3d_hierarchy_inside_same_family() -> None:
    rankings = CpuRankingService().build_rankings(
        [
            CpuRankingEntry(
                identifier="5700x3d",
                name="AMD Ryzen 7 5700X3D",
                benchmark_score=2968,
                techpowerup_score=None,
            ),
            CpuRankingEntry(
                identifier="5700x",
                name="AMD Ryzen 7 5700X",
                benchmark_score=3387,
                techpowerup_score=64.9,
            ),
            CpuRankingEntry(
                identifier="5700",
                name="AMD Ryzen 7 5700",
                benchmark_score=3294,
                techpowerup_score=None,
            ),
            CpuRankingEntry(
                identifier="5700g",
                name="AMD Ryzen 7 5700G",
                benchmark_score=3284,
                techpowerup_score=62.5,
            ),
        ]
    )

    assert rankings["5700x3d"].game_percentile > rankings["5700x"].game_percentile
    assert rankings["5700x"].game_percentile > rankings["5700"].game_percentile
    assert rankings["5700"].game_percentile > rankings["5700g"].game_percentile
    assert rankings["5700x3d"].performance_tier == "C"


def test_cpu_ranking_allows_ryzen_5_x3d_to_surpass_non_x3d_sibling_class() -> None:
    rankings = CpuRankingService().build_rankings(
        [
            CpuRankingEntry(
                identifier="5500x3d",
                name="AMD Ryzen 5 5500X3D",
                benchmark_score=2952,
                techpowerup_score=None,
            ),
            CpuRankingEntry(
                identifier="5600",
                name="AMD Ryzen 5 5600",
                benchmark_score=3256,
                techpowerup_score=58.1,
            ),
        ]
    )

    assert rankings["5500x3d"].game_percentile > rankings["5600"].game_percentile
    assert rankings["5500x3d"].performance_tier == "D"
    assert rankings["5600"].game_percentile == 58.1


def test_cpu_ranking_applies_ryzen_generation_and_variant_bonuses() -> None:
    rankings = CpuRankingService().build_rankings(
        [
            CpuRankingEntry(
                identifier="7700x",
                name="AMD Ryzen 7 7700X",
                benchmark_score=4000,
                techpowerup_score=90.7,
            ),
            CpuRankingEntry(
                identifier="5700x",
                name="AMD Ryzen 7 5700X",
                benchmark_score=3387,
                techpowerup_score=64.9,
            ),
        ]
    )

    assert rankings["7700x"].game_percentile == 91.61
    assert rankings["7700x"].performance_tier == "B"
    assert rankings["5700x"].game_percentile == 65.55
    assert rankings["5700x"].performance_tier == "C"


def test_cpu_ranking_keeps_ryzen_x3d_above_nearby_non_x3d_models_without_overinflating_scores() -> None:
    rankings = CpuRankingService().build_rankings(
        [
            CpuRankingEntry(
                identifier="5500x3d",
                name="AMD Ryzen 5 5500X3D",
                benchmark_score=2952,
                techpowerup_score=None,
            ),
            CpuRankingEntry(
                identifier="5700",
                name="AMD Ryzen 7 5700",
                benchmark_score=3294,
                techpowerup_score=None,
            ),
            CpuRankingEntry(
                identifier="5700x",
                name="AMD Ryzen 7 5700X",
                benchmark_score=3387,
                techpowerup_score=64.9,
            ),
        ]
    )

    assert rankings["5500x3d"].game_percentile > rankings["5700"].game_percentile
    assert rankings["5500x3d"].game_percentile < rankings["5700x"].game_percentile
    assert rankings["5500x3d"].performance_tier == "D"
    assert rankings["5700x"].performance_tier == "C"


def test_cpu_tier_is_based_on_relative_performance_score() -> None:
    assert cpu_tier_for_relative_performance(110.0) == "S"
    assert cpu_tier_for_relative_performance(95.0) == "A"
    assert cpu_tier_for_relative_performance(80.0) == "B"
    assert cpu_tier_for_relative_performance(65.0) == "C"
    assert cpu_tier_for_relative_performance(64.99) == "D"
