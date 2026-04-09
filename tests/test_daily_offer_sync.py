from __future__ import annotations

import asyncio
from typing import Any

from app.repositories.catalog_candidate_repository import CatalogCandidateRepository
from app.repositories.daily_offer_repository import DailyOfferRepository
from app.services.catalog_candidate_pipeline import CatalogCandidatePipelineService
from app.services.daily_offer_sync import DailyOfferSyncService
from app.services.telegram_offer_parser import TelegramOfferParser


class FakeCursor:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self.documents = documents

    def sort(self, field: str, direction: int) -> list[dict[str, Any]]:
        reverse = direction == -1
        return sorted(self.documents, key=lambda item: item.get(field, ""), reverse=reverse)


class FakeCatalogCollection:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self.documents = documents

    def find(self, *_args: Any, **_kwargs: Any) -> FakeCursor:
        return FakeCursor(self.documents)


class FakeOfferCollection:
    def __init__(self) -> None:
        self.indexes: list[tuple[list[tuple[str, int]], bool, dict[str, Any]]] = []
        self.operations: list[tuple[dict[str, Any], dict[str, Any], bool]] = []

    def create_index(self, keys: list[tuple[str, int]], unique: bool = False, **kwargs: Any) -> None:
        self.indexes.append((keys, unique, kwargs))

    def update_one(self, query: dict[str, Any], update: dict[str, Any], upsert: bool = False) -> object:
        self.operations.append((query, update, upsert))
        return object()


class FakeCandidateCollection:
    def __init__(self) -> None:
        self.documents: list[dict[str, Any]] = []
        self.indexes: list[tuple[list[tuple[str, int]], bool, dict[str, Any]]] = []

    def count_documents(self, query: dict[str, Any]) -> int:
        return len([doc for doc in self.documents if self._matches(doc, query)])

    def find(self, query: dict[str, Any], projection: dict[str, int] | None = None) -> FakeCursor:
        documents = [self._project(doc, projection) for doc in self.documents if self._matches(doc, query)]
        return FakeCursor(documents)

    def find_one(self, query: dict[str, Any], projection: dict[str, int] | None = None) -> dict[str, Any] | None:
        for document in self.documents:
            if self._matches(document, query):
                return self._project(document, projection)
        return None

    def create_index(self, keys: list[tuple[str, int]], unique: bool = False, **kwargs: Any) -> None:
        self.indexes.append((keys, unique, kwargs))

    def update_one(self, query: dict[str, Any], update: dict[str, Any], upsert: bool = False) -> object:
        for document in self.documents:
            if self._matches(document, query):
                self._apply_update(document, update)
                return object()
        if upsert:
            document = dict(query)
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
            self.documents.append(dict(replacement))
        return object()

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
    def _project(document: dict[str, Any], projection: dict[str, int] | None) -> dict[str, Any]:
        if projection is None:
            return dict(document)
        return {key: value for key, value in document.items() if key in projection or key == "_id"}

    @staticmethod
    def _apply_update(document: dict[str, Any], update: dict[str, Any]) -> None:
        for key, value in update.get("$set", {}).items():
            document[key] = value
        for key, value in update.get("$setOnInsert", {}).items():
            document.setdefault(key, value)
        for key, value in update.get("$inc", {}).items():
            document[key] = int(document.get(key, 0)) + int(value)


class FakeTelegramSearchService:
    def __init__(self, responses: dict[str, list[dict[str, Any]]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str | None, int]] = []
        self.exceptions: dict[str, Exception] = {}

    async def search_channel(self, query: str, channel: str | None = None, limit: int = 1) -> list[dict[str, Any]]:
        self.calls.append((query, channel, limit))
        if query in self.exceptions:
            raise self.exceptions[query]
        return self.responses.get(query, [])


