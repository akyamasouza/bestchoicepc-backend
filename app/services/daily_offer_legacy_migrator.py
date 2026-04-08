from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.repositories.protocols import CollectionProtocol
from app.schemas.common import EntityType
from app.services.entity_matcher import EntityMatcher


@dataclass(slots=True)
class DailyOfferLegacyMigrationResult:
    scanned: int = 0
    migrated: int = 0
    unresolved: int = 0
    errors: list[str] = field(default_factory=list)


class DailyOfferLegacyMigrator:
    def __init__(
        self,
        *,
        daily_offer_collection: CollectionProtocol,
        catalog_collections: dict[EntityType, CollectionProtocol],
        entity_matcher: EntityMatcher | None = None,
    ) -> None:
        self.daily_offer_collection = daily_offer_collection
        self.catalog_collections = catalog_collections
        self.entity_matcher = entity_matcher or EntityMatcher()

    def migrate(self, *, apply: bool = False) -> DailyOfferLegacyMigrationResult:
        result = DailyOfferLegacyMigrationResult()
        catalog = self._load_catalog()
        planned_keys: set[tuple[str, str, str, str]] = set()

        for offer in self._legacy_offers():
            result.scanned += 1

            entity_type = offer.get("entity_type")
            raw_text = str(offer.get("raw_text") or "").strip()
            if entity_type not in catalog or not raw_text:
                result.unresolved += 1
                result.errors.append(self._unresolved_message(offer, "sem entity_type suportado ou raw_text"))
                continue

            match = self._find_match(raw_text=raw_text, candidates=catalog[entity_type])
            if match is None:
                result.unresolved += 1
                result.errors.append(self._unresolved_message(offer, "sem match no catalogo"))
                continue

            canonical_key = self._canonical_key(offer, match)
            if canonical_key in planned_keys or self._canonical_offer_exists(offer, match):
                result.unresolved += 1
                result.errors.append(self._unresolved_message(offer, "duplicaria uma oferta canonica"))
                continue

            if apply:
                self.daily_offer_collection.update_one(
                    self._offer_identity_query(offer),
                    {
                        "$set": {
                            "entity_id": str(match["_id"]),
                            "entity_sku": str(match["sku"]),
                            "entity_name": str(match["name"]),
                        }
                    },
                )

            result.migrated += 1
            planned_keys.add(canonical_key)

        return result

    def _load_catalog(self) -> dict[str, list[dict[str, Any]]]:
        catalog: dict[str, list[dict[str, Any]]] = {}
        for entity_type, collection in self.catalog_collections.items():
            catalog[entity_type] = []
            for item in collection.find({}, {"sku": 1, "name": 1}):
                sku = str(item.get("sku") or "").strip()
                name = str(item.get("name") or "").strip()
                if sku and name:
                    catalog[entity_type].append({
                        "_id": item.get("_id"),
                        "sku": sku,
                        "name": name,
                    })

            catalog[entity_type].sort(key=lambda item: len(str(item["sku"])), reverse=True)

        return catalog

    def _legacy_offers(self) -> list[dict[str, Any]]:
        cursor = self.daily_offer_collection.find(
            {
                "$or": [
                    {"entity_id": {"$exists": False}},
                    {"entity_id": None},
                    {"entity_sku": {"$exists": False}},
                    {"entity_sku": None},
                ]
            }
        )
        return list(cursor)

    def _find_match(self, *, raw_text: str, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
        for item in candidates:
            reason = self.entity_matcher.mismatch_reason(
                entity_name=str(item["name"]),
                entity_id=str(item["sku"]),
                raw_text=raw_text,
            )
            if reason is None:
                return item

        return None

    def _canonical_offer_exists(self, offer: dict[str, Any], match: dict[str, Any]) -> bool:
        existing = self.daily_offer_collection.find_one({
            "business_date": offer.get("business_date"),
            "entity_type": offer.get("entity_type"),
            "entity_id": str(match["_id"]),
            "store": offer.get("store"),
        })
        if existing is None:
            return False

        return existing.get("_id") != offer.get("_id")

    @staticmethod
    def _canonical_key(offer: dict[str, Any], match: dict[str, Any]) -> tuple[str, str, str, str]:
        return (
            str(offer.get("business_date")),
            str(offer.get("entity_type")),
            str(match["_id"]),
            str(offer.get("store")),
        )

    @staticmethod
    def _offer_identity_query(offer: dict[str, Any]) -> dict[str, Any]:
        if "_id" in offer:
            return {"_id": offer["_id"]}

        return {
            "business_date": offer.get("business_date"),
            "entity_type": offer.get("entity_type"),
            "store": offer.get("store"),
            "telegram_message_id": offer.get("telegram_message_id"),
        }

    @staticmethod
    def _unresolved_message(offer: dict[str, Any], reason: str) -> str:
        label = offer.get("_id") or offer.get("telegram_message_url") or offer.get("telegram_message_id") or "sem-id"
        return f"{label}: {reason}"
