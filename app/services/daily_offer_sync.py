from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.domain.ports import CandidateRepository, CatalogReader, DailyOfferRepository as DailyOfferRepositoryPort, TelegramSearchPort
from app.repositories.daily_offer_repository import DailyOfferRepository
from app.repositories.protocols import DocumentIdCoercer, identity_document_id
from app.services.catalog_candidate_pipeline import CatalogCandidatePipelineService
from app.domain.entity_matcher import EntityMatcher
from app.services.telegram_offer_parser import TelegramOfferParser


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
        catalog_reader: CatalogReader,
        entity_type: str,
        daily_offer_repository: DailyOfferRepository,
        telegram_search_service: TelegramSearchPort,
        offer_parser: TelegramOfferParser,
        entity_matcher: EntityMatcher | None = None,
        candidate_pipeline: CatalogCandidatePipelineService | None = None,
        document_id_coercer: DocumentIdCoercer = identity_document_id,
    ) -> None:
        self.catalog_reader = catalog_reader
        self.entity_type = entity_type
        self.daily_offer_repository = daily_offer_repository
        self.telegram_search_service = telegram_search_service
        self.offer_parser = offer_parser
        self.entity_matcher = entity_matcher or EntityMatcher()
        self.candidate_pipeline = candidate_pipeline
        self.document_id_coercer = document_id_coercer

    async def sync(self, *, channel: str | None = None, limit: int = 1, object_id: str | None = None) -> DailyOfferSyncResult:
        result = DailyOfferSyncResult()
        self.daily_offer_repository.ensure_indexes()

        entity_label = self.entity_type.upper()

        query = {}
        if object_id is not None:
            query["_id"] = self.document_id_coercer(object_id)

        for item in self.catalog_reader.iter_entities(entity_type=self.entity_type, query=query, projection={"sku": 1, "name": 1}):
            result.processed += 1

            entity_sku = str(item.get("sku") or "").strip()
            entity_name = str(item.get("name") or "").strip()
            entity_id = str(item.get("_id"))

            if not entity_sku or not entity_name:
                result.skipped += 1
                result.errors.append(f"{entity_label} sem sku ou nome foi ignorada durante o sync.")
                continue

            search_query = self._telegram_search_query(entity_sku)

            try:
                messages = await self.telegram_search_service.search_channel(search_query, channel=channel, limit=limit)
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
                    entity_id=entity_id,
                    entity_sku=entity_sku,
                    entity_name=entity_name,
                )
            except ValueError as exc:
                result.skipped += 1
                result.errors.append(f"{entity_sku}: {exc}")
                continue

            mismatch_reason = self.entity_matcher.mismatch_reason(
                entity_name=entity_name,
                entity_id=entity_sku,
                raw_text=messages[0]["text"],
            )
            if mismatch_reason is not None:
                if self.candidate_pipeline is not None:
                    self.candidate_pipeline.detect_from_message(
                        entity_type=self.entity_type,
                        catalog_entity_name=entity_name,
                        catalog_entity_sku=entity_sku,
                        message=messages[0],
                        reason=mismatch_reason,
                    )
                result.skipped += 1
                result.errors.append(f"{entity_sku}: {mismatch_reason}")
                continue

            self.daily_offer_repository.upsert(offer)
            result.persisted += 1

        return result

    @staticmethod
    def _telegram_search_query(entity_sku: str) -> str:
        return " ".join(entity_sku.replace("_", "-").replace("-", " ").split())
