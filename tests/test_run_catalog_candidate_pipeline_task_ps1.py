from pathlib import Path


def test_task_scheduler_wrapper_contains_batch_command() -> None:
    script = Path("app/scripts/run_catalog_candidate_pipeline_task.ps1").read_text(encoding="utf-8")

    assert "app.scripts.run_catalog_candidate_pipeline" in script
    assert "--entity-type" in script
    assert "--limit" in script
    assert "Set-Location" in script
    assert "$LASTEXITCODE" in script
