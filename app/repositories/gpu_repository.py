from typing import Any

from pymongo.collection import Collection

from app.schemas.gpu import GpuBenchmark, GpuListItem


class GpuRepository:
    def __init__(self, collection: Collection):
        self.collection = collection

    def list_gpus(self) -> list[GpuListItem]:
        cursor = self.collection.find(
            {},
            {
                "name": 1,
                "sku": 1,
                "bus_interface": 1,
                "memory_size_mb": 1,
                "core_clock_mhz": 1,
                "memory_clock_mhz": 1,
                "max_tdp_w": 1,
                "category": 1,
                "benchmark": 1,
            },
        ).sort("name", 1)

        return [self._to_list_item(document) for document in cursor]

    def _to_list_item(self, document: dict[str, Any]) -> GpuListItem:
        return GpuListItem(
            id=str(document["_id"]),
            name=document["name"],
            sku=document["sku"],
            bus_interface=document.get("bus_interface"),
            memory_size_mb=document.get("memory_size_mb"),
            core_clock_mhz=document.get("core_clock_mhz"),
            memory_clock_mhz=document.get("memory_clock_mhz"),
            max_tdp_w=document.get("max_tdp_w"),
            category=document.get("category"),
            benchmark=self._to_benchmark(document.get("benchmark")),
        )

    def _to_benchmark(self, benchmark: dict[str, Any] | None) -> GpuBenchmark | None:
        if benchmark is None:
            return None

        return GpuBenchmark(
            g3d_mark=benchmark.get("g3d_mark"),
            g2d_mark=benchmark.get("g2d_mark"),
            samples=benchmark.get("samples"),
        )
