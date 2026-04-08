from __future__ import annotations

from typing import Any

from app.services.daily_offer_legacy_migrator import DailyOfferLegacyMigrator


class FakeCursor:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self.documents = documents

    def __iter__(self):
        return iter(self.documents)


class FakeCollection:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self.documents = documents
        self.updates: list[tuple[dict[str, Any], dict[str, Any]]] = []

    def find(self, query: dict[str, Any], _projection: dict[str, int] | None = None) -> FakeCursor:
        if "$or" in query:
            return FakeCursor([
                document
                for document in self.documents
                if document.get("entity_id") is None or document.get("entity_sku") is None
            ])

        return FakeCursor(self.documents)

    def find_one(self, query: dict[str, Any], _projection: dict[str, int] | None = None) -> dict[str, Any] | None:
        for document in self.documents:
            if all(document.get(field) == value for field, value in query.items()):
                return document

        return None

    def update_one(self, query: dict[str, Any], update: dict[str, Any], upsert: bool = False) -> object:
        self.updates.append((query, update))
        return object()


def test_legacy_migrator_fills_entity_id_and_entity_sku_from_catalog_match() -> None:
    daily_offers = FakeCollection([
        {
            "_id": "offer-1",
            "business_date": "2026-03-23",
            "entity_type": "cpu",
            "entity_id": None,
            "store": "kabum",
            "raw_text": "Processador AMD Ryzen 7 9800X3D R$ 2.799,99 Loja: KaBuM!",
        }
    ])
    cpus = FakeCollection([
        {
            "_id": "507f1f77bcf86cd799439011",
            "sku": "ryzen-7-9800x3d",
            "name": "AMD Ryzen 7 9800X3D",
        }
    ])
    migrator = DailyOfferLegacyMigrator(
        daily_offer_collection=daily_offers,
        catalog_collections={
            "cpu": cpus,
            "gpu": FakeCollection([]),
            "ssd": FakeCollection([]),
            "ram": FakeCollection([]),
            "psu": FakeCollection([]),
            "motherboard": FakeCollection([]),
        },
    )

    result = migrator.migrate(apply=True)

    assert result.scanned == 1
    assert result.migrated == 1
    assert result.unresolved == 0
    assert daily_offers.updates == [
        (
            {"_id": "offer-1"},
            {
                "$set": {
                    "entity_id": "507f1f77bcf86cd799439011",
                    "entity_sku": "ryzen-7-9800x3d",
                    "entity_name": "AMD Ryzen 7 9800X3D",
                }
            },
        )
    ]


def test_legacy_migrator_reports_duplicate_canonical_offer() -> None:
    daily_offers = FakeCollection([
        {
            "_id": "offer-1",
            "business_date": "2026-03-23",
            "entity_type": "cpu",
            "entity_id": "507f1f77bcf86cd799439011",
            "entity_sku": "ryzen-7-9800x3d",
            "store": "kabum",
            "raw_text": "Processador AMD Ryzen 7 9800X3D R$ 2.799,99 Loja: KaBuM!",
        },
        {
            "_id": "offer-2",
            "business_date": "2026-03-23",
            "entity_type": "cpu",
            "entity_id": None,
            "store": "kabum",
            "raw_text": "Processador AMD Ryzen 7 9800X3D R$ 2.799,99 Loja: KaBuM!",
        },
    ])
    cpus = FakeCollection([
        {
            "_id": "507f1f77bcf86cd799439011",
            "sku": "ryzen-7-9800x3d",
            "name": "AMD Ryzen 7 9800X3D",
        }
    ])
    migrator = DailyOfferLegacyMigrator(
        daily_offer_collection=daily_offers,
        catalog_collections={
            "cpu": cpus,
            "gpu": FakeCollection([]),
            "ssd": FakeCollection([]),
            "ram": FakeCollection([]),
            "psu": FakeCollection([]),
            "motherboard": FakeCollection([]),
        },
    )

    result = migrator.migrate(apply=True)

    assert result.scanned == 1
    assert result.migrated == 0
    assert result.unresolved == 1
    assert result.errors == ["offer-2: duplicaria uma oferta canonica"]
    assert daily_offers.updates == []
