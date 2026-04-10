from app.scripts import enrich_catalog_candidates
from app.services.catalog_candidate_pipeline import CatalogCandidatePipelineResult


class FakePipeline:
    def __init__(self, result: CatalogCandidatePipelineResult) -> None:
        self.result = result
        self.calls: list[str | None] = []

    def enrich_pending_candidates(self, *, entity_type: str | None = None) -> CatalogCandidatePipelineResult:
        self.calls.append(entity_type)
        return self.result


def test_run_calls_enrich_pending_candidates(monkeypatch) -> None:
    fake_pipeline = FakePipeline(CatalogCandidatePipelineResult(enriched=2, errors=["gpu:abc: failed"]))

    monkeypatch.setattr(enrich_catalog_candidates, "CatalogCandidateRepository", lambda _collection: object())
    monkeypatch.setattr(enrich_catalog_candidates, "DailyOfferRepository", lambda _collection: object())
    monkeypatch.setattr(enrich_catalog_candidates, "CatalogCandidateEnricher", lambda: object())
    monkeypatch.setattr(enrich_catalog_candidates, "TelegramOfferParser", lambda: object())
    monkeypatch.setattr(enrich_catalog_candidates, "get_catalog_candidate_collection", lambda: object())
    monkeypatch.setattr(enrich_catalog_candidates, "get_daily_offer_collection", lambda: object())
    monkeypatch.setattr(enrich_catalog_candidates, "CatalogCandidatePipelineService", lambda **_kwargs: fake_pipeline)

    result = enrich_catalog_candidates.run(entity_type="gpu")

    assert result.enriched == 2
    assert result.errors == ["gpu:abc: failed"]
    assert fake_pipeline.calls == ["gpu"]
