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


def test_list_motherboards_route_with_filters() -> None:
    app.dependency_overrides[get_motherboard_repository] = FakeMotherboardRepository
    client = TestClient(app)

    response = client.get("/motherboards?cpu_brand=AMD&socket=AM4&chipset=B550&form_factor=Micro%20ATX&memory_generation=DDR4&wifi=true&bluetooth=true&q=DS3H&page=1&limit=10")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["sku"] == "B550M DS3H AC R2"
