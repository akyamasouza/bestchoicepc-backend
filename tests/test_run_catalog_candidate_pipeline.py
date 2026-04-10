from app.scripts.run_catalog_candidate_pipeline import run
from app.services.hardware_registry import HARDWARE_ENTITY_REGISTRY


class FakeEnrichmentResult:
    def __init__(self, errors: list[str] | None = None) -> None:
        self.errors = errors or []


def test_run_executes_sync_then_enrichment_for_all_entity_types(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    async def fake_sync_run(*, entity_type: str, channel: str | None = None, limit: int = 1) -> int:
        calls.append(("sync", entity_type))
        assert channel is None
        assert limit == 2
        return 0

    def fake_enrich_run(*, entity_type: str | None = None) -> FakeEnrichmentResult:
        calls.append(("enrich", entity_type or ""))
        return FakeEnrichmentResult()

    monkeypatch.setattr("app.scripts.run_catalog_candidate_pipeline.sync_daily_offers.run", fake_sync_run)
    monkeypatch.setattr("app.scripts.run_catalog_candidate_pipeline.enrich_catalog_candidates.run", fake_enrich_run)

    result = run(entity_type="all", limit=2)

    expected_calls: list[tuple[str, str]] = []
    for entity_type in HARDWARE_ENTITY_REGISTRY.keys():
        expected_calls.append(("sync", entity_type))
        expected_calls.append(("enrich", entity_type))
    assert calls == expected_calls
    assert [item.entity_type for item in result.processed_entity_types] == list(HARDWARE_ENTITY_REGISTRY.keys())
    assert result.errors == []


def test_run_continues_after_sync_exception(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    async def fake_sync_run(*, entity_type: str, channel: str | None = None, limit: int = 1) -> int:
        calls.append(("sync", entity_type))
        if entity_type == "cpu":
            raise RuntimeError("boom")
        return 0

    def fake_enrich_run(*, entity_type: str | None = None) -> FakeEnrichmentResult:
        calls.append(("enrich", entity_type or ""))
        return FakeEnrichmentResult()

    monkeypatch.setattr("app.scripts.run_catalog_candidate_pipeline.sync_daily_offers.run", fake_sync_run)
    monkeypatch.setattr("app.scripts.run_catalog_candidate_pipeline.enrich_catalog_candidates.run", fake_enrich_run)

    result = run(entity_type="gpu", limit=1)
    assert result.errors == []

    result = run(entity_type="all", limit=1)

    assert "cpu: sync falhou com excecao (boom)" in result.errors
    assert ("enrich", "cpu") not in calls
    assert ("sync", "gpu") in calls
    assert ("enrich", "gpu") in calls


def test_run_records_sync_and_enrichment_errors(monkeypatch) -> None:
    async def fake_sync_run(*, entity_type: str, channel: str | None = None, limit: int = 1) -> int:
        return 1 if entity_type == "cpu" else 0

    def fake_enrich_run(*, entity_type: str | None = None) -> FakeEnrichmentResult:
        if entity_type == "gpu":
            return FakeEnrichmentResult(errors=["gpu:x: failed"])
        return FakeEnrichmentResult()

    monkeypatch.setattr("app.scripts.run_catalog_candidate_pipeline.sync_daily_offers.run", fake_sync_run)
    monkeypatch.setattr("app.scripts.run_catalog_candidate_pipeline.enrich_catalog_candidates.run", fake_enrich_run)

    cpu_result = run(entity_type="cpu", limit=1)
    assert cpu_result.errors == ["cpu: sync concluiu com erros"]

    gpu_result = run(entity_type="gpu", limit=1)
    assert gpu_result.errors == ["gpu: enrichment concluiu com erros"]
