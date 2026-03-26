from collections.abc import Iterable, Iterator
from typing import Any

from fastapi.testclient import TestClient

from app.main import app
from app.routes.gpus import get_gpu_repository
from app.schemas.gpu import GpuBenchmark, GpuListItem, GpuRanking


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
                    samples=8123,
                ),
                ranking=GpuRanking(
                    game_score=38975,
                    game_percentile=100.0,
                    performance_tier="S",
                ),
            )
        ]


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
                "samples": 8123,
            },
            "ranking": {
                "game_score": 38975.0,
                "game_percentile": 100.0,
                "performance_tier": "S",
            },
        }
    ]


def test_gpu_repository_maps_documents() -> None:
    from app.repositories.gpu_repository import GpuRepository

    repository = GpuRepository(
        FakeCollection(
            [
                {
                    "_id": 1,
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
                        "samples": 8123,
                    },
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
    assert result[0].ranking is not None
    assert result[0].ranking.performance_tier == "S"
