import re
from typing import Any, Literal

from pymongo import ASCENDING
from pymongo.collection import Collection

from app.repositories.candidate_query import CandidateQueryStrategy, execute_candidate_query
from app.repositories.paged_query import PagedQueryStrategy, execute_paged_query
from app.repositories.ranking_query import RankingQueryStrategy, execute_ranking_query
from app.schemas.gpu import (
    GpuBenchmark,
    GpuListItem,
    GpuListResponse,
    GpuRanking,
    GpuRankingListItem,
    GpuRankingListResponse,
)


class GpuRepository:
    def __init__(self, collection: Collection):
        self.collection = collection
        self.list_strategy = PagedQueryStrategy[GpuListItem, GpuListResponse](
            projection={
                "_id": 1,
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
            build_query_fn=self._build_list_query,
            map_item_fn=self._to_list_item,
            build_response_fn=self._build_list_response,
            sort_fields="name",
            sort_direction=ASCENDING,
        )
        self.match_candidate_strategy = CandidateQueryStrategy[GpuListItem](
            projection={
                "_id": 1,
                "name": 1,
                "sku": 1,
                "memory_size_mb": 1,
                "ranking": 1,
            },
            map_item_fn=self._to_list_item,
        )
        self.ranking_strategy = RankingQueryStrategy[
            GpuRankingListItem,
            GpuRankingListResponse,
        ](
            projection={
                "_id": 1,
                "name": 1,
                "sku": 1,
                "brand": 1,
                "category": 1,
                "first_benchmarked": 1,
                "ranking": 1,
            },
            build_query_fn=self._build_rankings_query,
            map_item_fn=self._to_ranking_list_item,
            build_response_fn=self._build_rankings_response,
        )

    def list_gpus(
        self,
        *,
        brand: str | None = None,
        category: str | None = None,
        q: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> GpuListResponse:
        return execute_paged_query(
            self.collection,
            self.list_strategy,
            filters={
                "brand": brand,
                "category": category,
                "q": q,
            },
            page=page,
            limit=limit,
        )

    def _build_list_query(self, filters: dict[str, Any]) -> dict[str, Any]:
        brand = filters.get("brand")
        category = filters.get("category")
        q = filters.get("q")
        query: dict[str, Any] = {}

        if brand is not None:
            query["brand"] = {"$regex": f"^{re.escape(brand.strip())}$", "$options": "i"}
        if category is not None:
            query["category"] = {"$regex": f"^{re.escape(category.strip())}$", "$options": "i"}
        if q is not None and q.strip():
            normalized_query = re.escape(q.strip())
            query["$or"] = [
                {"name": {"$regex": normalized_query, "$options": "i"}},
                {"sku": {"$regex": normalized_query, "$options": "i"}},
            ]

        return query

    @staticmethod
    def _build_list_response(
        items: list[GpuListItem],
        page: int,
        limit: int,
        total: int,
    ) -> GpuListResponse:
        return GpuListResponse(items=items, page=page, limit=limit, total=total)

    def list_match_candidates(self, *, id: str | None = None, sku: str | None = None) -> list[GpuListItem]:
        return execute_candidate_query(
            self.collection,
            self.match_candidate_strategy,
            id=id,
            sku=sku,
        )

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
        return execute_ranking_query(
            self.collection,
            self.ranking_strategy,
            filters={
                "brand": brand,
                "category": category,
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
        category = filters.get("category")
        release_year = filters.get("release_year")
        performance_tier = filters.get("performance_tier")
        q = filters.get("q")
        query: dict[str, Any] = {}

        if brand is not None:
            query["brand"] = {"$regex": f"^{re.escape(brand.strip())}$", "$options": "i"}

        if category is not None:
            query["category"] = {"$regex": f"^{re.escape(category.strip())}$", "$options": "i"}

        if release_year is not None:
            query["first_benchmarked"] = {"$regex": str(release_year)}

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
        items: list[GpuRankingListItem],
        page: int,
        limit: int,
        total: int,
    ) -> GpuRankingListResponse:
        return GpuRankingListResponse(
            items=items,
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
