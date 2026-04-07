from __future__ import annotations

import asyncio
from typing import Any

from app.repositories.daily_offer_repository import DailyOfferRepository
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
        self.indexes: list[tuple[list[tuple[str, int]], bool]] = []
        self.operations: list[tuple[dict[str, Any], dict[str, Any], bool]] = []

    def create_index(self, keys: list[tuple[str, int]], unique: bool = False) -> None:
        self.indexes.append((keys, unique))

    def update_one(self, query: dict[str, Any], update: dict[str, Any], upsert: bool = False) -> object:
        self.operations.append((query, update, upsert))
        return object()


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
            "AMD Ryzen 7 9800X3D": [
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
            "AMD Ryzen 7 9700X": [],
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
        ("AMD Ryzen 7 9700X", None, 1),
        ("AMD Ryzen 7 9800X3D", None, 1),
    ]
    assert offer_collection.indexes == [
        ([("business_date", 1), ("entity_type", 1), ("entity_id", 1), ("store", 1)], True),
        ([("entity_type", 1), ("entity_id", 1), ("business_date", -1)], False),
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
            "AMD Ryzen 7 9800X3D": [
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
            "AMD Ryzen 7 9800X3D": [
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
            "AMD Ryzen 7 9700X": [
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
    telegram_search_service.exceptions["AMD Ryzen 7 9800X3D"] = RuntimeError("429")
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
            "GeForce RTX 5090": [
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
            "GeForce RTX 5070": [
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
