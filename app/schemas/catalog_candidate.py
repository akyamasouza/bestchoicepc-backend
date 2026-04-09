from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import EntityType

CandidateStatus = Literal["pending_enrichment", "enriched", "promoted", "rejected"]
EnrichmentStatus = Literal["pending", "running", "done", "failed"]


class PendingDailyOfferEvidence(BaseModel):
    business_date: str
    store: str
    store_display_name: str
    price_card: float
    installments: int | None = None
    source_url: str | None = None
    telegram_message_id: int | None = None
    telegram_message_url: str | None = None
    posted_at: str | None = None
    lowest_price_90d: float | None = None
    median_price_90d: float | None = None
    raw_text: str


class CatalogCandidate(BaseModel):
    entity_type: EntityType
    fingerprint: str
    proposed_name: str | None = None
    proposed_sku: str | None = None
    raw_title: str | None = None
    raw_text: str
    telegram_message_id: int | None = None
    telegram_message_url: str | None = None
    product_url: str | None = None
    business_date: str | None = None
    source: str = "telegram"
    status: CandidateStatus = "pending_enrichment"
    enrichment_status: EnrichmentStatus = "pending"
    detection_reason: str | None = None
    related_catalog_entity_name: str | None = None
    related_catalog_entity_sku: str | None = None
    first_seen: str
    last_seen: str
    evidence_count: int = 1
    canonical_entity_id: str | None = None
    canonical_entity_sku: str | None = None
    enrichment: dict[str, Any] = Field(default_factory=dict)
    pending_offer: PendingDailyOfferEvidence | None = None
