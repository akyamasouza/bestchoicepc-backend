import logging
from typing import Any

from fastapi.testclient import TestClient

from app.core.logging import HTTP_LOGGER_NAME, REQUEST_ID_HEADER
from app.main import app
from app.routes.matches import get_cpu_repository, get_daily_offer_repository as get_match_daily_offer_repository
from app.routes.matches import get_gpu_repository, get_match_service


class EmptyDailyOfferRepository:
    def list_today(self, entity_type: str | None = None) -> list[object]:
        return []


class EmptyMatchRepository:
    def list_match_candidates(self, *, id: str | None = None, sku: str | None = None) -> list[object]:
        return []


class FailingMatchService:
    def find_matches(self, **_kwargs: object) -> list[object]:
        raise RuntimeError("falha controlada")


def test_http_request_log_includes_structured_request_fields(monkeypatch) -> None:
    records: list[tuple[str, dict[str, Any]]] = []
    logger = logging.getLogger(HTTP_LOGGER_NAME)

    def fake_info(message: str, *args: object, **kwargs: Any) -> None:
        records.append((message, kwargs["extra"]))

    monkeypatch.setattr(logger, "info", fake_info)
    client = TestClient(app)

    response = client.get("/docs", headers={REQUEST_ID_HEADER: "request-123"})

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == "request-123"
    assert records
    message, extra = records[-1]
    assert message == "http_request"
    assert extra["event"] == "http_request"
    assert extra["request_id"] == "request-123"
    assert extra["method"] == "GET"
    assert extra["path"] == "/docs"
    assert extra["status_code"] == 200
    assert isinstance(extra["duration_ms"], float)


def test_http_request_error_log_keeps_response_generic_and_structured(monkeypatch) -> None:
    records: list[tuple[str, dict[str, Any]]] = []
    logger = logging.getLogger(HTTP_LOGGER_NAME)

    def fake_exception(message: str, *args: object, **kwargs: Any) -> None:
        records.append((message, kwargs["extra"]))

    monkeypatch.setattr(logger, "exception", fake_exception)
    app.dependency_overrides[get_match_service] = lambda: FailingMatchService()
    app.dependency_overrides[get_cpu_repository] = lambda: EmptyMatchRepository()
    app.dependency_overrides[get_gpu_repository] = lambda: EmptyMatchRepository()
    app.dependency_overrides[get_match_daily_offer_repository] = lambda: EmptyDailyOfferRepository()
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/matches",
        headers={REQUEST_ID_HEADER: "request-500"},
        json={
            "use_case": "aaa",
            "resolution": "1440p",
            "budget": 5500,
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.headers[REQUEST_ID_HEADER] == "request-500"
    assert response.json() == {"detail": "Erro interno inesperado"}
    assert records
    message, extra = records[-1]
    assert message == "http_request_failed"
    assert extra["event"] == "http_request_failed"
    assert extra["request_id"] == "request-500"
    assert extra["method"] == "POST"
    assert extra["path"] == "/matches"
    assert extra["status_code"] == 500
    assert isinstance(extra["duration_ms"], float)
