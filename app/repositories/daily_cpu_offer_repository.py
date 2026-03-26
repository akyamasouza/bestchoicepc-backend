from datetime import datetime
from zoneinfo import ZoneInfo

from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.results import UpdateResult

from app.core.config import settings
from app.schemas.daily_cpu_offer import DailyCpuOffer


class DailyCpuOfferRepository:
    def __init__(self, collection: Collection):
        self.collection = collection

    def ensure_indexes(self) -> None:
        self.collection.create_index(
            [
                ("business_date", ASCENDING),
                ("cpu_sku", ASCENDING),
                ("store", ASCENDING),
            ],
            unique=True,
        )
        self.collection.create_index([("cpu_sku", ASCENDING), ("business_date", DESCENDING)])

    def upsert(self, offer: DailyCpuOffer) -> UpdateResult:
        return self.collection.update_one(
            {
                "business_date": offer.business_date,
                "cpu_sku": offer.cpu_sku,
                "store": offer.store,
            },
            {"$set": offer.model_dump()},
            upsert=True,
        )

    def list_today(self) -> list[DailyCpuOffer]:
        today = datetime.now(ZoneInfo(settings.business_timezone)).date().isoformat()
        cursor = self.collection.find({"business_date": today}).sort([("cpu_name", ASCENDING), ("store", ASCENDING)])
        return [DailyCpuOffer(**document) for document in cursor]
