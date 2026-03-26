from collections.abc import Iterable, Iterator
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
)


class FakeGpuRepository:
    def list_gpus(self) -> list[GpuListItem]:
        return [
            GpuListItem(
                id="gpu-1",
                name="GeForce RTX 5090",
                sku="geforce-rtx-5090",
                bus_interface="PCIe 5.0 x16",
                memory_size_mb=32768,
                core_clock_mhz=2017,
                memory_clock_mhz=1750,
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
            )
        ]

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
                category="Desktop",
                release_year=2025,
                ranking=GpuRanking(
                    game_score=38975,
                    game_percentile=100.0,
                    performance_tier="S",
                ),
            ),
            GpuRankingListItem(
                id="gpu-2",
                name="Radeon RX 7900 XTX",
                sku="radeon-rx-7900-xtx",
                brand="AMD",
                category="Desktop",
                release_year=2022,
                ranking=GpuRanking(
                    game_score=31393,
                    game_percentile=84.0,
                    performance_tier="B",
                ),
            ),
            GpuRankingListItem(
                id="gpu-3",
                name="Intel Arc B580",
                sku="intel-arc-b580",
                brand="Intel",
                category="Desktop",
                release_year=2024,
                ranking=GpuRanking(
                    game_score=15906,
                    game_percentile=42.0,
                    performance_tier="D",
                ),
            ),
        ]

        if brand is not None:
            items = [item for item in items if item.brand is not None and item.brand.lower() == brand.lower()]
        if category is not None:
            items = [
                item
                for item in items
                if item.category is not None and item.category.lower() == category.lower()
            ]
        if release_year is not None:
            items = [item for item in items if item.release_year == release_year]
        if performance_tier is not None:
            items = [
                item
                for item in items
                if item.ranking is not None and item.ranking.performance_tier == performance_tier.upper()
            ]
        if q is not None and q.strip():
            normalized_query = q.strip().lower()
            items = [
                item
                for item in items
                if normalized_query in item.name.lower() or normalized_query in item.sku.lower()
            ]
        if sort == "asc":
            items = sorted(items, key=lambda item: item.ranking.game_percentile if item.ranking else 0.0)
        else:
            items = sorted(items, key=lambda item: item.ranking.game_percentile if item.ranking else 0.0, reverse=True)

        total = len(items)
        start = (page - 1) * limit
        return GpuRankingListResponse(
            items=items[start : start + limit],
            page=page,
            limit=limit,
            total=total,
        )


class FakeCursor(Iterable[dict[str, Any]]):
    def __init__(self, documents: list[dict[str, Any]]):
        self.documents = documents

    def sort(self, field: str, direction: int) -> "FakeCursor":
        reverse = direction == -1
        self.documents = sorted(
            self.documents,
            key=lambda document: document.get(field, ""),
            reverse=reverse,
        )
        return self

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(self.documents)


class FakeCollection:
    def __init__(self, documents: list[dict[str, Any]]):
        self.documents = documents

    def find(self, *_args: Any, **_kwargs: Any) -> FakeCursor:
        return FakeCursor(self.documents)


def test_list_gpus() -> None:
    app.dependency_overrides[get_gpu_repository] = FakeGpuRepository
    client = TestClient(app)

    response = client.get("/gpus")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "gpu-1",
            "name": "GeForce RTX 5090",
            "sku": "geforce-rtx-5090",
            "bus_interface": "PCIe 5.0 x16",
            "memory_size_mb": 32768,
            "core_clock_mhz": 2017,
            "memory_clock_mhz": 1750,
            "max_tdp_w": 575,
            "category": "Desktop",
            "benchmark": {
                "g3d_mark": 38975,
                "g2d_mark": 1413,
                "tomshardware_relative_performance_1080p_medium": 100.0,
                "samples": 8123,
            },
            "ranking": {
                "game_score": 38975.0,
                "game_percentile": 100.0,
                "performance_tier": "S",
            },
        }
    ]


