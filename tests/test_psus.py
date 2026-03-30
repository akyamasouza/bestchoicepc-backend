from collections.abc import Iterable, Iterator
import re
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
    def list_psus(
        self,
        *,
        page: int = 1,
        limit: int = 20,
    ) -> PsuListResponse:
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
                benchmark=PsuBenchmark(
                    cybenetics_score=87.0974,
                ),
                ranking=PsuRanking(
                    game_score=87.0974,
                    game_percentile=100.0,
                    performance_tier="S",
                ),
            ),
            PsuListItem(
                id="psu-2",
                name="1st Player ACK 750W Gold",
                sku="1st-player-ack-750w-gold",
                brand="1st Player",
                wattage_w=750,
                form_factor="ATX",
                atx_version="ATX",
                efficiency_rating="GOLD",
                noise_rating="Standard+",
                benchmark=PsuBenchmark(
                    cybenetics_score=82.5645,
                ),
                ranking=PsuRanking(
                    game_score=82.5645,
                    game_percentile=94.8,
                    performance_tier="S",
                ),
            ),
        ]
        start = (page - 1) * limit
        return PsuListResponse(
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
        wattage_w: int | None = None,
        form_factor: str | None = None,
        atx_version: str | None = None,
        performance_tier: str | None = None,
        q: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> PsuRankingListResponse:
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
                ranking=PsuRanking(
                    game_score=87.0974,
                    game_percentile=100.0,
                    performance_tier="S",
                ),
            ),
            PsuRankingListItem(
                id="psu-2",
                name="1st Player ACK 750W Gold",
                sku="1st-player-ack-750w-gold",
                brand="1st Player",
                wattage_w=750,
                form_factor="ATX",
                atx_version="ATX",
                efficiency_rating="GOLD",
                noise_rating="Standard+",
                ranking=PsuRanking(
                    game_score=82.5645,
                    game_percentile=94.8,
                    performance_tier="S",
                ),
            ),
            PsuRankingListItem(
                id="psu-3",
                name="Quiet PSU 650W",
                sku="quiet-psu-650w",
                brand="Quiet",
                wattage_w=650,
                form_factor="SFX",
                atx_version="ATX3.1",
                efficiency_rating="GOLD",
                noise_rating="A",
                ranking=PsuRanking(
                    game_score=61.5,
                    game_percentile=70.61,
                    performance_tier="B",
                ),
            ),
        ]

        if brand is not None:
            items = [item for item in items if item.brand.lower() == brand.lower()]
        if wattage_w is not None:
            items = [item for item in items if item.wattage_w == wattage_w]
        if form_factor is not None:
            items = [item for item in items if item.form_factor is not None and item.form_factor.lower() == form_factor.lower()]
        if atx_version is not None:
            items = [item for item in items if item.atx_version is not None and item.atx_version.lower() == atx_version.lower()]
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
        return PsuRankingListResponse(
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


def test_list_psus() -> None:
    app.dependency_overrides[get_psu_repository] = FakePsuRepository
    client = TestClient(app)

    response = client.get("/psus?page=1&limit=1")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": "psu-1",
                "name": "1st Player NGDP 1000W",
                "sku": "1st-player-ngdp-1000w",
                "brand": "1st Player",
                "wattage_w": 1000,
                "form_factor": "ATX",
                "atx_version": "ATX3.0",
                "efficiency_rating": "PLATINUM",
                "noise_rating": "Standard++",
                "benchmark": {
                    "cybenetics_score": 87.0974,
                },
                "ranking": {
                    "game_score": 87.0974,
                    "game_percentile": 100.0,
                    "performance_tier": "S",
                },
            }
        ],
        "page": 1,
        "limit": 1,
        "total": 2,
    }


