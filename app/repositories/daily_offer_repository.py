from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.repositories.protocols import ASCENDING, DESCENDING, CollectionProtocol
from app.schemas.daily_offer import DailyOffer


class DailyOfferRepository:
    def __init__(self, collection: CollectionProtocol) -> None:
        self.collection = collection

    def ensure_indexes(self) -> None:
        self.collection.create_index(
            [
                ("business_date", ASCENDING),
                ("entity_type", ASCENDING),
                ("entity_id", ASCENDING),
                ("store", ASCENDING),
            ],
            unique=True,
            name="daily_offer_unique_entity_store_by_day",
            partialFilterExpression={
                "business_date": {"$type": "string"},
                "entity_type": {"$type": "string"},
                "entity_id": {"$type": "string"},
                "entity_sku": {"$type": "string"},
                "store": {"$type": "string"},
            },
        )
        self.collection.create_index(
            [
                ("entity_type", ASCENDING),
                ("entity_id", ASCENDING),
                ("business_date", DESCENDING),
            ]
        )

    def upsert(self, offer: DailyOffer) -> Any:
        return self.collection.update_one(
            {
                "business_date": offer.business_date,
                "entity_type": offer.entity_type,
                "entity_id": offer.entity_id,
                "store": offer.store,
            },
            {"$set": offer.model_dump()},
            upsert=True,
        )

    def list_today(self, entity_type: str | None = None) -> list[DailyOffer]:
        today = datetime.now(ZoneInfo(settings.business_timezone)).date().isoformat()
        query: dict[str, Any] = {
            "business_date": today,
            "entity_id": {"$type": "string"},
            "entity_sku": {"$type": "string"},
        }
        if entity_type is not None:
            query["entity_type"] = entity_type

        cursor = self.collection.find(query).sort([("entity_name", ASCENDING), ("store", ASCENDING)])
        return [DailyOffer(**document) for document in cursor]
