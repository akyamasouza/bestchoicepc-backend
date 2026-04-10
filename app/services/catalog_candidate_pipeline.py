from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import re
from typing import Any

from app.repositories.catalog_candidate_repository import CatalogCandidateRepository
from app.repositories.daily_offer_repository import DailyOfferRepository
from app.repositories.protocols import CollectionProtocol
from app.schemas.catalog_candidate import PendingDailyOfferEvidence
from app.schemas.common import EntityType
from app.schemas.daily_offer import DailyOffer
from app.services.catalog_candidate_enricher import CatalogCandidateEnricher
from app.services.hardware_registry import HardwareEntityConfig, get_hardware_entity_config
from app.services.telegram_offer_parser import TelegramOfferParser


@dataclass(slots=True)
class CatalogCandidatePipelineResult:
    detected: int = 0
    enriched: int = 0
    promoted: int = 0
    offers_persisted: int = 0
    errors: list[str] = field(default_factory=list)


class CatalogCandidatePipelineService:
    def __init__(
        self,
        *,
        candidate_repository: CatalogCandidateRepository,
        daily_offer_repository: DailyOfferRepository,
        offer_parser: TelegramOfferParser,
        enricher: CatalogCandidateEnricher | None = None,
    ) -> None:
        self.candidate_repository = candidate_repository
        self.daily_offer_repository = daily_offer_repository
        self.offer_parser = offer_parser
        self.enricher = enricher or CatalogCandidateEnricher()

    def detect_from_message(
        self,
        *,
        entity_type: EntityType,
        catalog_entity_name: str,
        catalog_entity_sku: str,
        message: dict[str, Any],
        reason: str,
    ) -> bool:
        raw_text = str(message.get("text") or "").strip()
        if not raw_text:
            return False

        if self.enricher._looks_like_compound_post(raw_text):
            return False

        raw_title = self._extract_title(raw_text)
        if self.enricher._looks_like_compound_name(raw_title):
            return False

        proposed_name = self.enricher._clean_candidate_name(raw_title)
        if proposed_name is None:
            return False

        proposed_sku = self.enricher._normalize_sku(proposed_name)
        if proposed_sku == self.enricher._normalize_sku(catalog_entity_sku):
            return False

        fingerprint = self._fingerprint(
            entity_type=entity_type,
            proposed_sku=proposed_sku,
            telegram_message_url=message.get("url"),
        )
        pending_offer = self._build_pending_offer(
            entity_type=entity_type,
            proposed_sku=proposed_sku,
            proposed_name=proposed_name,
            message=message,
        )
        self.candidate_repository.upsert_detected_candidate(
            entity_type=entity_type,
            fingerprint=fingerprint,
            raw_text=raw_text,
            raw_title=raw_title,
            proposed_name=proposed_name,
            proposed_sku=proposed_sku,
            telegram_message_id=self._parse_int(message.get("id")),
            telegram_message_url=self._parse_optional_str(message.get("url")),
            product_url=pending_offer.source_url if pending_offer is not None else self._first_url(raw_text),
            business_date=pending_offer.business_date if pending_offer is not None else None,
            detection_reason=reason,
            related_catalog_entity_name=catalog_entity_name,
            related_catalog_entity_sku=catalog_entity_sku,
            pending_offer=pending_offer,
        )
        return True

    def enrich_pending_candidates(self, *, entity_type: EntityType | None = None) -> CatalogCandidatePipelineResult:
        result = CatalogCandidatePipelineResult()
        for candidate in self.candidate_repository.list_pending(entity_type=entity_type):
            enrichment_result = self.enricher.enrich(candidate)
            if enrichment_result.data is None:
                reason = enrichment_result.error or "dados minimos insuficientes para promocao"
                if self.enricher.is_terminal_error(reason):
                    self.candidate_repository.mark_rejected(
                        candidate.fingerprint,
                        candidate.entity_type,
                        reason,
                    )
                else:
                    self.candidate_repository.mark_enrichment_failed(
                        candidate.fingerprint,
                        candidate.entity_type,
                        reason,
                    )
                result.errors.append(f"{candidate.entity_type}:{candidate.fingerprint}: {reason}")
                continue

            self.candidate_repository.mark_enriched(candidate.fingerprint, candidate.entity_type, enrichment_result.data)
            result.enriched += 1

        return result

    def promote_candidate(
        self,
        *,
        entity_type: EntityType,
        fingerprint: str,
        catalog_collection: CollectionProtocol | None = None,
    ) -> CatalogCandidatePipelineResult:
        result = CatalogCandidatePipelineResult()
        candidate = self.candidate_repository.find_one(entity_type=entity_type, fingerprint=fingerprint)
        if candidate is None:
            result.errors.append(f"{entity_type}:{fingerprint}: candidato nao encontrado")
            return result

        enrichment = dict(candidate.enrichment)
        if not self._is_promotable(entity_type, enrichment):
            result.errors.append(f"{entity_type}:{fingerprint}: candidato sem dados minimos para promocao")
            return result

        config = get_hardware_entity_config(entity_type)
        target_collection = catalog_collection or config.collection_getter()
        document = self._build_catalog_document(config=config, enrichment=enrichment)

        duplicate_skus = {
            str(document["sku"]),
            self.enricher._normalize_sku(str(document["sku"])),
        }
        canonical_sku = enrichment.get("canonical_sku")
        if canonical_sku is not None:
            duplicate_skus.add(str(canonical_sku))
            duplicate_skus.add(self.enricher._normalize_sku(str(canonical_sku)))

        existing = None
        for duplicate_sku in duplicate_skus:
            if not duplicate_sku:
                continue
            existing = target_collection.find_one({"sku": duplicate_sku}, {"_id": 1, "sku": 1})
            if existing is not None:
                break
        if existing is not None:
            result.errors.append(f"{entity_type}:{fingerprint}: candidato ja existe no catalogo canonico")
            return result

        document["sku"] = self.enricher._normalize_sku(str(document["sku"]))

        target_collection.update_one({"sku": document["sku"]}, {"$set": document}, upsert=True)

        promoted = target_collection.find_one({"sku": document["sku"]}, {"_id": 1, "sku": 1})
        if promoted is None:
            result.errors.append(f"{entity_type}:{fingerprint}: falha ao localizar item promovido")
            return result

        canonical_id = str(promoted["_id"])
        canonical_sku = str(promoted["sku"])
        self.candidate_repository.mark_promoted(
            fingerprint=fingerprint,
            entity_type=entity_type,
            canonical_entity_id=canonical_id,
            canonical_entity_sku=canonical_sku,
        )
        result.promoted += 1

        if candidate.pending_offer is not None:
            self.daily_offer_repository.upsert(
                DailyOffer(
                    business_date=candidate.pending_offer.business_date,
                    entity_type=entity_type,
                    entity_id=canonical_id,
                    entity_sku=canonical_sku,
                    entity_name=document["name"],
                    store=candidate.pending_offer.store,
                    store_display_name=candidate.pending_offer.store_display_name,
                    price_card=candidate.pending_offer.price_card,
                    installments=candidate.pending_offer.installments,
                    source_url=candidate.pending_offer.source_url,
                    telegram_message_id=candidate.pending_offer.telegram_message_id,
                    telegram_message_url=candidate.pending_offer.telegram_message_url,
                    posted_at=candidate.pending_offer.posted_at,
                    lowest_price_90d=candidate.pending_offer.lowest_price_90d,
                    median_price_90d=candidate.pending_offer.median_price_90d,
                    raw_text=candidate.pending_offer.raw_text,
                )
            )
            result.offers_persisted += 1

        return result

    def _build_catalog_document(self, *, config: HardwareEntityConfig, enrichment: dict[str, Any]) -> dict[str, Any]:
        proposed_name = enrichment.get("proposed_name")
        proposed_sku = enrichment.get("proposed_sku")
        document = {
            "name": proposed_name,
            "sku": proposed_sku,
        }
        if config.entity_type in {"ssd", "ram", "psu", "motherboard"} and proposed_name is not None:
            brand = self._brand_from_name(proposed_name)
            if brand is not None:
                document["brand"] = brand
        if config.entity_type == "cpu":
            document["socket"] = enrichment.get("socket")
        if config.entity_type == "gpu":
            document["category"] = enrichment.get("category")
            document["memory_size_mb"] = enrichment.get("memory_size_mb")
        if config.entity_type == "ssd":
            document["capacity_gb"] = enrichment.get("capacity_gb")
            document["interface"] = enrichment.get("interface")
        if config.entity_type == "ram":
            document["generation"] = enrichment.get("generation")
            document["capacity_gb"] = enrichment.get("capacity_gb")
            document["compatibility"] = enrichment.get("compatibility") or {"desktop": True, "notebook": False, "platforms": []}
        if config.entity_type == "psu":
            document["wattage_w"] = enrichment.get("wattage_w")
            document["efficiency_rating"] = enrichment.get("efficiency_rating")
        if config.entity_type == "motherboard":
            document["socket"] = enrichment.get("socket")
            document["compatibility"] = enrichment.get("compatibility") or {"desktop": True, "cpu_brands": [], "sockets": [], "memory_generations": []}
        return {key: value for key, value in document.items() if value is not None}

    @staticmethod
    def _extract_title(raw_text: str) -> str:
        return raw_text.split("R$", 1)[0].strip()

    @staticmethod
    def _fingerprint(*, entity_type: EntityType, proposed_sku: str, telegram_message_url: object) -> str:
        base = f"{entity_type}|{proposed_sku}|{telegram_message_url or ''}"
        return hashlib.sha1(base.encode("utf-8")).hexdigest()

    @staticmethod
    def _parse_int(value: object) -> int | None:
        if value is None:
            return None
        return int(value)

    @staticmethod
    def _parse_optional_str(value: object) -> str | None:
        if value is None:
            return None
        parsed = str(value).strip()
        return parsed or None

    @staticmethod
    def _first_url(raw_text: str) -> str | None:
        match = re.search(r"https?://\S+", raw_text)
        if match is None:
            return None
        return match.group(0).strip()

    @classmethod
    def _build_pending_offer(
        cls,
        *,
        entity_type: EntityType,
        proposed_sku: str,
        proposed_name: str,
        message: dict[str, Any],
    ) -> PendingDailyOfferEvidence | None:
        try:
            offer = TelegramOfferParser().parse(
                message,
                entity_type=entity_type,
                entity_id=f"pending:{proposed_sku}",
                entity_sku=proposed_sku,
                entity_name=proposed_name,
            )
        except ValueError:
            return None

        return PendingDailyOfferEvidence(
            business_date=offer.business_date,
            store=offer.store,
            store_display_name=offer.store_display_name,
            price_card=offer.price_card,
            installments=offer.installments,
            source_url=offer.source_url,
            telegram_message_id=offer.telegram_message_id,
            telegram_message_url=offer.telegram_message_url,
            posted_at=offer.posted_at,
            lowest_price_90d=offer.lowest_price_90d,
            median_price_90d=offer.median_price_90d,
            raw_text=offer.raw_text,
        )

    @staticmethod
    def _brand_from_name(name: str) -> str | None:
        tokens = name.split()
        if not tokens:
            return None
        return tokens[0]

    def _is_promotable(self, entity_type: EntityType, enrichment: dict[str, Any]) -> bool:
        config = get_hardware_entity_config(entity_type)
        document = self._build_catalog_document(config=config, enrichment=enrichment)
        return all(document.get(field) not in (None, "", []) for field in config.required_fields)
