from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.repositories.catalog_candidate_repository import CatalogCandidateRepository
from app.repositories.daily_offer_repository import DailyOfferRepository
from app.services.catalog_candidate_enricher import CatalogCandidateEnrichmentResult
from app.services.catalog_candidate_pipeline import CatalogCandidatePipelineService
from app.services.telegram_offer_parser import TelegramOfferParser


class FakeCursor:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self.documents = documents

    def sort(self, key_or_list: str | list[tuple[str, int]], direction: int | None = None) -> "FakeCursor":
        if isinstance(key_or_list, list):
            field = key_or_list[0][0]
            reverse = key_or_list[0][1] == -1
        else:
            field = key_or_list
            reverse = direction == -1
        self.documents = sorted(self.documents, key=lambda item: item.get(field, ""), reverse=reverse)
        return self

    def skip(self, _count: int) -> "FakeCursor":
        return self

    def limit(self, _count: int) -> "FakeCursor":
        return self

    def __iter__(self):
        return iter(self.documents)


class FakeCollection:
    def __init__(self) -> None:
        self.documents: list[dict[str, Any]] = []
        self.indexes: list[tuple[list[tuple[str, int]], bool, dict[str, Any]]] = []
        self.updates: list[tuple[dict[str, Any], dict[str, Any], bool]] = []
        self.next_id = 1

    def count_documents(self, query: dict[str, Any]) -> int:
        return len([doc for doc in self.documents if self._matches(doc, query)])

    def find(self, query: dict[str, Any], projection: dict[str, int] | None = None) -> FakeCursor:
        return FakeCursor([self._project(doc, projection) for doc in self.documents if self._matches(doc, query)])

    def find_one(self, query: dict[str, Any], projection: dict[str, int] | None = None) -> dict[str, Any] | None:
        for document in self.documents:
            if self._matches(document, query):
                return self._project(document, projection)
        return None

    def create_index(self, keys: list[tuple[str, int]], unique: bool = False, **kwargs: Any) -> None:
        self.indexes.append((keys, unique, kwargs))

    def update_one(self, query: dict[str, Any], update: dict[str, Any], upsert: bool = False) -> object:
        self.updates.append((query, update, upsert))
        for document in self.documents:
            if self._matches(document, query):
                self._apply_update(document, update)
                return object()

        if not upsert:
            return object()

        document = {"_id": f"generated-{self.next_id}"}
        self.next_id += 1
        for key, value in query.items():
            if not isinstance(value, dict):
                document[key] = value
        self._apply_update(document, update)
        self.documents.append(document)
        return object()

    def update_many(self, query: dict[str, Any], update: dict[str, Any]) -> object:
        for document in self.documents:
            if self._matches(document, query):
                self._apply_update(document, update)
        return object()

    def replace_one(self, query: dict[str, Any], replacement: dict[str, Any], upsert: bool = False) -> object:
        for index, document in enumerate(self.documents):
            if self._matches(document, query):
                replacement = dict(replacement)
                replacement.setdefault("_id", document.get("_id"))
                self.documents[index] = replacement
                return object()
        if upsert:
            replacement = dict(replacement)
            replacement.setdefault("_id", f"generated-{self.next_id}")
            self.next_id += 1
            self.documents.append(replacement)
        return object()

    @staticmethod
    def _project(document: dict[str, Any], projection: dict[str, int] | None) -> dict[str, Any]:
        if projection is None:
            return dict(document)
        projected = {key: value for key, value in document.items() if key in projection or key == "_id"}
        return projected

    @staticmethod
    def _matches(document: dict[str, Any], query: dict[str, Any]) -> bool:
        for key, value in query.items():
            if isinstance(value, dict) and "$in" in value:
                if document.get(key) not in value["$in"]:
                    return False
                continue
            if document.get(key) != value:
                return False
        return True

    @staticmethod
    def _apply_update(document: dict[str, Any], update: dict[str, Any]) -> None:
        for key, value in update.get("$set", {}).items():
            document[key] = value
        for key, value in update.get("$setOnInsert", {}).items():
            document.setdefault(key, value)
        for key, value in update.get("$inc", {}).items():
            document[key] = int(document.get(key, 0)) + int(value)