def test_list_psu_rankings_with_filters() -> None:
    app.dependency_overrides[get_psu_repository] = FakePsuRepository
    client = TestClient(app)

    response = client.get(
        "/psus/rankings?sort=desc&brand=1st%20Player&wattage_w=1000&form_factor=atx&atx_version=atx3.0&performance_tier=s&q=ngdp&page=1&limit=5"
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": "psu-1",
                "name": "1st Player NGDP 1000W",
                "sku": "1st-player-ngdp-1000w",
                "brand": "1st Player",
                "wattage_w": 1000,
                "form_factor": "ATX",
                "atx_version": "ATX3.0",
                "efficiency_rating": "PLATINUM",
                "noise_rating": "Standard++",
                "ranking": {
                    "game_score": 87.0974,
                    "game_percentile": 100.0,
                    "performance_tier": "S",
                },
            }
        ],
        "page": 1,
        "limit": 5,
        "total": 1,
    }


def test_psu_repository_maps_documents() -> None:
    from app.repositories.psu_repository import PsuRepository

    repository = PsuRepository(
        FakeCollection(
            [
                {
                    "_id": 1,
                    "name": "1st Player NGDP 1000W",
                    "sku": "1st-player-ngdp-1000w",
                    "brand": "1st Player",
                    "wattage_w": 1000,
                    "form_factor": "ATX",
                    "atx_version": "ATX3.0",
                    "efficiency_rating": "PLATINUM",
                    "noise_rating": "Standard++",
                    "benchmark": {
                        "cybenetics_score": 87.0974,
                    },
                    "ranking": {
                        "game_score": 87.0974,
                        "game_percentile": 100.0,
                        "performance_tier": "S",
                    },
                }
            ]
        )
    )

    result = repository.list_psus(page=1, limit=10)

    assert [psu.id for psu in result.items] == ["1"]
    assert [psu.name for psu in result.items] == ["1st Player NGDP 1000W"]
    assert result.page == 1
    assert result.limit == 10
    assert result.total == 1
    assert result.items[0].benchmark is not None
    assert result.items[0].benchmark.cybenetics_score == 87.0974
    assert result.items[0].ranking is not None
    assert result.items[0].ranking.performance_tier == "S"


def test_psu_repository_lists_rankings_with_sort_and_filters() -> None:
    from app.repositories.psu_repository import PsuRepository

    repository = PsuRepository(
        FakeCollection(
            [
                {
                    "_id": 1,
                    "name": "1st Player NGDP 1000W",
                    "sku": "1st-player-ngdp-1000w",
                    "brand": "1st Player",
                    "wattage_w": 1000,
                    "form_factor": "ATX",
                    "atx_version": "ATX3.0",
                    "efficiency_rating": "PLATINUM",
                    "noise_rating": "Standard++",
                    "ranking": {
                        "game_score": 87.0974,
                        "game_percentile": 100.0,
                        "performance_tier": "S",
                    },
                },
                {
                    "_id": 2,
                    "name": "1st Player ACK 750W Gold",
                    "sku": "1st-player-ack-750w-gold",
                    "brand": "1st Player",
                    "wattage_w": 750,
                    "form_factor": "ATX",
                    "atx_version": "ATX",
                    "efficiency_rating": "GOLD",
                    "noise_rating": "Standard+",
                    "ranking": {
                        "game_score": 82.5645,
                        "game_percentile": 94.8,
                        "performance_tier": "S",
                    },
                },
                {
                    "_id": 3,
                    "name": "Quiet PSU 650W",
                    "sku": "quiet-psu-650w",
                    "brand": "Quiet",
                    "wattage_w": 650,
                    "form_factor": "SFX",
                    "atx_version": "ATX3.1",
                    "efficiency_rating": "GOLD",
                    "noise_rating": "A",
                    "ranking": {
                        "game_score": 61.5,
                        "game_percentile": 70.61,
                        "performance_tier": "B",
                    },
                },
            ]
        )
    )

    result = repository.list_rankings(
        sort="desc",
        brand="1st Player",
        wattage_w=1000,
        form_factor="ATX",
        atx_version="ATX3.0",
        performance_tier="s",
        q="ngdp",
        page=1,
        limit=10,
    )

    assert [(psu.name, psu.brand, psu.wattage_w) for psu in result.items] == [
        ("1st Player NGDP 1000W", "1st Player", 1000),
    ]
    assert result.page == 1
    assert result.limit == 10
    assert result.total == 1
    assert result.items[0].sku == "1st-player-ngdp-1000w"
    assert result.items[0].ranking is not None
    assert result.items[0].ranking.game_percentile == 100.0
