from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from pymongo.collection import Collection

from app.repositories.daily_offer_repository import DailyOfferRepository
from app.services.entity_matcher import EntityMatcher
from app.services.telegram_offer_parser import TelegramOfferParser


class TelegramSearchServiceProtocol(Protocol):
    async def search_channel(
        self,
        query: str,
        channel: str | None = None,
        limit: int = 1,
    ) -> list[dict[str, Any]]: ...


@dataclass(slots=True)
class DailyOfferSyncResult:
    processed: int = 0
    matched: int = 0
    persisted: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


class DailyOfferSyncService:
    def __init__(
        self,
        *,
        catalog_collection: Collection,
        entity_type: str,
        daily_offer_repository: DailyOfferRepository,
        telegram_search_service: TelegramSearchServiceProtocol,
        offer_parser: TelegramOfferParser,
        entity_matcher: EntityMatcher | None = None,
    ) -> None:
        self.catalog_collection = catalog_collection
        self.entity_type = entity_type
        self.daily_offer_repository = daily_offer_repository
        self.telegram_search_service = telegram_search_service
        self.offer_parser = offer_parser
        self.entity_matcher = entity_matcher or EntityMatcher()

    async def sync(self, *, channel: str | None = None, limit: int = 1, object_id: str | None = None) -> DailyOfferSyncResult:
        result = DailyOfferSyncResult()
        self.daily_offer_repository.ensure_indexes()

        entity_label = self.entity_type.upper()

        query = {}
        if object_id is not None:
            from bson.objectid import ObjectId
            query["_id"] = ObjectId(object_id)

        for item in self.catalog_collection.find(query, {"sku": 1, "name": 1}).sort("name", 1):
            result.processed += 1

            entity_sku = str(item.get("sku") or "").strip()
            entity_name = str(item.get("name") or "").strip()

            if not entity_sku or not entity_name:
                result.skipped += 1
                result.errors.append(f"{entity_label} sem sku ou nome foi ignorada durante o sync.")
                continue

            try:
                messages = await self.telegram_search_service.search_channel(entity_name, channel=channel, limit=limit)
            except Exception as exc:
                result.skipped += 1
                result.errors.append(f"{entity_sku}: falha ao buscar no Telegram ({exc})")
                continue

            if not messages:
                result.skipped += 1
                continue

            result.matched += 1

            try:
                offer = self.offer_parser.parse(
                    messages[0],
                    entity_type=self.entity_type,
                    entity_sku=entity_sku,
                    entity_name=entity_name,
                )
            except ValueError as exc:
                result.skipped += 1
                result.errors.append(f"{entity_sku}: {exc}")
                continue

            mismatch_reason = self.entity_matcher.mismatch_reason(
                entity_name=entity_name,
                entity_sku=entity_sku,
                raw_text=offer.raw_text,
            )
            if mismatch_reason is not None:
                result.skipped += 1
                result.errors.append(f"{entity_sku}: {mismatch_reason}")
                continue

            self.daily_offer_repository.upsert(offer)
            result.persisted += 1

        return result
