from collections.abc import Iterable, Iterator
import re
from typing import Any

from fastapi.testclient import TestClient

from app.main import app
from app.routes.cpus import get_cpu_repository
from app.schemas.cpu import (
    CpuBenchmark,
    CpuListItem,
    CpuRanking,
    CpuRankingListItem,
    CpuRankingListResponse,
    CpuListResponse,
)


class FakeCpuRepository:
    def list_cpus(self, *, brand=None, socket=None, q=None, page=1, limit=20) -> CpuListResponse:
        items = [
            CpuListItem(
                id="cpu-1",
                name="AMD Ryzen 7 7800X3D",
                sku="100-000000910",
                socket="AM5",
                cores=8,
                threads=16,
                benchmark=CpuBenchmark(
                    multithread_rating=34321,
                    single_thread_rating=4012,
                    techpowerup_relative_performance_applications=85.1,
                    samples=4200,
                    margin_for_error="Low",
                ),
                ranking=CpuRanking(
                    game_score=4012,
                    game_percentile=95.4,
                    performance_tier="S",
                ),
            ),
            CpuListItem(
                id="cpu-2",
                name="AMD Ryzen 9 9950X",
                sku="100-100001277WOF",
                socket="AM5",
                cores=16,
                threads=32,
                benchmark=CpuBenchmark(
                    multithread_rating=65809,
                    single_thread_rating=4729,
                    techpowerup_relative_performance_applications=125.1,
                    samples=5519,
                    margin_for_error="Low",
                ),
                ranking=CpuRanking(
                    game_score=4729,
                    game_percentile=100.0,
                    performance_tier="S",
                ),
            ),
        ]
        return CpuListResponse(items=items, page=1, limit=20, total=2)

    def list_rankings(
        self,
        *,
        sort: str = "desc",
        brand: str | None = None,
        release_year: int | None = None,
        performance_tier: str | None = None,
        q: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> CpuRankingListResponse:
        items = [
            CpuRankingListItem(
                id="cpu-2",
                name="AMD Ryzen 9 9950X",
                sku="100-100001277WOF",
                brand="AMD",
                release_year=2024,
                ranking=CpuRanking(
                    game_score=4729,
                    game_percentile=100.0,
                    performance_tier="S",
                ),
            ),
            CpuRankingListItem(
                id="cpu-1",
                name="AMD Ryzen 7 7800X3D",
                sku="100-000000910",
                brand="AMD",
                release_year=2023,
                ranking=CpuRanking(
                    game_score=4012,
                    game_percentile=95.4,
                    performance_tier="S",
                ),
            ),
        ]
        total = len(items)
        return CpuRankingListResponse(
            items=items,
            page=page,
            limit=limit,
            total=total,
        )


def test_list_cpus() -> None:
    app.dependency_overrides[get_cpu_repository] = FakeCpuRepository
    client = TestClient(app)
    response = client.get("/cpus")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["id"] == "cpu-1"


def test_list_cpu_rankings() -> None:
    app.dependency_overrides[get_cpu_repository] = FakeCpuRepository
    client = TestClient(app)
    response = client.get("/cpus/rankings")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert data["items"][0]["id"] == "cpu-2"
