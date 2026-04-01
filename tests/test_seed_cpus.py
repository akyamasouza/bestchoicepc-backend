from typing import Any

from app.data.cpus import CPUS
from app.data.cpu_techpowerup import resolve_techpowerup_cpu_application_score
from app.scripts.seed_cpus import seed_cpus
from app.services.cpu_ranking import CpuRankingEntry, CpuRankingService


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


def test_seed_cpus_upserts_by_sku(monkeypatch) -> None:
    collection = FakeCollection()

    monkeypatch.setattr("app.scripts.seed_cpus.get_cpu_collection", lambda: collection)

    changed = seed_cpus()

    assert changed == len(CPUS)
    assert collection.indexes == [([("sku", 1)], True)]
    assert len(collection.operations) == len(CPUS)
    assert collection.operations[0][0] == {"sku": CPUS[0]["sku"]}
    first_document = collection.operations[0][1]["$set"]
    expected_score = resolve_techpowerup_cpu_application_score(CPUS[0]["name"], CPUS[0]["other_names"])
    expected_rankings = CpuRankingService().build_rankings(
        [
            CpuRankingEntry(
                identifier=cpu["sku"],
                name=cpu["name"],
                benchmark_score=float(cpu["benchmark"]["single_thread_rating"]),
                techpowerup_score=float(score) if score is not None else None,
            )
            for cpu in CPUS
            for score in [resolve_techpowerup_cpu_application_score(cpu["name"], cpu["other_names"])]
        ]
    )
    assert first_document["sku"] == CPUS[0]["sku"]
    assert first_document["benchmark"].get("techpowerup_relative_performance_applications") == expected_score
    assert first_document["ranking"] == {
        "game_score": expected_rankings[CPUS[0]["sku"]].game_score,
        "game_percentile": expected_rankings[CPUS[0]["sku"]].game_percentile,
        "performance_tier": expected_rankings[CPUS[0]["sku"]].performance_tier,
    }
    assert collection.operations[0][2] is True
