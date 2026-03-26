from collections.abc import Iterable, Iterator
from typing import Any

from fastapi.testclient import TestClient

from app.main import app
from app.routes.daily_cpu_offers import get_daily_cpu_offer_repository
from app.schemas.daily_cpu_offer import DailyCpuOffer


class FakeDailyCpuOfferRepository:
    def list_today(self) -> list[DailyCpuOffer]:
        return [
            DailyCpuOffer(
                business_date="2026-03-25",
                cpu_sku="100-100001084WOF",
                cpu_name="AMD Ryzen 7 9800X3D",
                store="amazon",
                store_display_name="Amazon",
                price_card=2799.99,
                installments=10,
                source_url="https://www.pcbuildwizard.com/product/N1nnkp/amazon.com.br?source=pcbuildwizard-tg",
                telegram_message_id=883696,
                telegram_message_url="https://t.me/pcbuildwizard/883696",
                posted_at="2026-03-25T22:02:51Z",
                lowest_price_90d=2679.98,
                median_price_90d=2980.35,
                raw_text="Processador AMD Ryzen 7 9800X3D...",
            )
        ]


class FakeCursor(Iterable[dict[str, Any]]):
    def __init__(self, documents: list[dict[str, Any]]):
        self.documents = documents

    def sort(self, fields: list[tuple[str, int]]) -> "FakeCursor":
        for field, direction in reversed(fields):
            reverse = direction == -1
            self.documents = sorted(self.documents, key=lambda document: document.get(field, ""), reverse=reverse)
        return self

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(self.documents)


class FakeCollection:
    def __init__(self, documents: list[dict[str, Any]]):
        self.documents = documents
        self.find_calls: list[dict[str, Any]] = []

    def find(self, query: dict[str, Any]) -> FakeCursor:
        self.find_calls.append(query)
        filtered = [document for document in self.documents if document.get("business_date") == query["business_date"]]
        return FakeCursor(filtered)


def test_list_today_daily_cpu_offers() -> None:
    app.dependency_overrides[get_daily_cpu_offer_repository] = FakeDailyCpuOfferRepository
    client = TestClient(app)

    response = client.get("/daily-cpu-offers")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == [
        {
            "business_date": "2026-03-25",
            "cpu_sku": "100-100001084WOF",
            "cpu_name": "AMD Ryzen 7 9800X3D",
            "store": "amazon",
            "store_display_name": "Amazon",
            "price_card": 2799.99,
            "installments": 10,
            "source_url": "https://www.pcbuildwizard.com/product/N1nnkp/amazon.com.br?source=pcbuildwizard-tg",
            "telegram_message_id": 883696,
            "telegram_message_url": "https://t.me/pcbuildwizard/883696",
            "posted_at": "2026-03-25T22:02:51Z",
            "lowest_price_90d": 2679.98,
            "median_price_90d": 2980.35,
            "raw_text": "Processador AMD Ryzen 7 9800X3D...",
        }
    ]


def test_daily_cpu_offer_repository_lists_only_today(monkeypatch) -> None:
    from app.repositories.daily_cpu_offer_repository import DailyCpuOfferRepository

    collection = FakeCollection(
        [
            {
                "business_date": "2026-03-25",
                "cpu_sku": "100-100001084WOF",
                "cpu_name": "AMD Ryzen 7 9800X3D",
                "store": "amazon",
                "store_display_name": "Amazon",
                "price_card": 2799.99,
                "installments": 10,
                "source_url": "https://example.com/amazon",
                "telegram_message_id": 1,
                "telegram_message_url": "https://t.me/pcbuildwizard/1",
                "posted_at": "2026-03-25T22:02:51Z",
                "lowest_price_90d": 2679.98,
                "median_price_90d": 2980.35,
                "raw_text": "a",
            },
            {
                "business_date": "2026-03-24",
                "cpu_sku": "100-100001404WOF",
                "cpu_name": "AMD Ryzen 7 9700X",
                "store": "kabum",
                "store_display_name": "KaBuM!",
                "price_card": 2199.99,
                "installments": 10,
                "source_url": "https://example.com/kabum",
                "telegram_message_id": 2,
                "telegram_message_url": "https://t.me/pcbuildwizard/2",
                "posted_at": "2026-03-24T22:02:51Z",
                "lowest_price_90d": 2100.0,
                "median_price_90d": 2400.0,
                "raw_text": "b",
            },
        ]
    )
    monkeypatch.setattr(
        "app.repositories.daily_cpu_offer_repository.datetime",
        type("FrozenDateTime", (), {"now": staticmethod(lambda _tz: __import__("datetime").datetime(2026, 3, 25, 12, 0, 0))}),
    )
    repository = DailyCpuOfferRepository(collection)

    result = repository.list_today()

    assert collection.find_calls == [{"business_date": "2026-03-25"}]
    assert len(result) == 1
    assert result[0].cpu_name == "AMD Ryzen 7 9800X3D"
