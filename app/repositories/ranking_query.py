from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Generic, TypeVar

from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection


ItemT = TypeVar("ItemT")
ResponseT = TypeVar("ResponseT")


def default_ranking_sort_fields(sort: str) -> list[tuple[str, int]]:
    return [
        ("ranking.game_percentile", DESCENDING if sort == "desc" else ASCENDING),
        ("name", ASCENDING),
    ]


@dataclass(frozen=True, slots=True)
class RankingQueryStrategy(Generic[ItemT, ResponseT]):
    projection: dict[str, int]
    build_query_fn: Callable[[dict[str, Any]], dict[str, Any]]
    map_item_fn: Callable[[dict[str, Any]], ItemT]
    build_response_fn: Callable[[list[ItemT], int, int, int], ResponseT]
    sort_fields_fn: Callable[[str], list[tuple[str, int]]] = default_ranking_sort_fields

    def build_query(self, filters: dict[str, Any]) -> dict[str, Any]:
        return self.build_query_fn(filters)

    def map_item(self, document: dict[str, Any]) -> ItemT:
        return self.map_item_fn(document)

    def build_response(self, items: list[ItemT], page: int, limit: int, total: int) -> ResponseT:
        return self.build_response_fn(items, page, limit, total)

    def sort_fields(self, sort: str) -> list[tuple[str, int]]:
        return self.sort_fields_fn(sort)


def execute_ranking_query(
    collection: Collection,
    strategy: RankingQueryStrategy[ItemT, ResponseT],
    *,
    filters: dict[str, Any],
    sort: str,
    page: int,
    limit: int,
) -> ResponseT:
    query = strategy.build_query(filters)
    total = collection.count_documents(query)
    cursor = (
        collection.find(query, strategy.projection)
        .sort(strategy.sort_fields(sort))
        .skip((page - 1) * limit)
        .limit(limit)
    )
    items = [strategy.map_item(document) for document in cursor]
    return strategy.build_response(items, page, limit, total)
