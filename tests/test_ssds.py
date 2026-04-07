from typing import Any
from fastapi.testclient import TestClient
from app.main import app
from app.routes.ssds import get_ssd_repository
from app.schemas.ssd import (
    SsdBenchmark,
    SsdListItem,
    SsdListResponse,
    SsdRanking,
    SsdRankingListItem,
    SsdRankingListResponse,
)

class FakeSsdRepository:
    def list_ssds(self, *, page: int = 1, limit: int = 20) -> SsdListResponse:
        items = [
            SsdListItem(
                id="ssd-1",
                name="Western Digital WD_BLACK SN850X 2TB",
                sku="WDS200T2X0E",
                brand="Western Digital",
                capacity_gb=2048,
                interface="PCIe 4.0 x4",
                nand="TLC",
                dram=True,
                benchmark=SsdBenchmark(ssd_tester_score=13183),
                ranking=SsdRanking(game_score=13183.0, game_percentile=100.0, performance_tier="S"),
            )
        ]
        return SsdListResponse(items=items, page=page, limit=limit, total=1)

    def list_rankings(self, **_kwargs) -> SsdRankingListResponse:
        items = [
            SsdRankingListItem(
                id="ssd-1",
                name="Western Digital WD_BLACK SN850X 2TB",
                sku="WDS200T2X0E",
                brand="Western Digital",
                capacity_gb=2048,
                interface="PCIe 4.0 x4",
                ranking=SsdRanking(game_score=13183.0, game_percentile=100.0, performance_tier="S"),
            )
        ]
        return SsdRankingListResponse(items=items, page=1, limit=10, total=1)

def test_list_ssds() -> None:
    app.dependency_overrides[get_ssd_repository] = FakeSsdRepository
    client = TestClient(app)
    response = client.get("/ssds")
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["sku"] == "WDS200T2X0E"

def test_list_ssd_rankings() -> None:
    app.dependency_overrides[get_ssd_repository] = FakeSsdRepository
    client = TestClient(app)
    response = client.get("/ssds/rankings")
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["total"] == 1