class FakeEnricher:
    def __init__(self, data: dict[str, Any] | None, error: str | None = None) -> None:
        self.data = data
        self.error = error

    def enrich(self, _candidate: Any) -> CatalogCandidateEnrichmentResult:
        return CatalogCandidateEnrichmentResult(data=self.data, error=self.error)


def build_pipeline(
    candidate_collection: FakeCollection,
    daily_offer_collection: FakeCollection,
    *,
    enricher: FakeEnricher | None = None,
) -> CatalogCandidatePipelineService:
    return CatalogCandidatePipelineService(
        candidate_repository=CatalogCandidateRepository(candidate_collection),
        daily_offer_repository=DailyOfferRepository(daily_offer_collection),
        offer_parser=TelegramOfferParser(),
        enricher=enricher,
    )


def test_detect_from_message_creates_multi_hardware_candidate() -> None:
    candidate_collection = FakeCollection()
    daily_offer_collection = FakeCollection()
    pipeline = build_pipeline(candidate_collection, daily_offer_collection)

    detected = pipeline.detect_from_message(
        entity_type="gpu",
        catalog_entity_name="GeForce RTX 5070",
        catalog_entity_sku="geforce-rtx-5070",
        message={
            "id": 10,
            "date_iso": "2026-03-25T22:02:51+00:00",
            "text": "Placa de Video PNY GeForce RTX 5070 Ti OC 16GB R$ 6.599,00 Loja: Kabum https://www.kabum.com.br/produto/123",
            "url": "https://t.me/pcbuildwizard/10",
        },
        reason="mensagem rejeitada por discriminadores conflitantes: ti",
    )

    assert detected is True
    stored = candidate_collection.documents[0]
    assert stored["entity_type"] == "gpu"
    assert stored["proposed_name"] == "Placa de Video PNY GeForce RTX 5070 Ti OC 16GB"
    assert stored["status"] == "pending_enrichment"
    assert stored["pending_offer"]["store"] == "kabum"


def test_enrich_pending_candidates_marks_candidate_as_enriched() -> None:
    candidate_collection = FakeCollection()
    daily_offer_collection = FakeCollection()
    pipeline = build_pipeline(
        candidate_collection,
        daily_offer_collection,
        enricher=FakeEnricher(
            {
                "proposed_name": "AMD Ryzen 7 5700X3D",
                "proposed_sku": "amd-ryzen-7-5700x3d",
                "product_url": "https://example.com/cpu",
                "raw_title": "AMD Ryzen 7 5700X3D",
                "socket": "AM4",
            }
        ),
    )
    pipeline.detect_from_message(
        entity_type="cpu",
        catalog_entity_name="AMD Ryzen 7 5700X",
        catalog_entity_sku="amd-ryzen-7-5700x",
        message={
            "id": 11,
            "date_iso": "2026-03-25T22:02:51+00:00",
            "text": "AMD Ryzen 7 5700X3D R$ 1.599,00 Loja: Amazon https://amazon.com.br/produto/abc",
            "url": "https://t.me/pcbuildwizard/11",
        },
        reason="mensagem rejeitada por discriminadores conflitantes: x3d",
    )

    result = pipeline.enrich_pending_candidates(entity_type="cpu")

    assert result.enriched == 1
    stored = candidate_collection.documents[0]
    assert stored["status"] == "enriched"
    assert stored["enrichment_status"] == "done"
    assert stored["enrichment"]["proposed_sku"] == "amd-ryzen-7-5700x3d"