def test_list_gpu_rankings_with_filters() -> None:
    app.dependency_overrides[get_gpu_repository] = FakeGpuRepository
    client = TestClient(app)

    response = client.get(
        "/gpus/rankings?sort=desc&brand=nvidia&category=desktop&release_year=2025&performance_tier=s&q=5090&page=1&limit=5"
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": "gpu-1",
                "name": "GeForce RTX 5090",
                "sku": "geforce-rtx-5090",
                "brand": "NVIDIA",
                "category": "Desktop",
                "release_year": 2025,
                "ranking": {
                    "game_score": 38975.0,
                    "game_percentile": 100.0,
                    "performance_tier": "S",
                },
            }
        ],
        "page": 1,
        "limit": 5,
        "total": 1,
    }


def test_gpu_repository_maps_documents() -> None:
    from app.repositories.gpu_repository import GpuRepository

    repository = GpuRepository(
        FakeCollection(
            [
                {
                    "_id": 1,
                    "name": "GeForce RTX 5090",
                    "sku": "geforce-rtx-5090",
                    "brand": "NVIDIA",
                    "bus_interface": "PCIe 5.0 x16",
                    "memory_size_mb": 32768,
                    "core_clock_mhz": 2017,
                    "memory_clock_mhz": 1750,
                    "max_tdp_w": 575,
                    "category": "Desktop",
                    "benchmark": {
                        "g3d_mark": 38975,
                        "g2d_mark": 1413,
                        "tomshardware_relative_performance_1080p_medium": 100.0,
                        "samples": 8123,
                    },
                    "first_benchmarked": "2025-01-31",
                    "ranking": {
                        "game_score": 38975,
                        "game_percentile": 100.0,
                        "performance_tier": "S",
                    },
                }
            ]
        )
    )

    result = repository.list_gpus()

    assert [gpu.id for gpu in result] == ["1"]
    assert [gpu.name for gpu in result] == ["GeForce RTX 5090"]
    assert result[0].benchmark is not None
    assert result[0].benchmark.g3d_mark == 38975
    assert result[0].benchmark.tomshardware_relative_performance_1080p_medium == 100.0
    assert result[0].ranking is not None
    assert result[0].ranking.performance_tier == "S"


def test_gpu_repository_lists_rankings_with_sort_and_filters() -> None:
    from app.repositories.gpu_repository import GpuRepository

    repository = GpuRepository(
        FakeCollection(
            [
                {
                    "_id": 1,
                    "name": "GeForce RTX 5090",
                    "sku": "geforce-rtx-5090",
                    "brand": "NVIDIA",
                    "category": "Desktop",
                    "first_benchmarked": "2025-01-31",
                    "ranking": {
                        "game_score": 38975,
                        "game_percentile": 100.0,
                        "performance_tier": "S",
                    },
                },
                {
                    "_id": 2,
                    "name": "Radeon RX 7900 XTX",
                    "sku": "radeon-rx-7900-xtx",
                    "brand": "AMD",
                    "category": "Desktop",
                    "first_benchmarked": "2022-12-18",
                    "ranking": {
                        "game_score": 31393,
                        "game_percentile": 84.0,
                        "performance_tier": "B",
                    },
                },
                {
                    "_id": 3,
                    "name": "Intel Arc B580",
                    "sku": "intel-arc-b580",
                    "brand": "Intel",
                    "category": "Desktop",
                    "first_benchmarked": "2024-12-14",
                    "ranking": {
                        "game_score": 15906,
                        "game_percentile": 42.0,
                        "performance_tier": "D",
                    },
                },
            ]
        )
    )

    result = repository.list_rankings(
        sort="desc",
        brand="NVIDIA",
        category="Desktop",
        release_year=2025,
        performance_tier="s",
        q="5090",
        page=1,
        limit=10,
    )

    assert [(gpu.name, gpu.brand, gpu.release_year) for gpu in result.items] == [
        ("GeForce RTX 5090", "NVIDIA", 2025),
    ]
    assert result.page == 1
    assert result.limit == 10
    assert result.total == 1
    assert result.items[0].sku == "geforce-rtx-5090"
    assert result.items[0].ranking is not None
    assert result.items[0].ranking.game_percentile == 100.0
