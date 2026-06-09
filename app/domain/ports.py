"""Hexagonal ports — abstract interfaces defined by the domain layer.

These Protocol classes describe WHAT the domain needs, not HOW it's implemented.
Adapters (MongoDB, Telegram, HTTP) implement these ports.
"""

from __future__ import annotations

from typing import Any, Protocol

from app.schemas.catalog_candidate import CatalogCandidate, PendingDailyOfferEvidence
from app.schemas.common import EntityType
from app.schemas.daily_offer import DailyOffer


# ---------------------------------------------------------------------------
# Repository ports
# ---------------------------------------------------------------------------

class CatalogReader(Protocol):
    """Read access to the hardware catalog (CPUs, GPUs, etc.)."""

    def iter_entities(
        self,
        *,
        entity_type: str,
        query: dict[str, Any] | None = None,
        projection: dict[str, int] | None = None,
    ) -> list[dict[str, Any]]: ...

    def find_by_sku(self, *, entity_type: str, sku: str) -> dict[str, Any] | None: ...

    def upsert_entity(self, *, entity_type: str, document: dict[str, Any]) -> None: ...


class DailyOfferRepository(Protocol):
    """Persist and query daily offers."""

    def ensure_indexes(self) -> None: ...

    def upsert(self, offer: DailyOffer) -> Any: ...

    def list_today(self, entity_type: str | None = None) -> list[DailyOffer]: ...

    def list_recent(self, *, entity_type: str | None = None, max_age_days: int = 90) -> list[DailyOffer]: ...


class CandidateRepository(Protocol):
    """Manage catalog candidates through their lifecycle."""

    def upsert_detected_candidate(
        self,
        *,
        entity_type: EntityType,
        fingerprint: str,
        raw_text: str,
        raw_title: str | None,
        proposed_name: str | None,
        proposed_sku: str | None,
        telegram_message_id: int | None,
        telegram_message_url: str | None,
        product_url: str | None,
        business_date: str | None,
        detection_reason: str | None,
        related_catalog_entity_name: str | None,
        related_catalog_entity_sku: str | None,
        pending_offer: PendingDailyOfferEvidence | None,
    ) -> Any: ...

    def list_pending(self, *, entity_type: EntityType | None = None) -> list[CatalogCandidate]: ...

    def find_one(self, *, entity_type: EntityType, fingerprint: str) -> CatalogCandidate | None: ...

    def mark_enriched(self, fingerprint: str, entity_type: EntityType, enrichment: dict[str, Any]) -> Any: ...

    def mark_enrichment_failed(self, fingerprint: str, entity_type: EntityType, reason: str) -> Any: ...

    def mark_rejected(self, fingerprint: str, entity_type: EntityType, reason: str) -> Any: ...

    def mark_promoted(
        self,
        *,
        fingerprint: str,
        entity_type: EntityType,
        canonical_entity_id: str,
        canonical_entity_sku: str,
    ) -> Any: ...


# ---------------------------------------------------------------------------
# External service ports
# ---------------------------------------------------------------------------

class TelegramSearchPort(Protocol):
    """Search Telegram channels for messages."""

    async def search_channel(
        self,
        query: str,
        channel: str | None = None,
        limit: int = 1,
    ) -> list[dict[str, Any]]: ...

    async def close(self) -> None: ...


class ProductEnricherPort(Protocol):
    """Enrich a detected catalog candidate with product data."""

    def enrich(self, candidate: CatalogCandidate) -> Any: ...

    def is_terminal_error(self, reason: str | None) -> bool: ...