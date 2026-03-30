import re
from typing import Any, Literal

from pymongo.collection import Collection

from app.repositories.ranking_query import RankingQueryStrategy, execute_ranking_query
from app.schemas.cpu import (
    CpuBenchmark,
    CpuListItem,
    CpuRanking,
    CpuRankingListItem,
    CpuRankingListResponse,
)


class CpuRepository:
    def __init__(self, collection: Collection):
        self.collection = collection
        self.ranking_strategy = RankingQueryStrategy[
            CpuRankingListItem,
            CpuRankingListResponse,
        ](
            projection={
                "_id": 1,
                "name": 1,
                "sku": 1,
                "first_seen": 1,
                "ranking": 1,
            },
            build_query_fn=self._build_rankings_query,
            map_item_fn=self._to_ranking_list_item,
            build_response_fn=self._build_rankings_response,
        )

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
                "ranking": 1,
            },
        ).sort("name", 1)

        return [self._to_list_item(document) for document in cursor]

    def list_rankings(
        self,
        *,
        sort: Literal["asc", "desc"] = "desc",
        brand: str | None = None,
        release_year: int | None = None,
        performance_tier: str | None = None,
        q: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> CpuRankingListResponse:
        return execute_ranking_query(
            self.collection,
            self.ranking_strategy,
            filters={
                "brand": brand,
                "release_year": release_year,
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
        release_year = filters.get("release_year")
        performance_tier = filters.get("performance_tier")
        q = filters.get("q")
        query: dict[str, Any] = {}

        if brand is not None:
            normalized_brand = re.escape(brand.strip())
            query["name"] = {"$regex": rf"^{normalized_brand}\b", "$options": "i"}

        if release_year is not None:
            query["first_seen"] = {"$regex": str(release_year)}

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
        items: list[CpuRankingListItem],
        page: int,
        limit: int,
        total: int,
    ) -> CpuRankingListResponse:
        return CpuRankingListResponse(
            items=items,
            page=page,
            limit=limit,
            total=total,
        )

    def _to_list_item(self, document: dict[str, Any]) -> CpuListItem:
        return CpuListItem(
            id=str(document["_id"]),
            name=document["name"],
            sku=document["sku"],
            socket=document.get("socket"),
            cores=document.get("cores"),
            threads=document.get("threads"),
            benchmark=self._to_benchmark(document.get("benchmark")),
            ranking=self._to_ranking(document.get("ranking")),
        )

    def _to_ranking_list_item(self, document: dict[str, Any]) -> CpuRankingListItem:
        return CpuRankingListItem(
            id=str(document["_id"]),
            name=document["name"],
            sku=document["sku"],
            brand=self._resolve_brand(document["name"]),
            release_year=self._resolve_release_year(document.get("first_seen")),
            ranking=self._to_ranking(document.get("ranking")),
        )

    def _to_benchmark(self, benchmark: dict[str, Any] | None) -> CpuBenchmark | None:
        if benchmark is None:
            return None

        return CpuBenchmark(
            multithread_rating=benchmark.get("multithread_rating"),
            single_thread_rating=benchmark.get("single_thread_rating"),
            techpowerup_relative_performance_applications=benchmark.get(
                "techpowerup_relative_performance_applications"
            ),
            samples=benchmark.get("samples"),
            margin_for_error=benchmark.get("margin_for_error"),
        )

    def _to_ranking(self, ranking: dict[str, Any] | None) -> CpuRanking | None:
        if ranking is None:
            return None

        return CpuRanking(
            game_score=ranking.get("game_score"),
            game_percentile=ranking.get("game_percentile"),
            performance_tier=ranking.get("performance_tier"),
        )

    @staticmethod
    def _resolve_brand(name: str) -> str:
        return name.split()[0]

    @staticmethod
    def _resolve_release_year(first_seen: Any) -> int | None:
        if first_seen is None:
            return None

        match = re.search(r"(20\d{2})", str(first_seen))
        if match is None:
            return None

        return int(match.group(1))
