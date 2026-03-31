from typing import Any

from app.scripts.seed_motherboards import seed_motherboards


class FakeResult:
    def __init__(self, *, upserted_id: str | None = None, modified_count: int = 0):
        self.upserted_id = upserted_id
        self.modified_count = modified_count


class FakeCollection:
    def __init__(self):
        self.indexes: list[tuple[list[tuple[str, int]], bool]] = []
        self.operations: list[tuple[dict[str, Any], dict[str, Any], bool]] = []
        self.deleted_query: dict[str, Any] | None = None

    def create_index(self, keys: list[tuple[str, int]], unique: bool = False) -> None:
        self.indexes.append((keys, unique))

    def replace_one(self, query: dict[str, Any], replacement: dict[str, Any], upsert: bool = False) -> FakeResult:
        self.operations.append((query, replacement, upsert))
        return FakeResult(upserted_id=query["sku"])

    def delete_many(self, query: dict[str, Any]) -> None:
        self.deleted_query = query


def test_seed_motherboards_upserts_by_sku(monkeypatch) -> None:
    collection = FakeCollection()

    monkeypatch.setattr("app.scripts.seed_motherboards.get_motherboard_collection", lambda: collection)
    monkeypatch.setattr(
        "app.scripts.seed_motherboards.MOTHERBOARDS",
        [
            {
                "name": "Placa-Mãe ASUS TUF Gaming B650M-E, WIFI, AMD AM5, B650, DDR5, Preto - 90MB1FV0-M0EAY0",
                "sku": "90MB1FV0-M0EAY0",
                "brand": "ASUS",
                "cpu_brand": "AMD",
                "socket": "AM5",
                "chipset": "B650",
                "form_factor": None,
                "memory_generation": "DDR5",
                "wifi": True,
                "bluetooth": False,
                "compatibility": {
                    "desktop": True,
                    "cpu_brands": ["AMD"],
                    "sockets": ["AM5"],
                    "memory_generations": ["DDR5"],
                },
            }
        ],
    )

    changed = seed_motherboards()

    assert changed == 1
    assert collection.indexes == [([("sku", 1)], True)]
    assert collection.operations[0][0] == {"sku": "90MB1FV0-M0EAY0"}
    assert collection.operations[0][1]["socket"] == "AM5"
    assert collection.operations[0][2] is True
    assert collection.deleted_query == {"sku": {"$nin": ["90MB1FV0-M0EAY0"]}}
