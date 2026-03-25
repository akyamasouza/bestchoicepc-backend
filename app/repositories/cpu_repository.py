from typing import Any

from pymongo.collection import Collection

from app.schemas.cpu import CpuBenchmark, CpuListItem


class CpuRepository:
    def __init__(self, collection: Collection):
        self.collection = collection

    def list_cpus(self) -> list[CpuListItem]:
        cursor = self.collection.find(
            {},
            {
                "name": 1,
                "sku": 1,
                "socket": 1,
                "cores": 1,
                "threads": 1,
                "benchmark": 1,
            },
        ).sort("name", 1)

        return [self._to_list_item(document) for document in cursor]

    def _to_list_item(self, document: dict[str, Any]) -> CpuListItem:
        return CpuListItem(
            id=str(document["_id"]),
            name=document["name"],
            sku=document["sku"],
            socket=document.get("socket"),
            cores=document.get("cores"),
            threads=document.get("threads"),
            benchmark=self._to_benchmark(document.get("benchmark")),
        )

    def _to_benchmark(self, benchmark: dict[str, Any] | None) -> CpuBenchmark | None:
        if benchmark is None:
            return None

        return CpuBenchmark(
            multithread_rating=benchmark.get("multithread_rating"),
            single_thread_rating=benchmark.get("single_thread_rating"),
            samples=benchmark.get("samples"),
            margin_for_error=benchmark.get("margin_for_error"),
        )
