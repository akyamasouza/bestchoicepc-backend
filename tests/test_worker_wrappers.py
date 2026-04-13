from app.workers import enrich_worker, sync_worker


def test_sync_worker_delegates_to_combined_pipeline_main(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(sync_worker, "main", lambda: calls.append("sync"))

    sync_worker.main()

    assert calls == ["sync"]


def test_enrich_worker_delegates_to_enrich_script_main(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(enrich_worker, "main", lambda: calls.append("enrich"))

    enrich_worker.main()

    assert calls == ["enrich"]
