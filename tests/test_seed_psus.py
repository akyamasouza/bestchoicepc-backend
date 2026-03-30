from typing import Any

from app.scripts.seed_psus import seed_psus
from app.services.psu_ranking import PsuRankingEntry, PsuRankingService


class FakeResult:
    def __init__(self, *, upserted_id: str | None = None, modified_count: int = 0):
        self.upserted_id = upserted_id
        self.modified_count = modified_count


class FakeCollection:
    def __init__(self):
        self.indexes: list[tuple[list[tuple[str, int]], bool]] = []
        self.operations: list[tuple[dict[str, Any], dict[str, Any], bool]] = []

    def create_index(self, keys: list[tuple[str, int]], unique: bool = False) -> None:
        self.indexes.append((keys, unique))

    def update_one(
        self,
        query: dict[str, Any],
        update: dict[str, Any],
        upsert: bool = False,
    ) -> FakeResult:
        self.operations.append((query, update, upsert))
        return FakeResult(upserted_id=query["sku"])


def test_seed_psus_upserts_by_sku(monkeypatch) -> None:
    collection = FakeCollection()

    monkeypatch.setattr("app.scripts.seed_psus.get_psu_collection", lambda: collection)
    monkeypatch.setattr(
        "app.scripts.seed_psus.PSUS",
        [
            {
                "name": "1st Player NGDP 1000W",
                "sku": "1st-player-ngdp-1000w",
                "brand": "1st Player",
                "wattage_w": 1000,
                "form_factor": "ATX",
                "atx_version": "ATX3.0",
                "efficiency_rating": "PLATINUM",
                "noise_rating": "Standard++",
                "benchmark": {
                    "cybenetics_score": 87.0974,
                },
            }
        ],
    )

    changed = seed_psus()

    expected_ranking = PsuRankingService().build_rankings(
        [
            PsuRankingEntry(
                identifier="1st-player-ngdp-1000w",
                name="1st Player NGDP 1000W",
                cybenetics_score=87.0974,
            )
        ]
    )["1st-player-ngdp-1000w"]

    assert changed == 1
    assert collection.indexes == [([("sku", 1)], True)]
    assert collection.operations[0][0] == {"sku": "1st-player-ngdp-1000w"}
    assert collection.operations[0][1] == {
        "$set": {
            "name": "1st Player NGDP 1000W",
            "sku": "1st-player-ngdp-1000w",
            "brand": "1st Player",
            "wattage_w": 1000,
            "form_factor": "ATX",
            "atx_version": "ATX3.0",
            "efficiency_rating": "PLATINUM",
            "noise_rating": "Standard++",
            "benchmark": {
                "cybenetics_score": 87.0974,
            },
            "ranking": {
                "game_score": expected_ranking.game_score,
                "game_percentile": expected_ranking.game_percentile,
                "performance_tier": expected_ranking.performance_tier,
            },
        }
    }
    assert collection.operations[0][2] is True
