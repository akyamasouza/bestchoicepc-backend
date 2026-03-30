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

    def sort(self, field_or_fields, direction: int | None = None) -> "FakeCursor":
        if isinstance(field_or_fields, list):
            for field, sort_direction in reversed(field_or_fields):
                reverse = sort_direction == -1
                self.documents = sorted(
                    self.documents,
                    key=lambda document: _get_nested_value(document, field),
                    reverse=reverse,
                )
            return self

        reverse = direction == -1
        self.documents = sorted(
            self.documents,
            key=lambda document: _get_nested_value(document, field_or_fields),
            reverse=reverse,
        )
        return self

    def skip(self, value: int) -> "FakeCursor":
        self.documents = self.documents[value:]
        return self

    def limit(self, value: int) -> "FakeCursor":
        self.documents = self.documents[:value]
        return self

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(self.documents)


class FakeCollection:
    def __init__(self, documents: list[dict[str, Any]]):
        self.documents = documents

    def find(self, query: dict[str, Any] | None = None, projection: dict[str, Any] | None = None) -> FakeCursor:
        filtered = [document for document in self.documents if _matches_query(document, query or {})]
        projected = [_apply_projection(document, projection) for document in filtered]
        return FakeCursor(projected)

    def count_documents(self, query: dict[str, Any]) -> int:
        return sum(1 for document in self.documents if _matches_query(document, query))


def _matches_query(document: dict[str, Any], query: dict[str, Any]) -> bool:
    for key, expected in query.items():
        if key == "$or":
            if not any(_matches_query(document, clause) for clause in expected):
                return False
            continue

        actual = _get_nested_value(document, key)
        if isinstance(expected, dict) and "$regex" in expected:
            pattern = expected["$regex"]
            flags = re.IGNORECASE if "i" in expected.get("$options", "") else 0
            if actual is None or re.search(pattern, str(actual), flags) is None:
                return False
            continue

        if isinstance(expected, dict) and "$ne" in expected:
            if actual == expected["$ne"]:
                return False
            continue

        if actual != expected:
            return False

    return True


def _apply_projection(document: dict[str, Any], projection: dict[str, Any] | None) -> dict[str, Any]:
    if projection is None:
        return dict(document)

    projected = {"_id": document.get("_id")}
    for key, enabled in projection.items():
        if not enabled or key == "_id":
            continue

        value = _get_nested_value(document, key)
        if value is not None:
            _set_nested_value(projected, key, value)

    return projected


def _get_nested_value(document: dict[str, Any], path: str) -> Any:
    current: Any = document
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _set_nested_value(document: dict[str, Any], path: str, value: Any) -> None:
    current = document
    parts = path.split(".")
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = value


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


def test_gpu_repository_lists_match_candidates_and_can_filter_by_owned_sku() -> None:
    from app.repositories.gpu_repository import GpuRepository

    repository = GpuRepository(
        FakeCollection(
            [
                {
                    "_id": 1,
                    "name": "GeForce RTX 5090",
                    "sku": "geforce-rtx-5090",
                    "memory_size_mb": 32768,
                    "ranking": {
                        "game_score": 38975,
                        "game_percentile": 100.0,
                        "performance_tier": "S",
                    },
                },
                {
                    "_id": 2,
                    "name": "GPU Sem Ranking",
                    "sku": "gpu-sem-ranking",
                    "memory_size_mb": 8192,
                    "ranking": {
                        "game_score": None,
                        "game_percentile": None,
                        "performance_tier": None,
                    },
                },
            ]
        )
    )

    all_candidates = repository.list_match_candidates()
    owned_candidates = repository.list_match_candidates(sku="gpu-sem-ranking")

    assert [gpu.sku for gpu in all_candidates] == ["geforce-rtx-5090"]
    assert [gpu.sku for gpu in owned_candidates] == ["gpu-sem-ranking"]
