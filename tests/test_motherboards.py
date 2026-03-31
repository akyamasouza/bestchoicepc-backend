from collections.abc import Iterable, Iterator
import re
from typing import Any

from fastapi.testclient import TestClient

from app.main import app
from app.routes.motherboards import get_motherboard_repository
from app.schemas.motherboard import (
    MotherboardCompatibility,
    MotherboardListItem,
    MotherboardListResponse,
)


class FakeMotherboardRepository:
    def list_motherboards(
        self,
        *,
        brand: str | None = None,
        cpu_brand: str | None = None,
        socket: str | None = None,
        chipset: str | None = None,
        form_factor: str | None = None,
        memory_generation: str | None = None,
        wifi: bool | None = None,
        bluetooth: bool | None = None,
        q: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> MotherboardListResponse:
        items = [
            MotherboardListItem(
                id="mb-1",
                name="Placa-Mãe ASUS TUF Gaming B650M-E, WIFI, AMD AM5, B650, DDR5, Preto - 90MB1FV0-M0EAY0",
                sku="90MB1FV0-M0EAY0",
                brand="ASUS",
                cpu_brand="AMD",
                socket="AM5",
                chipset="B650",
                form_factor=None,
                memory_generation="DDR5",
                wifi=True,
                bluetooth=False,
                compatibility=MotherboardCompatibility(
                    desktop=True,
                    cpu_brands=["AMD"],
                    sockets=["AM5"],
                    memory_generations=["DDR5"],
                ),
            ),
            MotherboardListItem(
                id="mb-2",
                name="Placa Mãe Gigabyte B550M DS3H AC R2, AMD AM4, Micro ATX, DDR4, RGB, Wi-Fi, Bluetooth, Preto - B550M DS3H AC R2",
                sku="B550M DS3H AC R2",
                brand="Gigabyte",
                cpu_brand="AMD",
                socket="AM4",
                chipset="B550",
                form_factor="Micro ATX",
                memory_generation="DDR4",
                wifi=True,
                bluetooth=True,
                compatibility=MotherboardCompatibility(
                    desktop=True,
                    cpu_brands=["AMD"],
                    sockets=["AM4"],
                    memory_generations=["DDR4"],
                ),
            ),
        ]

        if brand is not None:
            items = [item for item in items if item.brand.lower() == brand.lower()]
        if cpu_brand is not None:
            items = [item for item in items if item.cpu_brand and item.cpu_brand.lower() == cpu_brand.lower()]
        if socket is not None:
            items = [item for item in items if item.socket and item.socket.lower() == socket.lower()]
        if chipset is not None:
            items = [item for item in items if item.chipset and item.chipset.lower() == chipset.lower()]
        if form_factor is not None:
            items = [item for item in items if item.form_factor and item.form_factor.lower() == form_factor.lower()]
        if memory_generation is not None:
            items = [item for item in items if item.memory_generation == memory_generation.upper()]
        if wifi is not None:
            items = [item for item in items if item.wifi == wifi]
        if bluetooth is not None:
            items = [item for item in items if item.bluetooth == bluetooth]
        if q is not None and q.strip():
            normalized = q.strip().lower()
            items = [item for item in items if normalized in item.name.lower() or normalized in item.sku.lower()]

        total = len(items)
        start = (page - 1) * limit
        return MotherboardListResponse(items=items[start : start + limit], page=page, limit=limit, total=total)


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


def test_list_motherboards_route_with_filters() -> None:
    app.dependency_overrides[get_motherboard_repository] = FakeMotherboardRepository
    client = TestClient(app)

    response = client.get("/motherboards?cpu_brand=AMD&socket=AM4&chipset=B550&form_factor=Micro%20ATX&memory_generation=DDR4&wifi=true&bluetooth=true&q=DS3H&page=1&limit=10")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["sku"] == "B550M DS3H AC R2"


def test_motherboard_repository_maps_documents() -> None:
    from app.repositories.motherboard_repository import MotherboardRepository

    repository = MotherboardRepository(
        FakeCollection(
            [
                {
                    "_id": 1,
                    "name": "Placa-Mãe ASUS TUF Gaming B650M-E, WIFI, AMD AM5, B650, DDR5, Preto - 90MB1FV0-M0EAY0",
                    "sku": "90MB1FV0-M0EAY0",
                    "brand": "ASUS",
                    "cpu_brand": "AMD",
                    "socket": "AM5",
                    "chipset": "B650",
                    "form_factor": None,
                    "memory_generation": "DDR5",
                    "wifi": True,
                    "bluetooth": False,
                    "compatibility": {"desktop": True, "cpu_brands": ["AMD"], "sockets": ["AM5"], "memory_generations": ["DDR5"]},
                }
            ]
        )
    )

    result = repository.list_motherboards(page=1, limit=10)

    assert result.total == 1
    assert result.items[0].socket == "AM5"
    assert result.items[0].compatibility.cpu_brands == ["AMD"]


def test_motherboard_repository_filters_in_database_query() -> None:
    from app.repositories.motherboard_repository import MotherboardRepository

    repository = MotherboardRepository(
        FakeCollection(
            [
                {
                    "_id": 1,
                    "name": "Placa-Mãe ASUS TUF Gaming B650M-E, WIFI, AMD AM5, B650, DDR5, Preto - 90MB1FV0-M0EAY0",
                    "sku": "90MB1FV0-M0EAY0",
                    "brand": "ASUS",
                    "cpu_brand": "AMD",
                    "socket": "AM5",
                    "chipset": "B650",
                    "form_factor": None,
                    "memory_generation": "DDR5",
                    "wifi": True,
                    "bluetooth": False,
                    "compatibility": {"desktop": True, "cpu_brands": ["AMD"], "sockets": ["AM5"], "memory_generations": ["DDR5"]},
                },
                {
                    "_id": 2,
                    "name": "Placa Mãe Gigabyte B550M DS3H AC R2, AMD AM4, Micro ATX, DDR4, RGB, Wi-Fi, Bluetooth, Preto - B550M DS3H AC R2",
                    "sku": "B550M DS3H AC R2",
                    "brand": "Gigabyte",
                    "cpu_brand": "AMD",
                    "socket": "AM4",
                    "chipset": "B550",
                    "form_factor": "Micro ATX",
                    "memory_generation": "DDR4",
                    "wifi": True,
                    "bluetooth": True,
                    "compatibility": {"desktop": True, "cpu_brands": ["AMD"], "sockets": ["AM4"], "memory_generations": ["DDR4"]},
                },
            ]
        )
    )

    result = repository.list_motherboards(
        cpu_brand="AMD",
        socket="AM4",
        chipset="B550",
        form_factor="Micro ATX",
        memory_generation="DDR4",
        wifi=True,
        bluetooth=True,
        q="DS3H",
        page=1,
        limit=10,
    )

    assert result.total == 1
    assert result.items[0].sku == "B550M DS3H AC R2"
