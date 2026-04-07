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


def test_list_rams_route_with_filters() -> None:
    app.dependency_overrides[get_ram_repository] = FakeRamRepository
    client = TestClient(app)

    response = client.get("/rams?brand=Kingston&generation=DDR5&form_factor=SODIMM&device=notebook&capacity_gb=16&module_count=1&speed_mhz=5600&q=KF556&page=1&limit=10")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["sku"] == "KF556S40IB-16"
