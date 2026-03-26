from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from pymongo.collection import Collection

from app.repositories.daily_offer_repository import DailyOfferRepository
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
    ) -> None:
        self.catalog_collection = catalog_collection
        self.entity_type = entity_type
        self.daily_offer_repository = daily_offer_repository
        self.telegram_search_service = telegram_search_service
        self.offer_parser = offer_parser

    async def sync(self, *, channel: str | None = None, limit: int = 1) -> DailyOfferSyncResult:
        result = DailyOfferSyncResult()
        self.daily_offer_repository.ensure_indexes()

        entity_label = self.entity_type.upper()

        for item in self.catalog_collection.find({}, {"sku": 1, "name": 1}).sort("name", 1):
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

            self.daily_offer_repository.upsert(offer)
            result.persisted += 1

        return result
