from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.routes.cpus import get_cpu_repository
from app.routes.daily_offers import get_daily_offer_repository
from app.routes.gpus import get_gpu_repository
from app.routes.matches import (
    get_cpu_repository as get_match_cpu_repository,
    get_daily_offer_repository as get_match_daily_offer_repository,
    get_gpu_repository as get_match_gpu_repository,
    get_match_service,
)


class EmptyDailyOfferRepository:
    def list_today(self, entity_type: str | None = None) -> list[object]:
        return []

    def list_recent(self, *, entity_type: str | None = None, max_age_days: int = 90) -> list[object]:
        return []


class EmptyMatchRepository:
    def list_match_candidates(self, *, id: str | None = None, sku: str | None = None) -> list[object]:
        return []


class EmptyRankingRepository:
    def list_cpus(self, *, brand=None, socket=None, q=None, page=1, limit=20) -> object:
        return {"items": [], "page": page, "limit": limit, "total": 0}

    def list_gpus(self, *, brand=None, category=None, q=None, page=1, limit=20) -> object:
        return {"items": [], "page": page, "limit": limit, "total": 0}

    def list_rankings(self, *args, **kwargs) -> object:
        return {"items": [], "page": kwargs.get("page", 1), "limit": kwargs.get("limit", 20), "total": 0}


class FailingMatchService:
    def find_matches(self, **_kwargs: object) -> list[object]:
        raise RuntimeError("falha controlada")


class SpyMatchService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def find_matches(self, **kwargs: object) -> list[object]:
        self.calls.append(kwargs)
        return []


def _clear_overrides() -> None:
    app.dependency_overrides.clear()


def _assert_validation_error(response, *fields: str) -> None:
    body = response.json()
    assert response.status_code == 422
    assert isinstance(body["detail"], list)
    found_fields = {item["loc"][-1] for item in body["detail"]}
    for field in fields:
        assert field in found_fields


def test_daily_offers_rejects_invalid_entity_type() -> None:
    app.dependency_overrides[get_daily_offer_repository] = lambda: EmptyDailyOfferRepository()
    client = TestClient(app)

    response = client.get("/daily-offers?entity_type=invalid")

    _clear_overrides()

    _assert_validation_error(response, "entity_type")


def test_matches_rejects_invalid_payload() -> None:
    client = TestClient(app)

    response = client.post(
        "/matches",
        json={
            "use_case": "",
            "resolution": "",
            "budget": 5000,
        },
    )

    _assert_validation_error(response, "use_case", "resolution")


def test_matches_normalizes_supported_use_case_aliases() -> None:
    match_service = SpyMatchService()
    app.dependency_overrides[get_match_service] = lambda: match_service
    app.dependency_overrides[get_match_cpu_repository] = lambda: EmptyMatchRepository()
    app.dependency_overrides[get_match_gpu_repository] = lambda: EmptyMatchRepository()
    app.dependency_overrides[get_match_daily_offer_repository] = lambda: EmptyDailyOfferRepository()
    client = TestClient(app)

    response = client.post(
        "/matches",
        json={
            "use_case": "custo-beneficio",
            "resolution": "2160p",
            "budget": 5500,
        },
    )

    _clear_overrides()

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}
    assert len(match_service.calls) == 1
    assert match_service.calls[0]["query"].use_case == "value"
    assert match_service.calls[0]["query"].resolution == "2160p"


def test_matches_returns_bad_request_for_unknown_owned_cpu_and_gpu() -> None:
    app.dependency_overrides[get_match_service] = lambda: FailingMatchService()
    app.dependency_overrides[get_match_cpu_repository] = lambda: EmptyMatchRepository()
    app.dependency_overrides[get_match_gpu_repository] = lambda: EmptyMatchRepository()
    app.dependency_overrides[get_match_daily_offer_repository] = lambda: EmptyDailyOfferRepository()
    client = TestClient(app)

    response = client.post(
        "/matches",
        json={
            "use_case": "aaa",
            "resolution": "1440p",
            "budget": 5500,
            "owned_cpu_id": "cpu-inexistente",
            "owned_gpu_id": "gpu-inexistente",
        },
    )

    _clear_overrides()

    assert response.status_code == 400
    body = response.json()
    assert body["detail"] == "CPU ownada nao encontrada: cpu-inexistente"
    if "error" in body:
        assert body["error"]["code"] == "owned_cpu_not_found"


def test_matches_returns_500_for_unexpected_service_error() -> None:
    app.dependency_overrides[get_match_service] = lambda: FailingMatchService()
    app.dependency_overrides[get_match_cpu_repository] = lambda: EmptyMatchRepository()
    app.dependency_overrides[get_match_gpu_repository] = lambda: EmptyMatchRepository()
    app.dependency_overrides[get_match_daily_offer_repository] = lambda: EmptyDailyOfferRepository()
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/matches",
        json={
            "use_case": "aaa",
            "resolution": "1440p",
            "budget": 5500,
            "limit": 3,
        },
    )

    _clear_overrides()

    assert response.status_code == 500
    assert response.json()["detail"] == "Erro interno inesperado"


def test_routes_reject_invalid_query_values() -> None:
    app.dependency_overrides[get_cpu_repository] = lambda: EmptyRankingRepository()
    app.dependency_overrides[get_gpu_repository] = lambda: EmptyRankingRepository()
    client = TestClient(app)

    invalid_cases = [
        ("/daily-offers?entity_type=invalid", "entity_type"),
        ("/cpus/rankings?sort=up", "sort"),
        ("/gpus/rankings?performance_tier=AB", "performance_tier"),
        ("/cpus?page=0&limit=101", "page"),
    ]

    for path, field in invalid_cases:
        response = client.get(path)
        _assert_validation_error(response, field)

    _clear_overrides()
