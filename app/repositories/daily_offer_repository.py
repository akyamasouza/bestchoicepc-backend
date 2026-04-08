from datetime import datetime, timedelta
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
        query = self._canonical_query({"business_date": today})
        if entity_type is not None:
            query["entity_type"] = entity_type

        cursor = self.collection.find(query).sort([("entity_name", ASCENDING), ("store", ASCENDING)])
        return [DailyOffer(**document) for document in cursor]

    def list_recent(self, *, entity_type: str | None = None, max_age_days: int = 90) -> list[DailyOffer]:
        if max_age_days < 0:
            raise ValueError("max_age_days must be greater than or equal to zero.")

        today = datetime.now(ZoneInfo(settings.business_timezone)).date()
        cutoff = (today - timedelta(days=max_age_days)).isoformat()
        query = self._canonical_query({"business_date": {"$gte": cutoff}})
        if entity_type is not None:
            query["entity_type"] = entity_type

        cursor = self.collection.find(query).sort([
            ("business_date", DESCENDING),
            ("entity_name", ASCENDING),
            ("store", ASCENDING),
        ])
        return [DailyOffer(**document) for document in cursor]

    @staticmethod
    def _canonical_query(query: dict[str, Any]) -> dict[str, Any]:
        return {
            **query,
            "entity_id": {"$type": "string"},
            "entity_sku": {"$type": "string"},
            "status": {"$ne": "rejected"},
        }
