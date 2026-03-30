from typing import Any, Literal

from pymongo.collection import Collection

from app.schemas.ssd import (
    SsdBenchmark,
    SsdListItem,
    SsdListResponse,
    SsdRanking,
    SsdRankingListItem,
    SsdRankingListResponse,
)


class SsdRepository:
    def __init__(self, collection: Collection):
        self.collection = collection

    def list_ssds(
        self,
        *,
        page: int = 1,
        limit: int = 20,
    ) -> SsdListResponse:
        cursor = self.collection.find(
            {},
            {
                "name": 1,
                "sku": 1,
                "brand": 1,
                "capacity_gb": 1,
                "interface": 1,
                "nand": 1,
                "dram": 1,
                "benchmark": 1,
                "ranking": 1,
            },
        ).sort("name", 1)

        items = [self._to_list_item(document) for document in cursor]
        total = len(items)
        start = (page - 1) * limit

        return SsdListResponse(
            items=items[start : start + limit],
            page=page,
            limit=limit,
            total=total,
        )

    def list_rankings(
        self,
        *,
        sort: Literal["asc", "desc"] = "desc",
        brand: str | None = None,
        capacity_gb: int | None = None,
        interface: str | None = None,
        performance_tier: str | None = None,
        q: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> SsdRankingListResponse:
        cursor = self.collection.find(
            {},
            {
                "_id": 1,
                "name": 1,
                "sku": 1,
                "brand": 1,
                "capacity_gb": 1,
                "interface": 1,
                "ranking": 1,
            },
        )

        items = [self._to_ranking_list_item(document) for document in cursor]

        if brand is not None:
            normalized_brand = brand.strip().lower()
            items = [item for item in items if item.brand.lower() == normalized_brand]

        if capacity_gb is not None:
            items = [item for item in items if item.capacity_gb == capacity_gb]

        if interface is not None:
            normalized_interface = interface.strip().lower()
            items = [
                item
                for item in items
                if item.interface is not None and item.interface.lower() == normalized_interface
            ]

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

        return SsdRankingListResponse(
            items=items[start : start + limit],
            page=page,
            limit=limit,
            total=total,
        )

    def _to_list_item(self, document: dict[str, Any]) -> SsdListItem:
        return SsdListItem(
            id=str(document["_id"]),
            name=document["name"],
            sku=document["sku"],
            brand=document["brand"],
            capacity_gb=document.get("capacity_gb"),
            interface=document.get("interface"),
            nand=document.get("nand"),
            dram=document.get("dram"),
            benchmark=self._to_benchmark(document.get("benchmark")),
            ranking=self._to_ranking(document.get("ranking")),
        )

    def _to_ranking_list_item(self, document: dict[str, Any]) -> SsdRankingListItem:
        return SsdRankingListItem(
            id=str(document["_id"]),
            name=document["name"],
            sku=document["sku"],
            brand=document["brand"],
            capacity_gb=document.get("capacity_gb"),
            interface=document.get("interface"),
            ranking=self._to_ranking(document.get("ranking")),
        )

    def _to_benchmark(self, benchmark: dict[str, Any] | None) -> SsdBenchmark | None:
        if benchmark is None:
            return None

        return SsdBenchmark(
            ssd_tester_score=benchmark.get("ssd_tester_score"),
        )

    def _to_ranking(self, ranking: dict[str, Any] | None) -> SsdRanking | None:
        if ranking is None:
            return None

        return SsdRanking(
            game_score=ranking.get("game_score"),
            game_percentile=ranking.get("game_percentile"),
            performance_tier=ranking.get("performance_tier"),
        )

    @staticmethod
    def _ranking_percentile_sort_key(item: SsdRankingListItem) -> float:
        if item.ranking is None or item.ranking.game_percentile is None:
            return float("-inf")

        return item.ranking.game_percentile
