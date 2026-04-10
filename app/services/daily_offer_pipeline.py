from __future__ import annotations

import asyncio
import datetime
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

from app.core.database import get_catalog_candidate_collection, get_daily_offer_collection
from app.repositories.catalog_candidate_repository import CatalogCandidateRepository
from app.repositories.daily_offer_repository import DailyOfferRepository
from app.schemas.common import EntityType
from app.services.catalog_candidate_enricher import CatalogCandidateEnricher
from app.services.catalog_candidate_pipeline import CatalogCandidatePipelineService
from app.services.telegram_offer_parser import TelegramOfferParser
from app.services.telegram_search import TelegramChannelSearchService
from pydantic import BaseModel, ValidationError


class OfferSchema(BaseModel):
    name: str
    price: float
    sku: Optional[str] = None


# Observer Pattern for events
class EventObserver(Protocol):
    def on_event(self, event_type: str, data: Dict[str, Any]) -> None:
        ...


# Strategy Pattern for search sources
class SearchStrategy(ABC):
    @abstractmethod
    async def search(self, entity_type: str, channel: str | None, limit: int) -> List[Dict[str, Any]]:
        ...


class TelegramSearchStrategy(SearchStrategy):
    def __init__(self, service: TelegramChannelSearchService, retries: int = 3):
        self.service = service
        self.retries = retries

    async def search(self, entity_type: str, channel: str | None, limit: int) -> List[Dict[str, Any]]:
        # With retry
        for attempt in range(self.retries):
            try:
                results = await self.service.search_channel(entity_type, channel or "default", limit)
                return [{"message": msg, "entity_type": entity_type} for msg in results]
            except Exception as e:
                if attempt == self.retries - 1:
                    raise e
                await asyncio.sleep(1)  # Wait before retry
        return []


# Factory Pattern for candidates
class CandidateFactory:
    @staticmethod
    def create_candidate(raw_data: Dict[str, Any], entity_type: str) -> Dict[str, Any]:
        # Basic validation and creation
        now = datetime.datetime.utcnow()
        candidate = {
            "entity_type": entity_type,
            "raw_data": raw_data,
            "status": "pending",
            "created_at": now,
            "expiry": now + datetime.timedelta(days=7),  # TTL 7 days
        }
        # Add basic fields from raw_data if possible
        return candidate


# Pipeline Pattern
@dataclass
class PipelineResult:
    processed: int = 0
    matched: int = 0
    candidates_created: int = 0
    persisted: int = 0
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class DailyOfferPipeline:
    def __init__(
        self,
        search_strategy: SearchStrategy,
        observer: EventObserver | None = None,
    ):
        self.logger = logging.getLogger(__name__)
        self.search_strategy = search_strategy
        self.observer = observer
        self.candidate_repo = CatalogCandidateRepository(get_catalog_candidate_collection())
        self.daily_offer_repo = DailyOfferRepository(get_daily_offer_collection())
        self.parser = TelegramOfferParser()
        self.enricher = CatalogCandidateEnricher()
        self.pipeline_service = CatalogCandidatePipelineService(
            candidate_repository=self.candidate_repo,
            daily_offer_repository=self.daily_offer_repo,
            offer_parser=self.parser,
            enricher=self.enricher,
        )

    async def run(
        self, entity_type: str, channel: str | None = None, limit: int = 1
    ) -> PipelineResult:
        result = PipelineResult()

        # Stage 1: Search
        self.logger.info(f"Starting search for entity_type={entity_type}, channel={channel}, limit={limit}")
        raw_messages = await self.search_strategy.search(entity_type, channel, limit)
        result.processed = len(raw_messages)
        self.logger.info(f"Search completed: {result.processed} messages found")
        self._notify("search_completed", {"count": result.processed})

        # Stage 2: Parse and Validate
        parsed_offers = []
        for msg in raw_messages:
            try:
                # Simplified parsing for candidates
                parsed = self._simple_parse(msg["message"], entity_type)
                if self._validate_offer(parsed, entity_type):
                    parsed_offers.append(parsed)
                    result.matched += 1
                else:
                    result.errors.append(f"Validation failed for message: {msg}")
            except Exception as e:
                result.errors.append(f"Parsing error: {e}")

        self._notify("parsing_completed", {"matched": result.matched})

        # Stage 3: Create Candidates or Persist
        for offer in parsed_offers:
            if self._entity_exists_in_catalog(offer, entity_type):
                # Persist directly
                await self._persist_offer(offer, entity_type)
                result.persisted += 1
            else:
                # Create candidate
                candidate_data = CandidateFactory.create_candidate(offer, entity_type)
                self.candidate_repo.upsert_detected_candidate(
                    entity_type=entity_type,
                    fingerprint=f"{entity_type}-{offer.get('name', 'unknown')}",
                    raw_text=str(offer),
                    raw_title=offer.get("name"),
                    proposed_name=offer.get("name"),
                    proposed_sku=offer.get("sku"),
                    telegram_message_id=None,
                    telegram_message_url=None,
                    product_url=None,
                    business_date=None,
                    detection_reason="telegram_sync",
                    related_catalog_entity_name=None,
                    related_catalog_entity_sku=None,
                    pending_offer=None,
                )
                result.candidates_created += 1
                self._notify("candidate_created", {"entity_type": entity_type, "data": offer})

        self._notify("pipeline_completed", {"result": result})
        return result

    def _validate_offer(self, offer: Dict[str, Any], entity_type: str) -> bool:
        # Use Pydantic schema for validation
        try:
            OfferSchema(**offer)
            return True
        except ValidationError:
            return False

    def _entity_exists_in_catalog(self, offer: Dict[str, Any], entity_type: str) -> bool:
        # Simplified: check if SKU matches any in catalog
        # In real impl, query catalog collection
        return False  # For now, assume not exists to create candidates

    async def _persist_offer(self, offer: Dict[str, Any], entity_type: str) -> None:
        # Delegate to existing sync service
        pass  # Placeholder

    def _simple_parse(self, message: Dict[str, Any], entity_type: str) -> Dict[str, Any]:
        # Placeholder: extract basic fields from message
        return {
            "name": message.get("text", "").split()[0],  # Simplified
            "price": 100.0,  # Placeholder
            "sku": "unknown",
        }

    def _notify(self, event_type: str, data: Dict[str, Any]) -> None:
        if self.observer:
            self.observer.on_event(event_type, data)