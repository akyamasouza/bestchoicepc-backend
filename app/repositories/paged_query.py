from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Generic, TypeVar

from app.repositories.protocols import CollectionProtocol


ItemT = TypeVar("ItemT")
ResponseT = TypeVar("ResponseT")


@dataclass(frozen=True, slots=True)
class PagedQueryStrategy(Generic[ItemT, ResponseT]):
    projection: dict[str, int]
    build_query_fn: Callable[[dict[str, Any]], dict[str, Any]]
    map_item_fn: Callable[[dict[str, Any]], ItemT]
    build_response_fn: Callable[[list[ItemT], int, int, int], ResponseT]
    sort_fields: str | list[tuple[str, int]]
    sort_direction: int | None = None

    def build_query(self, filters: dict[str, Any]) -> dict[str, Any]:
        return self.build_query_fn(filters)

    def map_item(self, document: dict[str, Any]) -> ItemT:
        return self.map_item_fn(document)

    def build_response(self, items: list[ItemT], page: int, limit: int, total: int) -> ResponseT:
        return self.build_response_fn(items, page, limit, total)


def execute_paged_query(
    collection: CollectionProtocol,
    strategy: PagedQueryStrategy[ItemT, ResponseT],
    *,
    filters: dict[str, Any],
    page: int,
    limit: int,
) -> ResponseT:
    query = strategy.build_query(filters)
    total = collection.count_documents(query)
    cursor = collection.find(query, strategy.projection)

    if isinstance(strategy.sort_fields, list):
        cursor = cursor.sort(strategy.sort_fields)
    else:
        cursor = cursor.sort(strategy.sort_fields, strategy.sort_direction)

    cursor = cursor.skip((page - 1) * limit).limit(limit)
    items = [strategy.map_item(document) for document in cursor]
    return strategy.build_response(items, page, limit, total)
