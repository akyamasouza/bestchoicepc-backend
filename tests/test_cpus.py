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
)


class FakeCpuRepository:
    def list_cpus(self) -> list[CpuListItem]:
        return [
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
            CpuRankingListItem(
                id="cpu-3",
                name="Intel Core i7-14700K",
                sku="BX8071514700K",
                brand="Intel",
                release_year=2024,
                ranking=CpuRanking(
                    game_score=4300,
                    game_percentile=88.0,
                    performance_tier="B",
                ),
            ),
        ]

        if brand is not None:
            items = [item for item in items if item.brand.lower() == brand.lower()]
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
        return CpuRankingListResponse(
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


def test_list_cpus() -> None:
    app.dependency_overrides[get_cpu_repository] = FakeCpuRepository
    client = TestClient(app)

    response = client.get("/cpus")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "cpu-1",
            "name": "AMD Ryzen 7 7800X3D",
            "sku": "100-000000910",
            "socket": "AM5",
            "cores": 8,
            "threads": 16,
            "benchmark": {
                "multithread_rating": 34321,
                "single_thread_rating": 4012,
                "techpowerup_relative_performance_applications": 85.1,
                "samples": 4200,
                "margin_for_error": "Low",
            },
            "ranking": {
                "game_score": 4012.0,
                "game_percentile": 95.4,
                "performance_tier": "S",
            },
        },
        {
            "id": "cpu-2",
            "name": "AMD Ryzen 9 9950X",
            "sku": "100-100001277WOF",
            "socket": "AM5",
            "cores": 16,
            "threads": 32,
            "benchmark": {
                "multithread_rating": 65809,
                "single_thread_rating": 4729,
                "techpowerup_relative_performance_applications": 125.1,
                "samples": 5519,
                "margin_for_error": "Low",
            },
            "ranking": {
                "game_score": 4729.0,
                "game_percentile": 100.0,
                "performance_tier": "S",
            },
        },
    ]


def test_list_cpu_rankings_with_filters() -> None:
    app.dependency_overrides[get_cpu_repository] = FakeCpuRepository
    client = TestClient(app)

    response = client.get(
        "/cpus/rankings?sort=asc&brand=amd&release_year=2024&performance_tier=s&q=9950&page=1&limit=5"
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": "cpu-2",
                "name": "AMD Ryzen 9 9950X",
                "sku": "100-100001277WOF",
                "brand": "AMD",
                "release_year": 2024,
                "ranking": {
                    "game_score": 4729.0,
                    "game_percentile": 100.0,
                    "performance_tier": "S",
                },
            }
        ],
        "page": 1,
        "limit": 5,
        "total": 1,
    }


def test_cpu_repository_maps_documents() -> None:
    from app.repositories.cpu_repository import CpuRepository

    repository = CpuRepository(
        FakeCollection(
            [
                {
                    "_id": 2,
                    "name": "AMD Ryzen 9 9950X",
                    "sku": "100-100001277WOF",
                    "first_seen": "Q3 2024",
                    "socket": "AM5",
                    "cores": 16,
                    "threads": 32,
                    "benchmark": {
                        "multithread_rating": 65809,
                        "single_thread_rating": 4729,
                        "techpowerup_relative_performance_applications": 125.1,
                        "samples": 5519,
                        "margin_for_error": "Low",
                    },
                    "ranking": {
                        "game_score": 4729,
                        "game_percentile": 100.0,
                        "performance_tier": "S",
                    },
                },
                {
                    "_id": 1,
                    "name": "AMD Ryzen 7 7800X3D",
                    "sku": "100-000000910",
                    "first_seen": "Q2 2023",
                    "socket": "AM5",
                    "cores": 8,
                    "threads": 16,
                    "benchmark": {
                        "multithread_rating": 34321,
                        "single_thread_rating": 4012,
                        "techpowerup_relative_performance_applications": 85.1,
                        "samples": 4200,
                        "margin_for_error": "Low",
                    },
                    "ranking": {
                        "game_score": 4012,
                        "game_percentile": 95.4,
                        "performance_tier": "S",
                    },
                },
            ]
        )
    )

    result = repository.list_cpus()

    assert [cpu.id for cpu in result] == ["1", "2"]
    assert [cpu.name for cpu in result] == [
        "AMD Ryzen 7 7800X3D",
        "AMD Ryzen 9 9950X",
    ]
    assert result[0].benchmark is not None
    assert result[0].benchmark.multithread_rating == 34321
    assert result[0].benchmark.techpowerup_relative_performance_applications == 85.1
    assert result[0].ranking is not None
    assert result[0].ranking.performance_tier == "S"


def test_cpu_repository_lists_rankings_with_sort_and_filters() -> None:
    from app.repositories.cpu_repository import CpuRepository

    repository = CpuRepository(
        FakeCollection(
            [
                {
                    "_id": 1,
                    "name": "AMD Ryzen 7 7800X3D",
                    "sku": "100-000000910",
                    "first_seen": "Q2 2023",
                    "ranking": {
                        "game_score": 4012,
                        "game_percentile": 95.4,
                        "performance_tier": "S",
                    },
                },
                {
                    "_id": 2,
                    "name": "AMD Ryzen 9 9950X",
                    "sku": "100-100001277WOF",
                    "first_seen": "Q3 2024",
                    "ranking": {
                        "game_score": 4729,
                        "game_percentile": 100.0,
                        "performance_tier": "S",
                    },
                },
                {
                    "_id": 3,
                    "name": "Intel Core i7-14700K",
                    "sku": "BX8071514700K",
                    "first_seen": "Q4 2024",
                    "ranking": {
                        "game_score": 4300,
                        "game_percentile": 88.0,
                        "performance_tier": "B",
                    },
                },
            ]
        )
    )

    result = repository.list_rankings(
        sort="asc",
        brand="AMD",
        release_year=2024,
        performance_tier="s",
        q="9950",
        page=1,
        limit=10,
    )

    assert [(cpu.name, cpu.brand, cpu.release_year) for cpu in result.items] == [
        ("AMD Ryzen 9 9950X", "AMD", 2024),
    ]
    assert result.page == 1
    assert result.limit == 10
    assert result.total == 1
    assert result.items[0].sku == "100-100001277WOF"
    assert result.items[0].ranking is not None
    assert result.items[0].ranking.game_percentile == 100.0


def test_cpu_repository_lists_match_candidates_and_can_filter_by_owned_sku() -> None:
    from app.repositories.cpu_repository import CpuRepository

    repository = CpuRepository(
        FakeCollection(
            [
                {
                    "_id": 1,
                    "name": "AMD Ryzen 7 7800X3D",
                    "sku": "100-000000910",
                    "ranking": {
                        "game_score": 4012,
                        "game_percentile": 95.4,
                        "performance_tier": "S",
                    },
                },
                {
                    "_id": 2,
                    "name": "CPU Sem Ranking",
                    "sku": "cpu-sem-ranking",
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
    owned_candidates = repository.list_match_candidates(sku="cpu-sem-ranking")

    assert [cpu.sku for cpu in all_candidates] == ["100-000000910"]
    assert [cpu.sku for cpu in owned_candidates] == ["cpu-sem-ranking"]
