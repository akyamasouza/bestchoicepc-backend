import re
from typing import Any, Literal

from pymongo.collection import Collection

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
        cursor = self.collection.find(
            {},
            {
                "_id": 1,
                "name": 1,
                "sku": 1,
                "first_seen": 1,
                "ranking": 1,
            },
        )

        items = [self._to_ranking_list_item(document) for document in cursor]
        if brand is not None:
            normalized_brand = brand.strip().lower()
            items = [item for item in items if item.brand.lower() == normalized_brand]

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
        items = sorted(
            items,
            key=self._ranking_percentile_sort_key,
            reverse=sort == "desc",
        )

        total = len(items)
        start = (page - 1) * limit
        paginated_items = items[start : start + limit]

        return CpuRankingListResponse(
            items=paginated_items,
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

    @staticmethod
    def _ranking_percentile_sort_key(item: CpuRankingListItem) -> float:
        if item.ranking is None or item.ranking.game_percentile is None:
            return float("-inf")

        return item.ranking.game_percentile
