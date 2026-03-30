from app.services.ssd_ranking import SsdRankingEntry, SsdRankingService, ssd_tier_for_relative_performance


def test_ssd_ranking_normalizes_against_top_score() -> None:
    rankings = SsdRankingService().build_rankings(
        [
            SsdRankingEntry(
                identifier="ssd-1",
                name="SSD One",
                ssd_tester_score=10000,
            ),
            SsdRankingEntry(
                identifier="ssd-2",
                name="SSD Two",
                ssd_tester_score=8000,
            ),
        ]
    )

    assert rankings["ssd-1"].game_score == 10000.0
    assert rankings["ssd-1"].game_percentile == 100.0
    assert rankings["ssd-1"].performance_tier == "S"
    assert rankings["ssd-2"].game_percentile == 80.0
    assert rankings["ssd-2"].performance_tier == "A"


def test_ssd_tier_is_based_on_relative_performance_score() -> None:
    assert ssd_tier_for_relative_performance(90.0) == "S"
    assert ssd_tier_for_relative_performance(80.0) == "A"
    assert ssd_tier_for_relative_performance(65.0) == "B"
    assert ssd_tier_for_relative_performance(50.0) == "C"
    assert ssd_tier_for_relative_performance(49.99) == "D"
