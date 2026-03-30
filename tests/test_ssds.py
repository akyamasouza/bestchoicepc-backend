from collections.abc import Iterable, Iterator
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
