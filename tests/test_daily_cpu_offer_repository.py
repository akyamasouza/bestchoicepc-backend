from typing import Any

from app.repositories.daily_offer_repository import DailyOfferRepository
from app.schemas.daily_offer import DailyOffer


class FakeUpdateResult:
    def __init__(self) -> None:
        self.upserted_id = "offer-1"


class FakeCollection:
    def __init__(self) -> None:
        self.indexes: list[tuple[list[tuple[str, int]], bool]] = []
        self.operations: list[tuple[dict[str, Any], dict[str, Any], bool]] = []

    def create_index(self, keys: list[tuple[str, int]], unique: bool = False) -> None:
        self.indexes.append((keys, unique))

    def update_one(self, query: dict[str, Any], update: dict[str, Any], upsert: bool = False) -> FakeUpdateResult:
        self.operations.append((query, update, upsert))
        return FakeUpdateResult()


def test_repository_creates_expected_indexes_and_upserts_by_date_sku_store() -> None:
    collection = FakeCollection()
    repository = DailyOfferRepository(collection)

    repository.ensure_indexes()
    offer = DailyOffer(
        business_date="2026-03-25",
        entity_type="cpu",
        entity_id="100-100001084WOF",
        entity_name="AMD Ryzen 7 9800X3D",
        store="amazon",
        store_display_name="Amazon",
        price_card=2799.99,
        installments=10,
        source_url="https://example.com",
        telegram_message_id=123,
        telegram_message_url="https://t.me/pcbuildwizard/123",
        posted_at="2026-03-25T22:02:51Z",
        lowest_price_90d=2679.98,
        median_price_90d=2980.35,
        raw_text="raw",
    )

    repository.upsert(offer)

    assert collection.indexes == [
        ([("business_date", 1), ("entity_type", 1), ("entity_id", 1), ("store", 1)], True),
        ([("entity_type", 1), ("entity_id", 1), ("business_date", -1)], False),
    ]
    assert collection.operations == [
        (
            {
                "business_date": "2026-03-25",
                "entity_type": "cpu",
                "entity_id": "100-100001084WOF",
                "store": "amazon",
            },
            {"$set": offer.model_dump()},
            True,
        )
    ]
