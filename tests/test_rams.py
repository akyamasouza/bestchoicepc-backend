from collections.abc import Iterable, Iterator
import re
from typing import Any

from fastapi.testclient import TestClient

from app.main import app
from app.routes.rams import get_ram_repository
from app.schemas.ram import RamCompatibility, RamListItem, RamListResponse


class FakeRamRepository:
    def list_rams(
        self,
        *,
        brand: str | None = None,
        generation: str | None = None,
        form_factor: str | None = None,
        device: str | None = None,
        capacity_gb: int | None = None,
        module_count: int | None = None,
        speed_mhz: int | None = None,
        profile: str | None = None,
        rgb: bool | None = None,
        q: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> RamListResponse:
        items = [
            RamListItem(
                id="ram-1",
                name="Memória RAM Kingston Fury Beast, 8GB, 3200MHz, DDR4, CL16, Preto - KF432C16BB/8",
                sku="KF432C16BB/8",
                brand="Kingston",
                generation="DDR4",
                form_factor="UDIMM",
                capacity_gb=8,
                module_count=1,
                capacity_per_module_gb=8,
                speed_mhz=3200,
                cl=16,
                rgb=False,
                profile="unknown",
                device="desktop",
                compatibility=RamCompatibility(desktop=True, notebook=False, platforms=["DDR4"]),
            ),
            RamListItem(
                id="ram-2",
                name="Memória RAM para Notebook Kingston Fury Impact, 16GB, 5600MHz, DDR5, CL40, SODIMM - KF556S40IB-16",
                sku="KF556S40IB-16",
                brand="Kingston",
                generation="DDR5",
                form_factor="SODIMM",
                capacity_gb=16,
                module_count=1,
                capacity_per_module_gb=16,
                speed_mhz=5600,
                cl=40,
                rgb=False,
                profile="unknown",
                device="notebook",
                compatibility=RamCompatibility(desktop=False, notebook=True, platforms=["DDR5"]),
            ),
        ]

        if brand is not None:
            items = [item for item in items if item.brand.lower() == brand.lower()]
        if generation is not None:
            items = [item for item in items if item.generation == generation.upper()]
        if form_factor is not None:
            items = [item for item in items if item.form_factor and item.form_factor.lower() == form_factor.lower()]
        if device is not None:
            items = [item for item in items if item.device and item.device.lower() == device.lower()]
        if capacity_gb is not None:
            items = [item for item in items if item.capacity_gb == capacity_gb]
        if module_count is not None:
            items = [item for item in items if item.module_count == module_count]
        if speed_mhz is not None:
            items = [item for item in items if item.speed_mhz == speed_mhz]
        if profile is not None:
            items = [item for item in items if item.profile and item.profile.lower() == profile.lower()]
        if rgb is not None:
            items = [item for item in items if item.rgb == rgb]
        if q is not None and q.strip():
            normalized = q.strip().lower()
            items = [item for item in items if normalized in item.name.lower() or normalized in item.sku.lower()]

        total = len(items)
        start = (page - 1) * limit
        return RamListResponse(items=items[start : start + limit], page=page, limit=limit, total=total)


class FakeCursor(Iterable[dict[str, Any]]):
    def __init__(self, documents: list[dict[str, Any]]):
        self.documents = documents

    def sort(self, field_or_fields, direction: int | None = None) -> "FakeCursor":
        reverse = direction == -1
        self.documents = sorted(self.documents, key=lambda document: _get_nested_value(document, field_or_fields), reverse=reverse)
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


def test_list_rams_route_with_filters() -> None:
    app.dependency_overrides[get_ram_repository] = FakeRamRepository
    client = TestClient(app)

    response = client.get("/rams?brand=Kingston&generation=DDR5&form_factor=SODIMM&device=notebook&capacity_gb=16&module_count=1&speed_mhz=5600&q=KF556&page=1&limit=10")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["sku"] == "KF556S40IB-16"


def test_ram_repository_maps_documents() -> None:
    from app.repositories.ram_repository import RamRepository

    repository = RamRepository(
        FakeCollection(
            [
                {
                    "_id": 1,
                    "name": "Memória RAM Kingston Fury Beast, 8GB, 3200MHz, DDR4, CL16, Preto - KF432C16BB/8",
                    "sku": "KF432C16BB/8",
                    "brand": "Kingston",
                    "generation": "DDR4",
                    "form_factor": "UDIMM",
                    "capacity_gb": 8,
                    "module_count": 1,
                    "capacity_per_module_gb": 8,
                    "speed_mhz": 3200,
                    "cl": 16,
                    "rgb": False,
                    "profile": "unknown",
                    "device": "desktop",
                    "compatibility": {"desktop": True, "notebook": False, "platforms": ["DDR4"]},
                }
            ]
        )
    )

    result = repository.list_rams(page=1, limit=10)

    assert result.total == 1
    assert result.items[0].sku == "KF432C16BB/8"
    assert result.items[0].compatibility.desktop is True


def test_ram_repository_filters_in_database_query() -> None:
    from app.repositories.ram_repository import RamRepository

    repository = RamRepository(
        FakeCollection(
            [
                {
                    "_id": 1,
                    "name": "Memória RAM Kingston Fury Beast, 8GB, 3200MHz, DDR4, CL16, Preto - KF432C16BB/8",
                    "sku": "KF432C16BB/8",
                    "brand": "Kingston",
                    "generation": "DDR4",
                    "form_factor": "UDIMM",
                    "capacity_gb": 8,
                    "module_count": 1,
                    "capacity_per_module_gb": 8,
                    "speed_mhz": 3200,
                    "cl": 16,
                    "rgb": False,
                    "profile": "unknown",
                    "device": "desktop",
                    "compatibility": {"desktop": True, "notebook": False, "platforms": ["DDR4"]},
                },
                {
                    "_id": 2,
                    "name": "Memória RAM para Notebook Kingston Fury Impact, 16GB, 5600MHz, DDR5, CL40, SODIMM - KF556S40IB-16",
                    "sku": "KF556S40IB-16",
                    "brand": "Kingston",
                    "generation": "DDR5",
                    "form_factor": "SODIMM",
                    "capacity_gb": 16,
                    "module_count": 1,
                    "capacity_per_module_gb": 16,
                    "speed_mhz": 5600,
                    "cl": 40,
                    "rgb": False,
                    "profile": "unknown",
                    "device": "notebook",
                    "compatibility": {"desktop": False, "notebook": True, "platforms": ["DDR5"]},
                },
            ]
        )
    )

    result = repository.list_rams(
        brand="Kingston",
        generation="DDR5",
        form_factor="SODIMM",
        device="notebook",
        capacity_gb=16,
        module_count=1,
        speed_mhz=5600,
        q="KF556",
        page=1,
        limit=10,
    )

    assert result.total == 1
    assert result.items[0].sku == "KF556S40IB-16"
