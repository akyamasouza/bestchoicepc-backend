from typing import Any

from app.scripts.seed_ssds import seed_ssds
from app.services.ssd_ranking import SsdRankingEntry, SsdRankingService


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


def test_seed_ssds_upserts_by_sku(monkeypatch) -> None:
    collection = FakeCollection()

    monkeypatch.setattr("app.scripts.seed_ssds.get_ssd_collection", lambda: collection)
    monkeypatch.setattr(
        "app.scripts.seed_ssds.SSDS",
        [
            {
                "name": "Samsung 9100 PRO 1TB",
                "sku": "MZ-VAP1T0BW",
                "brand": "Samsung",
                "capacity_gb": 1024,
                "interface": "PCIe 5.0 x4",
                "nand": "TLC",
                "dram": True,
                "benchmark": {
                    "ssd_tester_score": 12554,
                },
            }
        ],
    )

    changed = seed_ssds()

    expected_ranking = SsdRankingService().build_rankings(
        [
            SsdRankingEntry(
                identifier="MZ-VAP1T0BW",
                name="Samsung 9100 PRO 1TB",
                ssd_tester_score=12554,
            )
        ]
    )["MZ-VAP1T0BW"]

    assert changed == 1
    assert collection.indexes == [([("sku", 1)], True)]
    assert collection.operations[0][0] == {"sku": "MZ-VAP1T0BW"}
    assert collection.operations[0][1] == {
        "$set": {
            "name": "Samsung 9100 PRO 1TB",
            "sku": "MZ-VAP1T0BW",
            "brand": "Samsung",
            "capacity_gb": 1024,
            "interface": "PCIe 5.0 x4",
            "nand": "TLC",
            "dram": True,
            "benchmark": {
                "ssd_tester_score": 12554,
            },
            "ranking": {
                "game_score": expected_ranking.game_score,
                "game_percentile": expected_ranking.game_percentile,
                "performance_tier": expected_ranking.performance_tier,
            },
        }
    }
    assert collection.operations[0][2] is True
