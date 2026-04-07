from collections.abc import Iterable, Iterator
import re
from typing import Any

from fastapi.testclient import TestClient

from app.main import app
from app.routes.gpus import get_gpu_repository
from app.schemas.gpu import (
    GpuBenchmark,
    GpuListItem,
    GpuRanking,
    GpuRankingListItem,
    GpuRankingListResponse,
    GpuListResponse,
)


class FakeGpuRepository:
    def list_gpus(self, *, brand=None, category=None, q=None, page=1, limit=20) -> GpuListResponse:
        items = [
            GpuListItem(
                id="gpu-1",
                name="GeForce RTX 5090",
                sku="geforce-rtx-5090",
                bus_interface="PCIe 5.0 x16",
                memory_size_mb=32768,
                max_tdp_w=575,
                category="Desktop",
                benchmark=GpuBenchmark(
                    g3d_mark=38975,
                    g2d_mark=1413,
                    tomshardware_relative_performance_1080p_medium=100.0,
                    samples=8123,
                ),
                ranking=GpuRanking(
                    game_score=38975,
                    game_percentile=100.0,
                    performance_tier="S",
                ),
            ),
        ]
        return GpuListResponse(items=items, page=1, limit=20, total=1)

    def list_rankings(
        self,
        *,
        sort: str = "desc",
        brand: str | None = None,
        category: str | None = None,
        release_year: int | None = None,
        performance_tier: str | None = None,
        q: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> GpuRankingListResponse:
        items = [
            GpuRankingListItem(
                id="gpu-1",
                name="GeForce RTX 5090",
                sku="geforce-rtx-5090",
                brand="NVIDIA",
                release_year=2025,
                ranking=GpuRanking(
                    game_score=38975,
                    game_percentile=100.0,
                    performance_tier="S",
                ),
            ),
        ]
        return GpuRankingListResponse(
            items=items,
            page=page,
            limit=limit,
            total=1,
        )


def test_list_gpus() -> None:
    app.dependency_overrides[get_gpu_repository] = FakeGpuRepository
    client = TestClient(app)
    response = client.get("/gpus")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == "gpu-1"


def test_list_gpu_rankings() -> None:
    app.dependency_overrides[get_gpu_repository] = FakeGpuRepository
    client = TestClient(app)
    response = client.get("/gpus/rankings")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == "gpu-1"