def build_candidate_pipeline(candidate_collection: FakeCandidateCollection, offer_collection: FakeOfferCollection) -> CatalogCandidatePipelineService:
    repository = DailyOfferRepository(offer_collection)
    return CatalogCandidatePipelineService(
        candidate_repository=CatalogCandidateRepository(candidate_collection),
        daily_offer_repository=repository,
        offer_parser=TelegramOfferParser(),
    )


def test_sync_persists_one_daily_offer_per_cpu_query() -> None:
    catalog_collection = FakeCatalogCollection(
        [
            {"_id": "id-1", "sku": "ryzen-7-9800x3d", "name": "AMD Ryzen 7 9800X3D"},
            {"_id": "id-2", "sku": "ryzen-7-9700x", "name": "AMD Ryzen 7 9700X"},
        ]
    )
    offer_collection = FakeOfferCollection()
    repository = DailyOfferRepository(offer_collection)
    telegram_search_service = FakeTelegramSearchService(
        {
            "ryzen 7 9800x3d": [
                {
                    "id": 883696,
                    "date_iso": "2026-03-25T22:02:51+00:00",
                    "text": (
                        "Processador AMD Ryzen 7 9800X3D, 8-Core, SMT, AM5, PCIe x16 5.0 "
                        "R$ 2.799,99 em 10 parcelas Frete Grátis Loja: Amazon "
                        "https://www.pcbuildwizard.com/product/N1nnkp/amazon.com.br?source=pcbuildwizard-tg "
                        "Menor preço em 90 dias: R$ 2.679,98 Mediana dos preços de 90 dias: R$ 2.980,35"
                    ),
                    "url": "https://t.me/pcbuildwizard/883696",
                }
            ],
            "ryzen 7 9700x": [],
        }
    )
    service = DailyOfferSyncService(
        catalog_collection=catalog_collection,
        entity_type="cpu",
        daily_offer_repository=repository,
        telegram_search_service=telegram_search_service,
        offer_parser=TelegramOfferParser(business_timezone="America/Manaus"),
    )

    result = asyncio.run(service.sync())

    assert result.processed == 2
    assert result.matched == 1
    assert result.persisted == 1
    assert result.skipped == 1
    assert result.errors == []
    assert telegram_search_service.calls == [
        ("ryzen 7 9700x", None, 1),
        ("ryzen 7 9800x3d", None, 1),
    ]
    assert offer_collection.indexes == [
        (
            [("business_date", 1), ("entity_type", 1), ("entity_id", 1), ("store", 1)],
            True,
            {
                "name": "daily_offer_unique_entity_store_by_day",
                "partialFilterExpression": {
                    "business_date": {"$type": "string"},
                    "entity_type": {"$type": "string"},
                    "entity_id": {"$type": "string"},
                    "entity_sku": {"$type": "string"},
                    "store": {"$type": "string"},
                },
            },
        ),
        ([("entity_type", 1), ("entity_id", 1), ("business_date", -1)], False, {}),
    ]
    assert offer_collection.operations[0][0] == {
        "business_date": "2026-03-25",
        "entity_type": "cpu",
        "entity_id": "id-1",
        "store": "amazon",
    }


def test_sync_collects_parser_errors_and_continues() -> None:
    catalog_collection = FakeCatalogCollection([{"_id": "id-1", "sku": "ryzen-7-9800x3d", "name": "AMD Ryzen 7 9800X3D"}])
    offer_collection = FakeOfferCollection()
    repository = DailyOfferRepository(offer_collection)
    telegram_search_service = FakeTelegramSearchService(
        {
            "ryzen 7 9800x3d": [
                {
                    "id": 1,
                    "date_iso": "2026-03-25T22:02:51+00:00",
                    "text": "Mensagem sem loja nem link",
                    "url": "https://t.me/pcbuildwizard/1",
                }
            ]
        }
    )
    service = DailyOfferSyncService(
        catalog_collection=catalog_collection,
        entity_type="cpu",
        daily_offer_repository=repository,
        telegram_search_service=telegram_search_service,
        offer_parser=TelegramOfferParser(),
    )

    result = asyncio.run(service.sync())

    assert result.processed == 1
    assert result.matched == 1
    assert result.persisted == 0
    assert result.skipped == 1
    assert result.errors == ["ryzen-7-9800x3d: Could not extract store from Telegram message."]
    assert offer_collection.operations == []


