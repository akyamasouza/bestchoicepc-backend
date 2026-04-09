from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.repositories.protocols import ASCENDING, CollectionProtocol
from app.schemas.catalog_candidate import CatalogCandidate, PendingDailyOfferEvidence
from app.schemas.common import EntityType


class CatalogCandidateRepository:
    def __init__(self, collection: CollectionProtocol) -> None:
        self.collection = collection

    def ensure_indexes(self) -> None:
        self.collection.create_index([("entity_type", ASCENDING), ("fingerprint", ASCENDING)], unique=True)
        self.collection.create_index([("status", ASCENDING), ("enrichment_status", ASCENDING), ("entity_type", ASCENDING)])

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
    ) -> Any:
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        set_fields: dict[str, Any] = {
            "raw_text": raw_text,
            "raw_title": raw_title,
            "telegram_message_id": telegram_message_id,
            "telegram_message_url": telegram_message_url,
            "product_url": product_url,
            "business_date": business_date,
            "source": "telegram",
            "status": "pending_enrichment",
            "enrichment_status": "pending",
            "detection_reason": detection_reason,
            "related_catalog_entity_name": related_catalog_entity_name,
            "related_catalog_entity_sku": related_catalog_entity_sku,
            "last_seen": now,
        }
        if proposed_name is not None:
            set_fields["proposed_name"] = proposed_name
        if proposed_sku is not None:
            set_fields["proposed_sku"] = proposed_sku
        if pending_offer is not None:
            set_fields["pending_offer"] = pending_offer.model_dump()

        return self.collection.update_one(
            {"entity_type": entity_type, "fingerprint": fingerprint},
            {
                "$set": set_fields,
                "$setOnInsert": {
                    "entity_type": entity_type,
                    "fingerprint": fingerprint,
                    "first_seen": now,
                    "enrichment": {},
                    "canonical_entity_id": None,
                    "canonical_entity_sku": None,
                },
                "$inc": {"evidence_count": 1},
            },
            upsert=True,
        )

    def list_pending(self, *, entity_type: EntityType | None = None) -> list[CatalogCandidate]:
        query: dict[str, Any] = {"status": "pending_enrichment", "enrichment_status": "pending"}
        if entity_type is not None:
            query["entity_type"] = entity_type

        cursor = self.collection.find(query).sort([("entity_type", ASCENDING), ("last_seen", ASCENDING)])
        return [CatalogCandidate(**document) for document in cursor]

    def list_enriched(self, *, entity_type: EntityType | None = None) -> list[CatalogCandidate]:
        query: dict[str, Any] = {"status": "enriched", "enrichment_status": "done"}
        if entity_type is not None:
            query["entity_type"] = entity_type

        cursor = self.collection.find(query).sort([("entity_type", ASCENDING), ("last_seen", ASCENDING)])
        return [CatalogCandidate(**document) for document in cursor]

    def mark_enriched(self, fingerprint: str, entity_type: EntityType, enrichment: dict[str, Any]) -> Any:
        return self.collection.update_one(
            {"entity_type": entity_type, "fingerprint": fingerprint},
            {"$set": {"enrichment": enrichment, "enrichment_status": "done", "status": "enriched"}},
        )

    def mark_enrichment_failed(self, fingerprint: str, entity_type: EntityType, reason: str) -> Any:
        return self.collection.update_one(
            {"entity_type": entity_type, "fingerprint": fingerprint},
            {"$set": {"enrichment_status": "failed", "enrichment": {"reason": reason}}},
        )

    def mark_promoted(
        self,
        *,
        fingerprint: str,
        entity_type: EntityType,
        canonical_entity_id: str,
        canonical_entity_sku: str,
    ) -> Any:
        return self.collection.update_one(
            {"entity_type": entity_type, "fingerprint": fingerprint},
            {
                "$set": {
                    "status": "promoted",
                    "canonical_entity_id": canonical_entity_id,
                    "canonical_entity_sku": canonical_entity_sku,
                }
            },
        )

    def find_one(self, *, entity_type: EntityType, fingerprint: str) -> CatalogCandidate | None:
        document = self.collection.find_one({"entity_type": entity_type, "fingerprint": fingerprint})
        if document is None:
            return None

        return CatalogCandidate(**document)
