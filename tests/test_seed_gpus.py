from typing import Any

from app.data.gpus import GPUS
from app.scripts.seed_gpus import seed_gpus


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


def test_seed_gpus_upserts_by_sku(monkeypatch) -> None:
    collection = FakeCollection()

    monkeypatch.setattr("app.scripts.seed_gpus.get_gpu_collection", lambda: collection)

    changed = seed_gpus()

    assert changed == len(GPUS)
    assert collection.indexes == [([("sku", 1)], True)]
    assert len(collection.operations) == len(GPUS)
    assert collection.operations[0][0] == {"sku": GPUS[0]["sku"]}
    assert collection.operations[0][1] == {"$set": GPUS[0]}
    assert collection.operations[0][2] is True
