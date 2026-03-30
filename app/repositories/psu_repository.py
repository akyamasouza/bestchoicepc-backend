import re
from typing import Any, Literal

from pymongo import ASCENDING
from pymongo.collection import Collection

from app.repositories.ranking_query import RankingQueryStrategy, execute_ranking_query
from app.schemas.psu import (
    PsuBenchmark,
    PsuListItem,
    PsuListResponse,
    PsuRanking,
    PsuRankingListItem,
    PsuRankingListResponse,
)


class PsuRepository:
    def __init__(self, collection: Collection):
        self.collection = collection
        self.ranking_strategy = RankingQueryStrategy[
            PsuRankingListItem,
            PsuRankingListResponse,
        ](
            projection={
                "_id": 1,
                "name": 1,
                "sku": 1,
                "brand": 1,
                "wattage_w": 1,
                "form_factor": 1,
                "atx_version": 1,
                "efficiency_rating": 1,
                "noise_rating": 1,
                "ranking": 1,
            },
            build_query_fn=self._build_rankings_query,
            map_item_fn=self._to_ranking_list_item,
            build_response_fn=self._build_rankings_response,
        )

    def list_psus(
        self,
        *,
        page: int = 1,
        limit: int = 20,
    ) -> PsuListResponse:
        query: dict[str, Any] = {}
        total = self.collection.count_documents(query)
        cursor = (
            self.collection.find(
                query,
                {
                    "name": 1,
                    "sku": 1,
                    "brand": 1,
                    "wattage_w": 1,
                    "form_factor": 1,
                    "atx_version": 1,
                    "efficiency_rating": 1,
                    "noise_rating": 1,
                    "benchmark": 1,
                    "ranking": 1,
                },
            )
            .sort("name", ASCENDING)
            .skip((page - 1) * limit)
            .limit(limit)
        )

        items = [self._to_list_item(document) for document in cursor]

        return PsuListResponse(
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
        wattage_w: int | None = None,
        form_factor: str | None = None,
        atx_version: str | None = None,
        performance_tier: str | None = None,
        q: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> PsuRankingListResponse:
        return execute_ranking_query(
            self.collection,
            self.ranking_strategy,
            filters={
                "brand": brand,
                "wattage_w": wattage_w,
                "form_factor": form_factor,
                "atx_version": atx_version,
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
        wattage_w = filters.get("wattage_w")
        form_factor = filters.get("form_factor")
        atx_version = filters.get("atx_version")
        performance_tier = filters.get("performance_tier")
        q = filters.get("q")
        query: dict[str, Any] = {}

        if brand is not None:
            query["brand"] = {"$regex": f"^{re.escape(brand.strip())}$", "$options": "i"}

        if wattage_w is not None:
            query["wattage_w"] = wattage_w

        if form_factor is not None:
            query["form_factor"] = {"$regex": f"^{re.escape(form_factor.strip())}$", "$options": "i"}

        if atx_version is not None:
            query["atx_version"] = {"$regex": f"^{re.escape(atx_version.strip())}$", "$options": "i"}

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
        items: list[PsuRankingListItem],
        page: int,
        limit: int,
        total: int,
    ) -> PsuRankingListResponse:
        return PsuRankingListResponse(
            items=items,
            page=page,
            limit=limit,
            total=total,
        )

    def _to_list_item(self, document: dict[str, Any]) -> PsuListItem:
        return PsuListItem(
            id=str(document["_id"]),
            name=document["name"],
            sku=document["sku"],
            brand=document["brand"],
            wattage_w=document.get("wattage_w"),
            form_factor=document.get("form_factor"),
            atx_version=document.get("atx_version"),
            efficiency_rating=document.get("efficiency_rating"),
            noise_rating=document.get("noise_rating"),
            benchmark=self._to_benchmark(document.get("benchmark")),
            ranking=self._to_ranking(document.get("ranking")),
        )

    def _to_ranking_list_item(self, document: dict[str, Any]) -> PsuRankingListItem:
        return PsuRankingListItem(
            id=str(document["_id"]),
            name=document["name"],
            sku=document["sku"],
            brand=document["brand"],
            wattage_w=document.get("wattage_w"),
            form_factor=document.get("form_factor"),
            atx_version=document.get("atx_version"),
            efficiency_rating=document.get("efficiency_rating"),
            noise_rating=document.get("noise_rating"),
            ranking=self._to_ranking(document.get("ranking")),
        )

    def _to_benchmark(self, benchmark: dict[str, Any] | None) -> PsuBenchmark | None:
        if benchmark is None:
            return None

        return PsuBenchmark(
            cybenetics_score=benchmark.get("cybenetics_score"),
        )

    def _to_ranking(self, ranking: dict[str, Any] | None) -> PsuRanking | None:
        if ranking is None:
            return None

        return PsuRanking(
            game_score=ranking.get("game_score"),
            game_percentile=ranking.get("game_percentile"),
            performance_tier=ranking.get("performance_tier"),
        )