def test_sync_persists_old_offers_when_found() -> None:
    catalog_collection = FakeCatalogCollection([{"_id": "id-1", "sku": "ryzen-7-9800x3d", "name": "AMD Ryzen 7 9800X3D"}])
    offer_collection = FakeOfferCollection()
    repository = DailyOfferRepository(offer_collection)
    telegram_search_service = FakeTelegramSearchService(
        {
            "ryzen 7 9800x3d": [
                {
                    "id": 1,
                    "date_iso": "2025-11-01T22:02:51+00:00",
                    "text": (
                        "Processador AMD Ryzen 7 9800X3D R$ 2.799,99 em 10 parcelas "
                        "Loja: Amazon https://www.pcbuildwizard.com/product/N1nnkp/amazon.com.br?source=pcbuildwizard-tg"
                    ),
                    "url": "https://t.me/pcbuildwizard/1",
                }
            ]
        }
    )
    service = DailyOfferSyncService(
        catalog_collection=catalog_collection,
        entity_type="cpu",
        daily_offer_repository=repository,
        telegram_search_service=telegram_search_service,
        offer_parser=TelegramOfferParser(),
    )

    result = asyncio.run(service.sync())

    assert result.processed == 1
    assert result.matched == 1
    assert result.persisted == 1
    assert result.skipped == 0
    assert result.errors == []
    assert len(offer_collection.operations) == 1


def test_sync_collects_search_errors_and_continues() -> None:
    catalog_collection = FakeCatalogCollection(
        [
            {"_id": "id-1", "sku": "ryzen-7-9800x3d", "name": "AMD Ryzen 7 9800X3D"},
            {"_id": "id-2", "sku": "ryzen-7-9700x", "name": "AMD Ryzen 7 9700X"},
        ]
    )
    offer_collection = FakeOfferCollection()
    repository = DailyOfferRepository(offer_collection)
    telegram_search_service = FakeTelegramSearchService(
        {
            "ryzen 7 9700x": [
                {
                    "id": 2,
                    "date_iso": "2026-03-25T22:02:51+00:00",
                    "text": (
                        "Processador AMD Ryzen 7 9700X R$ 2.199,99 "
                        "Loja: Amazon https://www.pcbuildwizard.com/product/abc/amazon.com.br?source=pcbuildwizard-tg"
                    ),
                    "url": "https://t.me/pcbuildwizard/2",
                }
            ]
        }
    )
    telegram_search_service.exceptions["ryzen 7 9800x3d"] = RuntimeError("429")
    service = DailyOfferSyncService(
        catalog_collection=catalog_collection,
        entity_type="cpu",
        daily_offer_repository=repository,
        telegram_search_service=telegram_search_service,
        offer_parser=TelegramOfferParser(),
    )

    result = asyncio.run(service.sync())

    assert result.processed == 2
    assert result.matched == 1
    assert result.persisted == 1
    assert result.skipped == 1
    assert result.errors == ["ryzen-7-9800x3d: falha ao buscar no Telegram (429)"]
    assert len(offer_collection.operations) == 1


