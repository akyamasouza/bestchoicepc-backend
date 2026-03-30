from app.services.psu_ranking import PsuRankingEntry, PsuRankingService, psu_tier_for_relative_performance


def test_psu_ranking_normalizes_against_top_score() -> None:
    rankings = PsuRankingService().build_rankings(
        [
            PsuRankingEntry(
                identifier="psu-1",
                name="PSU One",
                cybenetics_score=100.0,
            ),
            PsuRankingEntry(
                identifier="psu-2",
                name="PSU Two",
                cybenetics_score=80.0,
            ),
        ]
    )

    assert rankings["psu-1"].game_score == 100.0
    assert rankings["psu-1"].game_percentile == 100.0
    assert rankings["psu-1"].performance_tier == "S"
    assert rankings["psu-2"].game_percentile == 80.0
    assert rankings["psu-2"].performance_tier == "A"


def test_psu_tier_is_based_on_relative_performance_score() -> None:
    assert psu_tier_for_relative_performance(90.0) == "S"
    assert psu_tier_for_relative_performance(80.0) == "A"
    assert psu_tier_for_relative_performance(65.0) == "B"
    assert psu_tier_for_relative_performance(50.0) == "C"
    assert psu_tier_for_relative_performance(49.99) == "D"
