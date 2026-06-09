from app.scripts import catalog_candidate_pipeline
from app.application.candidate_pipeline import CatalogCandidatePipelineResult


class FakePipeline:
    def __init__(self, result: CatalogCandidatePipelineResult) -> None:
        self.result = result
        self.calls: list[str | None] = []

    def enrich_pending_candidates(self, *, entity_type: str | None = None) -> CatalogCandidatePipelineResult:
        self.calls.append(entity_type)
        return self.result


def test_run_enrich_calls_pipeline(monkeypatch) -> None:
    fake_pipeline = FakePipeline(CatalogCandidatePipelineResult(enriched=2, errors=["gpu:abc: failed"]))

    monkeypatch.setattr(catalog_candidate_pipeline, "CatalogCandidateRepository", lambda _collection: object())
    monkeypatch.setattr(catalog_candidate_pipeline, "DailyOfferRepository", lambda _collection: object())
    monkeypatch.setattr(catalog_candidate_pipeline, "CatalogCandidateEnricher", lambda: object())
    monkeypatch.setattr(catalog_candidate_pipeline, "TelegramOfferParser", lambda: object())
    monkeypatch.setattr(catalog_candidate_pipeline, "get_catalog_candidate_collection", lambda: object())
    monkeypatch.setattr(catalog_candidate_pipeline, "get_daily_offer_collection", lambda: object())
    monkeypatch.setattr(catalog_candidate_pipeline, "CatalogCandidatePipelineService", lambda **_kwargs: fake_pipeline)

    catalog_candidate_pipeline.run_enrich(entity_type="gpu")

    assert fake_pipeline.calls == ["gpu"]