def test_sync_persists_gpu_offers_with_gpu_entity_type() -> None:
    catalog_collection = FakeCatalogCollection([{"_id": "id-3", "sku": "geforce-rtx-5090", "name": "GeForce RTX 5090"}])
    offer_collection = FakeOfferCollection()
    repository = DailyOfferRepository(offer_collection)
    telegram_search_service = FakeTelegramSearchService(
        {
            "geforce rtx 5090": [
                {
                    "id": 10,
                    "date_iso": "2026-03-25T22:02:51+00:00",
                    "text": "GeForce RTX 5090 R$ 19.999,99 em 10 parcelas Loja: Kabum https://www.kabum.com.br/produto/123",
                    "url": "https://t.me/pcbuildwizard/10",
                }
            ]
        }
    )
    service = DailyOfferSyncService(
        catalog_collection=catalog_collection,
        entity_type="gpu",
        daily_offer_repository=repository,
        telegram_search_service=telegram_search_service,
        offer_parser=TelegramOfferParser(),
    )

    result = asyncio.run(service.sync())

    assert result.processed == 1
    assert result.matched == 1
    assert result.persisted == 1
    assert result.skipped == 0
    assert result.errors == []
    assert offer_collection.operations[0][0] == {
        "business_date": "2026-03-25",
        "entity_type": "gpu",
        "entity_id": "id-3",
        "store": "kabum",
    }


def test_sync_rejects_gpu_variant_mismatch_before_persisting() -> None:
    catalog_collection = FakeCatalogCollection([{"_id": "id-4", "sku": "geforce-rtx-5070", "name": "GeForce RTX 5070"}])
    offer_collection = FakeOfferCollection()
    repository = DailyOfferRepository(offer_collection)
    telegram_search_service = FakeTelegramSearchService(
        {
            "geforce rtx 5070": [
                {
                    "id": 883615,
                    "date_iso": "2026-03-25T21:01:41+00:00",
                    "text": (
                        "Placa de Video PNY GeForce RTX 5070 Ti OC 16GB, 16 GB GDDR7, PCIe x16 5.0 "
                        "R$ 6.599,00 Loja: MA InfoStore https://www.mainfostore.com.br/produto/abc"
                    ),
                    "url": "https://t.me/pcbuildwizard/883615",
                }
            ]
        }
    )
    service = DailyOfferSyncService(
        catalog_collection=catalog_collection,
        entity_type="gpu",
        daily_offer_repository=repository,
        telegram_search_service=telegram_search_service,
        offer_parser=TelegramOfferParser(),
    )

    result = asyncio.run(service.sync())

    assert result.processed == 1
    assert result.matched == 1
    assert result.persisted == 0
    assert result.skipped == 1
    assert result.errors == ["geforce-rtx-5070: mensagem rejeitada por discriminadores conflitantes: ti"]
    assert offer_collection.operations == []


def test_sync_registers_multi_hardware_candidate_on_identity_mismatch() -> None:
    catalog_collection = FakeCatalogCollection([{"_id": "id-4", "sku": "geforce-rtx-5070", "name": "GeForce RTX 5070"}])
    offer_collection = FakeOfferCollection()
    candidate_collection = FakeCandidateCollection()
    repository = DailyOfferRepository(offer_collection)
    telegram_search_service = FakeTelegramSearchService(
        {
            "geforce rtx 5070": [
                {
                    "id": 883615,
                    "date_iso": "2026-03-25T21:01:41+00:00",
                    "text": (
                        "Placa de Video PNY GeForce RTX 5070 Ti OC 16GB, 16 GB GDDR7, PCIe x16 5.0 "
                        "R$ 6.599,00 Loja: Kabum https://www.kabum.com.br/produto/123"
                    ),
                    "url": "https://t.me/pcbuildwizard/883615",
                }
            ]
        }
    )
    service = DailyOfferSyncService(
        catalog_collection=catalog_collection,
        entity_type="gpu",
        daily_offer_repository=repository,
        telegram_search_service=telegram_search_service,
        offer_parser=TelegramOfferParser(),
        candidate_pipeline=build_candidate_pipeline(candidate_collection, offer_collection),
    )

    result = asyncio.run(service.sync())

    assert result.persisted == 0
    assert result.skipped == 1
    assert candidate_collection.documents[0]["entity_type"] == "gpu"
    assert candidate_collection.documents[0]["status"] == "pending_enrichment"
    assert candidate_collection.documents[0]["pending_offer"]["store"] == "kabum"
    assert offer_collection.operations == []
