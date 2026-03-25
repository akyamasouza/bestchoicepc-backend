from collections.abc import Iterable, Iterator
from typing import Any

from fastapi.testclient import TestClient

from app.main import app
from app.routes.cpus import get_cpu_repository
from app.schemas.cpu import CpuBenchmark, CpuListItem


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
                    samples=4200,
                    margin_for_error="Low",
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
                    samples=5519,
                    margin_for_error="Low",
                ),
            ),
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
                "samples": 4200,
                "margin_for_error": "Low",
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
                "samples": 5519,
                "margin_for_error": "Low",
            },
        },
    ]


def test_cpu_repository_maps_documents() -> None:
    from app.repositories.cpu_repository import CpuRepository

    repository = CpuRepository(
        FakeCollection(
            [
                {
                    "_id": 2,
                    "name": "AMD Ryzen 9 9950X",
                    "sku": "100-100001277WOF",
                    "socket": "AM5",
                    "cores": 16,
                    "threads": 32,
                    "benchmark": {
                        "multithread_rating": 65809,
                        "single_thread_rating": 4729,
                        "samples": 5519,
                        "margin_for_error": "Low",
                    },
                },
                {
                    "_id": 1,
                    "name": "AMD Ryzen 7 7800X3D",
                    "sku": "100-000000910",
                    "socket": "AM5",
                    "cores": 8,
                    "threads": 16,
                    "benchmark": {
                        "multithread_rating": 34321,
                        "single_thread_rating": 4012,
                        "samples": 4200,
                        "margin_for_error": "Low",
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
