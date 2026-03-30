from collections.abc import Iterable, Iterator
import re
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
    def list_ssds(
        self,
        *,
        page: int = 1,
        limit: int = 20,
    ) -> SsdListResponse:
        items = [
            SsdListItem(
                id="ssd-1",
                name="Western Digital WD_BLACK SN8100 2TB",
                sku="WDS200T1X0M-00CMT0",
                brand="Western Digital",
                capacity_gb=2048,
                interface="PCIe 5.0 x4",
                nand="TLC",
                dram=True,
                benchmark=SsdBenchmark(
                    ssd_tester_score=13183,
                ),
                ranking=SsdRanking(
                    game_score=13183.0,
                    game_percentile=100.0,
                    performance_tier="S",
                ),
            ),
            SsdListItem(
                id="ssd-2",
                name="Samsung 9100 PRO 1TB",
                sku="MZ-VAP1T0BW",
                brand="Samsung",
                capacity_gb=1024,
                interface="PCIe 5.0 x4",
                nand="TLC",
                dram=True,
                benchmark=SsdBenchmark(
                    ssd_tester_score=12554,
                ),
                ranking=SsdRanking(
                    game_score=12554.0,
                    game_percentile=95.23,
                    performance_tier="S",
                ),
            ),
        ]
        start = (page - 1) * limit
        return SsdListResponse(
            items=items[start : start + limit],
            page=page,
            limit=limit,
            total=len(items),
        )

    def list_rankings(
        self,
        *,
        sort: str = "desc",
        brand: str | None = None,
        capacity_gb: int | None = None,
        interface: str | None = None,
        performance_tier: str | None = None,
        q: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> SsdRankingListResponse:
        items = [
            SsdRankingListItem(
                id="ssd-1",
                name="Western Digital WD_BLACK SN8100 2TB",
                sku="WDS200T1X0M-00CMT0",
                brand="Western Digital",
                capacity_gb=2048,
                interface="PCIe 5.0 x4",
                ranking=SsdRanking(
                    game_score=13183.0,
                    game_percentile=100.0,
                    performance_tier="S",
                ),
            ),
            SsdRankingListItem(
                id="ssd-2",
                name="Samsung 9100 PRO 1TB",
                sku="MZ-VAP1T0BW",
                brand="Samsung",
                capacity_gb=1024,
                interface="PCIe 5.0 x4",
                ranking=SsdRanking(
                    game_score=12554.0,
                    game_percentile=95.23,
                    performance_tier="S",
                ),
            ),
            SsdRankingListItem(
                id="ssd-3",
                name="Kingston NV3 1TB",
                sku="SNV3S-1000G",
                brand="Kingston",
                capacity_gb=1024,
                interface="PCIe 4.0 x4",
                ranking=SsdRanking(
                    game_score=8200.0,
                    game_percentile=62.2,
                    performance_tier="C",
                ),
            ),
        ]

        if brand is not None:
            items = [item for item in items if item.brand.lower() == brand.lower()]
        if capacity_gb is not None:
            items = [item for item in items if item.capacity_gb == capacity_gb]
        if interface is not None:
            items = [item for item in items if item.interface is not None and item.interface.lower() == interface.lower()]
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
        return SsdRankingListResponse(
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


def test_list_ssds() -> None:
    app.dependency_overrides[get_ssd_repository] = FakeSsdRepository
    client = TestClient(app)

    response = client.get("/ssds?page=1&limit=1")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": "ssd-1",
                "name": "Western Digital WD_BLACK SN8100 2TB",
                "sku": "WDS200T1X0M-00CMT0",
                "brand": "Western Digital",
                "capacity_gb": 2048,
                "interface": "PCIe 5.0 x4",
                "nand": "TLC",
                "dram": True,
                "benchmark": {
                    "ssd_tester_score": 13183,
                },
                "ranking": {
                    "game_score": 13183.0,
                    "game_percentile": 100.0,
                    "performance_tier": "S",
                },
            }
        ],
        "page": 1,
        "limit": 1,
        "total": 2,
    }


