from __future__ import annotations

import asyncio

from app.scripts import sync_daily_offers
from app.services.daily_offer_sync import DailyOfferSyncResult


class FakeSyncService:
    def __init__(self, result: DailyOfferSyncResult) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    async def sync(self, *, channel: str | None = None, limit: int = 1, object_id: str | None = None) -> DailyOfferSyncResult:
        self.calls.append({"channel": channel, "limit": limit, "object_id": object_id})
        return self.result


class FakeTelegramSearchService:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


def test_run_uses_canonical_sync_service(monkeypatch) -> None:
    fake_service = FakeSyncService(DailyOfferSyncResult(processed=2, matched=1, persisted=1, skipped=1, errors=[]))
    fake_telegram = FakeTelegramSearchService()

    monkeypatch.setattr(sync_daily_offers, "TelegramChannelSearchService", lambda: fake_telegram)
    monkeypatch.setattr(sync_daily_offers, "CatalogCandidateRepository", lambda _collection: object())
    monkeypatch.setattr(sync_daily_offers, "DailyOfferRepository", lambda _collection: object())
    monkeypatch.setattr(sync_daily_offers, "CatalogCandidateEnricher", lambda: object())
    monkeypatch.setattr(sync_daily_offers, "TelegramOfferParser", lambda: object())
    monkeypatch.setattr(sync_daily_offers, "CatalogCandidatePipelineService", lambda **_kwargs: object())
    monkeypatch.setattr(sync_daily_offers, "DailyOfferSyncService", lambda **_kwargs: fake_service)
    monkeypatch.setattr(sync_daily_offers, "get_catalog_candidate_collection", lambda: object())
    monkeypatch.setattr(sync_daily_offers, "get_daily_offer_collection", lambda: object())
    monkeypatch.setattr(sync_daily_offers, "get_catalog_collection", lambda _entity_type: object())

    result = asyncio.run(sync_daily_offers.run(entity_type="gpu", channel="@pcbuildwizard", limit=2, object_id="abc"))

    assert result == 0
    assert fake_service.calls == [{"channel": "@pcbuildwizard", "limit": 2, "object_id": "abc"}]
    assert fake_telegram.closed is True


def test_run_returns_non_zero_when_sync_has_errors(monkeypatch) -> None:
    fake_service = FakeSyncService(DailyOfferSyncResult(processed=1, matched=1, persisted=0, skipped=1, errors=["gpu: erro"]))
    fake_telegram = FakeTelegramSearchService()

    monkeypatch.setattr(sync_daily_offers, "TelegramChannelSearchService", lambda: fake_telegram)
    monkeypatch.setattr(sync_daily_offers, "CatalogCandidateRepository", lambda _collection: object())
    monkeypatch.setattr(sync_daily_offers, "DailyOfferRepository", lambda _collection: object())
    monkeypatch.setattr(sync_daily_offers, "CatalogCandidateEnricher", lambda: object())
    monkeypatch.setattr(sync_daily_offers, "TelegramOfferParser", lambda: object())
    monkeypatch.setattr(sync_daily_offers, "CatalogCandidatePipelineService", lambda **_kwargs: object())
    monkeypatch.setattr(sync_daily_offers, "DailyOfferSyncService", lambda **_kwargs: fake_service)
    monkeypatch.setattr(sync_daily_offers, "get_catalog_candidate_collection", lambda: object())
    monkeypatch.setattr(sync_daily_offers, "get_daily_offer_collection", lambda: object())
    monkeypatch.setattr(sync_daily_offers, "get_catalog_collection", lambda _entity_type: object())

    result = asyncio.run(sync_daily_offers.run(entity_type="gpu"))

    assert result == 1
    assert fake_telegram.closed is True
