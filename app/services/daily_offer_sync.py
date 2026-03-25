from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from pymongo.collection import Collection

from app.repositories.daily_cpu_offer_repository import DailyCpuOfferRepository
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
        cpu_collection: Collection,
        daily_offer_repository: DailyCpuOfferRepository,
        telegram_search_service: TelegramSearchServiceProtocol,
        offer_parser: TelegramOfferParser,
        max_offer_age_days: int = 90,
    ) -> None:
        self.cpu_collection = cpu_collection
        self.daily_offer_repository = daily_offer_repository
        self.telegram_search_service = telegram_search_service
        self.offer_parser = offer_parser
        self.max_offer_age_days = max_offer_age_days

    async def sync(self, *, channel: str | None = None, limit: int = 1) -> DailyOfferSyncResult:
        result = DailyOfferSyncResult()
        self.daily_offer_repository.ensure_indexes()
        min_posted_at = datetime.now(UTC) - timedelta(days=self.max_offer_age_days)

        for cpu in self.cpu_collection.find({}, {"sku": 1, "name": 1}).sort("name", 1):
            result.processed += 1

            cpu_sku = str(cpu.get("sku") or "").strip()
            cpu_name = str(cpu.get("name") or "").strip()

            if not cpu_sku or not cpu_name:
                result.skipped += 1
                result.errors.append("CPU sem sku ou nome foi ignorada durante o sync.")
                continue

            try:
                messages = await self.telegram_search_service.search_channel(cpu_name, channel=channel, limit=limit)
            except Exception as exc:
                result.skipped += 1
                result.errors.append(f"{cpu_sku}: falha ao buscar no Telegram ({exc})")
                continue

            if not messages:
                result.skipped += 1
                continue

            result.matched += 1

            try:
                offer = self.offer_parser.parse(messages[0], cpu_sku=cpu_sku, cpu_name=cpu_name)
            except ValueError as exc:
                result.skipped += 1
                result.errors.append(f"{cpu_sku}: {exc}")
                continue

            if self._posted_at_is_too_old(offer.posted_at, min_posted_at):
                result.skipped += 1
                result.errors.append(
                    f"{cpu_sku}: oferta ignorada por antiguidade maior que {self.max_offer_age_days} dias."
                )
                continue

            self.daily_offer_repository.upsert(offer)
            result.persisted += 1

        return result

    @staticmethod
    def _posted_at_is_too_old(posted_at: str | None, min_posted_at: datetime) -> bool:
        if posted_at is None:
            return True

        parsed_posted_at = datetime.fromisoformat(posted_at.replace("Z", "+00:00")).astimezone(UTC)
        return parsed_posted_at < min_posted_at