def test_list_ssd_rankings_with_filters() -> None:
    app.dependency_overrides[get_ssd_repository] = FakeSsdRepository
    client = TestClient(app)

    response = client.get(
        "/ssds/rankings?sort=desc&brand=samsung&capacity_gb=1024&interface=pcie%205.0%20x4&performance_tier=s&q=9100&page=1&limit=5"
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": "ssd-2",
                "name": "Samsung 9100 PRO 1TB",
                "sku": "MZ-VAP1T0BW",
                "brand": "Samsung",
                "capacity_gb": 1024,
                "interface": "PCIe 5.0 x4",
                "ranking": {
                    "game_score": 12554.0,
                    "game_percentile": 95.23,
                    "performance_tier": "S",
                },
            }
        ],
        "page": 1,
        "limit": 5,
        "total": 1,
    }


def test_ssd_repository_maps_documents() -> None:
    from app.repositories.ssd_repository import SsdRepository

    repository = SsdRepository(
        FakeCollection(
            [
                {
                    "_id": 1,
                    "name": "Western Digital WD_BLACK SN8100 2TB",
                    "sku": "WDS200T1X0M-00CMT0",
                    "brand": "Western Digital",
                    "capacity_gb": 2048,
                    "interface": "PCIe 5.0 x4",
                    "nand": "TLC",
                    "dram": True,
                    "benchmark": {
                        "ssd_tester_score": 13183,
                    },
                    "ranking": {
                        "game_score": 13183.0,
                        "game_percentile": 100.0,
                        "performance_tier": "S",
                    },
                }
            ]
        )
    )

    result = repository.list_ssds(page=1, limit=10)

    assert [ssd.id for ssd in result.items] == ["1"]
    assert [ssd.name for ssd in result.items] == ["Western Digital WD_BLACK SN8100 2TB"]
    assert result.page == 1
    assert result.limit == 10
    assert result.total == 1
    assert result.items[0].benchmark is not None
    assert result.items[0].benchmark.ssd_tester_score == 13183
    assert result.items[0].ranking is not None
    assert result.items[0].ranking.performance_tier == "S"


def test_ssd_repository_lists_rankings_with_sort_and_filters() -> None:
    from app.repositories.ssd_repository import SsdRepository

    repository = SsdRepository(
        FakeCollection(
            [
                {
                    "_id": 1,
                    "name": "Western Digital WD_BLACK SN8100 2TB",
                    "sku": "WDS200T1X0M-00CMT0",
                    "brand": "Western Digital",
                    "capacity_gb": 2048,
                    "interface": "PCIe 5.0 x4",
                    "ranking": {
                        "game_score": 13183.0,
                        "game_percentile": 100.0,
                        "performance_tier": "S",
                    },
                },
                {
                    "_id": 2,
                    "name": "Samsung 9100 PRO 1TB",
                    "sku": "MZ-VAP1T0BW",
                    "brand": "Samsung",
                    "capacity_gb": 1024,
                    "interface": "PCIe 5.0 x4",
                    "ranking": {
                        "game_score": 12554.0,
                        "game_percentile": 95.23,
                        "performance_tier": "S",
                    },
                },
                {
                    "_id": 3,
                    "name": "Kingston NV3 1TB",
                    "sku": "SNV3S-1000G",
                    "brand": "Kingston",
                    "capacity_gb": 1024,
                    "interface": "PCIe 4.0 x4",
                    "ranking": {
                        "game_score": 8200.0,
                        "game_percentile": 62.2,
                        "performance_tier": "C",
                    },
                },
            ]
        )
    )

    result = repository.list_rankings(
        sort="desc",
        brand="Samsung",
        capacity_gb=1024,
        interface="PCIe 5.0 x4",
        performance_tier="s",
        q="9100",
        page=1,
        limit=10,
    )

    assert [(ssd.name, ssd.brand, ssd.capacity_gb) for ssd in result.items] == [
        ("Samsung 9100 PRO 1TB", "Samsung", 1024),
    ]
    assert result.page == 1
    assert result.limit == 10
    assert result.total == 1
    assert result.items[0].sku == "MZ-VAP1T0BW"
    assert result.items[0].ranking is not None
    assert result.items[0].ranking.game_percentile == 95.23
