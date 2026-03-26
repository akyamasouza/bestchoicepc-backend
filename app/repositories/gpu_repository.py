import re
from typing import Any, Literal

from pymongo.collection import Collection

from app.schemas.gpu import (
    GpuBenchmark,
    GpuListItem,
    GpuRanking,
    GpuRankingListItem,
    GpuRankingListResponse,
)


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
                "ranking": 1,
            },
        ).sort("name", 1)

        return [self._to_list_item(document) for document in cursor]

    def list_rankings(
        self,
        *,
        sort: Literal["asc", "desc"] = "desc",
        brand: str | None = None,
        category: str | None = None,
        release_year: int | None = None,
        performance_tier: str | None = None,
        q: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> GpuRankingListResponse:
        cursor = self.collection.find(
            {},
            {
                "_id": 1,
                "name": 1,
                "sku": 1,
                "brand": 1,
                "category": 1,
                "first_benchmarked": 1,
                "ranking": 1,
            },
        )

        items = [self._to_ranking_list_item(document) for document in cursor]

        if brand is not None:
            normalized_brand = brand.strip().lower()
            items = [
                item for item in items if item.brand is not None and item.brand.lower() == normalized_brand
            ]

        if category is not None:
            normalized_category = category.strip().lower()
            items = [
                item
                for item in items
                if item.category is not None and item.category.lower() == normalized_category
            ]

        if release_year is not None:
            items = [item for item in items if item.release_year == release_year]

        if performance_tier is not None:
            normalized_tier = performance_tier.strip().upper()
            items = [
                item
                for item in items
                if item.ranking is not None and item.ranking.performance_tier == normalized_tier
            ]

        if q is not None and q.strip():
            normalized_query = q.strip().lower()
            items = [
                item
                for item in items
                if normalized_query in item.name.lower() or normalized_query in item.sku.lower()
            ]

        items = sorted(items, key=lambda item: item.name.lower())
        items = sorted(items, key=self._ranking_percentile_sort_key, reverse=sort == "desc")

        total = len(items)
        start = (page - 1) * limit
        paginated_items = items[start : start + limit]

        return GpuRankingListResponse(
            items=paginated_items,
            page=page,
            limit=limit,
            total=total,
        )

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
            ranking=self._to_ranking(document.get("ranking")),
        )

    def _to_ranking_list_item(self, document: dict[str, Any]) -> GpuRankingListItem:
        return GpuRankingListItem(
            id=str(document["_id"]),
            name=document["name"],
            sku=document["sku"],
            brand=document.get("brand"),
            category=document.get("category"),
            release_year=self._resolve_release_year(document.get("first_benchmarked")),
            ranking=self._to_ranking(document.get("ranking")),
        )

    def _to_benchmark(self, benchmark: dict[str, Any] | None) -> GpuBenchmark | None:
        if benchmark is None:
            return None

        return GpuBenchmark(
            g3d_mark=benchmark.get("g3d_mark"),
            g2d_mark=benchmark.get("g2d_mark"),
            tomshardware_relative_performance_1080p_medium=benchmark.get(
                "tomshardware_relative_performance_1080p_medium"
            ),
            samples=benchmark.get("samples"),
        )

    def _to_ranking(self, ranking: dict[str, Any] | None) -> GpuRanking | None:
        if ranking is None:
            return None

        return GpuRanking(
            game_score=ranking.get("game_score"),
            game_percentile=ranking.get("game_percentile"),
            performance_tier=ranking.get("performance_tier"),
        )

    @staticmethod
    def _resolve_release_year(first_benchmarked: Any) -> int | None:
        if first_benchmarked is None:
            return None

        match = re.search(r"(20\d{2})", str(first_benchmarked))
        if match is None:
            return None

        return int(match.group(1))

    @staticmethod
    def _ranking_percentile_sort_key(item: GpuRankingListItem) -> float:
        if item.ranking is None or item.ranking.game_percentile is None:
            return float("-inf")

        return item.ranking.game_percentile