def test_enrich_pending_candidates_marks_failure_when_enricher_fails() -> None:
    candidate_collection = FakeCollection()
    daily_offer_collection = FakeCollection()
    pipeline = build_pipeline(
        candidate_collection,
        daily_offer_collection,
        enricher=FakeEnricher(None, "failed to fetch product page (timeout)"),
    )
    pipeline.detect_from_message(
        entity_type="ssd",
        catalog_entity_name="SSD Adata 1TB",
        catalog_entity_sku="ssd-adata-1tb",
        message={
            "id": 12,
            "date_iso": "2026-03-25T22:02:51+00:00",
            "text": "SSD Kingston NV3 1TB R$ 399,90 Loja: Kabum https://www.kabum.com.br/produto/999",
            "url": "https://t.me/pcbuildwizard/12",
        },
        reason="mensagem rejeitada por falta de modelo numerico: 1000",
    )

    result = pipeline.enrich_pending_candidates(entity_type="ssd")

    assert result.enriched == 0
    assert len(result.errors) == 1
    assert result.errors[0].startswith("ssd:")
    assert result.errors[0].endswith("failed to fetch product page (timeout)")
    assert candidate_collection.documents[0]["enrichment_status"] == "failed"


def test_promote_candidate_persists_catalog_document_and_offer() -> None:
    candidate_collection = FakeCollection()
    daily_offer_collection = FakeCollection()
    pipeline = build_pipeline(
        candidate_collection,
        daily_offer_collection,
        enricher=FakeEnricher(
            {
                "proposed_name": "SSD Kingston NV3 1TB NVMe PCIe 4.0",
                "proposed_sku": "ssd-kingston-nv3-1tb-nvme-pcie-4-0",
                "product_url": "https://www.kabum.com.br/produto/999",
                "raw_title": "SSD Kingston NV3 1TB",
                "brand": "SSD",
                "capacity_gb": 1024,
                "interface": "NVMe",
            }
        ),
    )
    pipeline.detect_from_message(
        entity_type="ssd",
        catalog_entity_name="SSD Adata 1TB",
        catalog_entity_sku="ssd-adata-1tb",
        message={
            "id": 12,
            "date_iso": "2026-03-25T22:02:51+00:00",
            "text": "SSD Kingston NV3 1TB R$ 399,90 Loja: Kabum https://www.kabum.com.br/produto/999",
            "url": "https://t.me/pcbuildwizard/12",
        },
        reason="mensagem rejeitada por falta de modelo numerico: 1000",
    )
    pipeline.enrich_pending_candidates(entity_type="ssd")

    canonical_collection = FakeCollection()

    result = pipeline.promote_candidate(
        entity_type="ssd",
        fingerprint=candidate_collection.documents[0]["fingerprint"],
        catalog_collection=canonical_collection,
    )

    assert result.promoted == 1
    assert result.offers_persisted == 1
    assert canonical_collection.documents[0]["sku"] == "ssd-kingston-nv3-1tb-nvme-pcie-4-0"
    assert daily_offer_collection.updates[0][0]["entity_type"] == "ssd"


def test_promote_candidate_requires_minimum_fields_for_ram() -> None:
    candidate_collection = FakeCollection()
    daily_offer_collection = FakeCollection()
    pipeline = build_pipeline(candidate_collection, daily_offer_collection)

    candidate_collection.documents.append(
        {
            "_id": "candidate-1",
            "entity_type": "ram",
            "fingerprint": "fp-1",
            "proposed_name": None,
            "proposed_sku": None,
            "raw_title": None,
            "raw_text": "Mensagem incompleta",
            "status": "enriched",
            "enrichment_status": "done",
            "enrichment": {},
            "first_seen": datetime(2026, 3, 25, tzinfo=UTC).isoformat(),
            "last_seen": datetime(2026, 3, 25, tzinfo=UTC).isoformat(),
            "evidence_count": 1,
        }
    )

    result = pipeline.promote_candidate(entity_type="ram", fingerprint="fp-1")

    assert result.promoted == 0
    assert result.errors == ["ram:fp-1: candidato sem dados minimos para promocao"]
