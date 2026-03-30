from typing import Any

from app.scripts.seed_rams import seed_rams


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

    def update_one(self, query: dict[str, Any], update: dict[str, Any], upsert: bool = False) -> FakeResult:
        self.operations.append((query, update, upsert))
        return FakeResult(upserted_id=query["sku"])


def test_seed_rams_upserts_by_sku(monkeypatch) -> None:
    collection = FakeCollection()

    monkeypatch.setattr("app.scripts.seed_rams.get_ram_collection", lambda: collection)
    monkeypatch.setattr(
        "app.scripts.seed_rams.RAMS",
        [
            {
                "name": "Memória RAM Kingston Fury Beast, 8GB, 3200MHz, DDR4, CL16, Preto - KF432C16BB/8",
                "sku": "KF432C16BB/8",
                "brand": "Kingston",
                "generation": "DDR4",
                "form_factor": "UDIMM",
                "capacity_gb": 8,
                "module_count": 1,
                "capacity_per_module_gb": 8,
                "speed_mhz": 3200,
                "cl": 16,
                "rgb": False,
                "profile": "unknown",
                "device": "desktop",
                "compatibility": {
                    "desktop": True,
                    "notebook": False,
                    "platforms": ["DDR4"],
                },
            }
        ],
    )

    changed = seed_rams()

    assert changed == 1
    assert collection.indexes == [([("sku", 1)], True)]
    assert collection.operations[0][0] == {"sku": "KF432C16BB/8"}
    assert collection.operations[0][1]["$set"]["generation"] == "DDR4"
    assert collection.operations[0][2] is True
