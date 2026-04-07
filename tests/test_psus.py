from typing import Any
from fastapi.testclient import TestClient
from app.main import app
from app.routes.psus import get_psu_repository
from app.schemas.psu import (
    PsuBenchmark,
    PsuListItem,
    PsuListResponse,
    PsuRanking,
    PsuRankingListItem,
    PsuRankingListResponse,
)

class FakePsuRepository:
    def list_psus(self, *, page: int = 1, limit: int = 20) -> PsuListResponse:
        items = [
            PsuListItem(
                id="psu-1",
                name="1st Player NGDP 1000W",
                sku="1st-player-ngdp-1000w",
                brand="1st Player",
                wattage_w=1000,
                form_factor="ATX",
                atx_version="ATX3.0",
                efficiency_rating="PLATINUM",
                noise_rating="Standard++",
                benchmark=PsuBenchmark(cybenetics_score=87.0974),
                ranking=PsuRanking(game_score=87.0974, game_percentile=100.0, performance_tier="S"),
            )
        ]
        return PsuListResponse(items=items, page=page, limit=limit, total=1)

    def list_rankings(self, **_kwargs) -> PsuRankingListResponse:
        items = [
            PsuRankingListItem(
                id="psu-1",
                name="1st Player NGDP 1000W",
                sku="1st-player-ngdp-1000w",
                brand="1st Player",
                wattage_w=1000,
                form_factor="ATX",
                atx_version="ATX3.0",
                efficiency_rating="PLATINUM",
                noise_rating="Standard++",
                ranking=PsuRanking(game_score=87.0974, game_percentile=100.0, performance_tier="S"),
            )
        ]
        return PsuRankingListResponse(items=items, page=1, limit=10, total=1)

def test_list_psus() -> None:
    app.dependency_overrides[get_psu_repository] = FakePsuRepository
    client = TestClient(app)
    response = client.get("/psus?page=1&limit=1")
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["sku"] == "1st-player-ngdp-1000w"

def test_list_psu_rankings() -> None:
    app.dependency_overrides[get_psu_repository] = FakePsuRepository
    client = TestClient(app)
    response = client.get("/psus/rankings")
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["total"] == 1
