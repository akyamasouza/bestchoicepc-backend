import re
from typing import Any, Literal

from app.repositories.protocols import ASCENDING, CollectionProtocol
from app.repositories.ranking_query import RankingQueryStrategy, execute_ranking_query
from app.schemas.ssd import (
    SsdBenchmark,
    SsdListItem,
    SsdListResponse,
    SsdRanking,
    SsdRankingListItem,
    SsdRankingListResponse,
)


class SsdRepository:
    def __init__(self, collection: CollectionProtocol) -> None:
        self.collection = collection
        self.ranking_strategy = RankingQueryStrategy[
            SsdRankingListItem,
            SsdRankingListResponse,
        ](
            projection={
                "_id": 1,
                "name": 1,
                "sku": 1,
                "brand": 1,
                "capacity_gb": 1,
                "interface": 1,
                "ranking": 1,
            },
            build_query_fn=self._build_rankings_query,
            map_item_fn=self._to_ranking_list_item,
            build_response_fn=self._build_rankings_response,
        )

    def list_ssds(
        self,
        *,
        page: int = 1,
        limit: int = 20,
    ) -> SsdListResponse:
        query: dict[str, Any] = {}
        total = self.collection.count_documents(query)
        cursor = (
            self.collection.find(
                query,
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
            )
            .sort("name", ASCENDING)
            .skip((page - 1) * limit)
            .limit(limit)
        )

        items = [self._to_list_item(document) for document in cursor]

        return SsdListResponse(
            items=items,
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
        return execute_ranking_query(
            self.collection,
            self.ranking_strategy,
            filters={
                "brand": brand,
                "capacity_gb": capacity_gb,
                "interface": interface,
                "performance_tier": performance_tier,
                "q": q,
            },
            sort=sort,
            page=page,
            limit=limit,
        )

    def _build_rankings_query(
        self,
        filters: dict[str, Any],
    ) -> dict[str, Any]:
        brand = filters.get("brand")
        capacity_gb = filters.get("capacity_gb")
        interface = filters.get("interface")
        performance_tier = filters.get("performance_tier")
        q = filters.get("q")
        query: dict[str, Any] = {}

        if brand is not None:
            query["brand"] = {"$regex": f"^{re.escape(brand.strip())}$", "$options": "i"}

        if capacity_gb is not None:
            query["capacity_gb"] = capacity_gb

        if interface is not None:
            query["interface"] = {"$regex": f"^{re.escape(interface.strip())}$", "$options": "i"}

        if performance_tier is not None:
            query["ranking.performance_tier"] = performance_tier.strip().upper()

        if q is not None and q.strip():
            normalized_query = re.escape(q.strip())
            query["$or"] = [
                {"name": {"$regex": normalized_query, "$options": "i"}},
                {"sku": {"$regex": normalized_query, "$options": "i"}},
            ]

        return query

    @staticmethod
    def _build_rankings_response(
        items: list[SsdRankingListItem],
        page: int,
        limit: int,
        total: int,
    ) -> SsdRankingListResponse:
        return SsdRankingListResponse(
            items=items,
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
