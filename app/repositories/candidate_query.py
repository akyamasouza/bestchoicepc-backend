from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Generic, TypeVar

from pymongo import ASCENDING
from pymongo.collection import Collection


ItemT = TypeVar("ItemT")


@dataclass(frozen=True, slots=True)
class CandidateQueryStrategy(Generic[ItemT]):
    projection: dict[str, int]
    map_item_fn: Callable[[dict[str, Any]], ItemT]

    def map_item(self, document: dict[str, Any]) -> ItemT:
        return self.map_item_fn(document)


def execute_candidate_query(
    collection: Collection,
    strategy: CandidateQueryStrategy[ItemT],
    *,
    sku: str | None,
) -> list[ItemT]:
    query: dict[str, Any] = {"sku": sku} if sku is not None else {"ranking.game_percentile": {"$ne": None}}
    cursor = collection.find(query, strategy.projection).sort("name", ASCENDING)
    return [strategy.map_item(document) for document in cursor]
