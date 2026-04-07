from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Generic, TypeVar

from app.repositories.protocols import (
    ASCENDING,
    CollectionProtocol,
    DocumentIdCoercer,
    identity_document_id,
)


ItemT = TypeVar("ItemT")


@dataclass(frozen=True, slots=True)
class CandidateQueryStrategy(Generic[ItemT]):
    projection: dict[str, int]
    map_item_fn: Callable[[dict[str, Any]], ItemT]
    coerce_id_fn: DocumentIdCoercer = identity_document_id

    def map_item(self, document: dict[str, Any]) -> ItemT:
        return self.map_item_fn(document)


def execute_candidate_query(
    collection: CollectionProtocol,
    strategy: CandidateQueryStrategy[ItemT],
    *,
    id: str | None = None,
    sku: str | None = None,
) -> list[ItemT]:
    if id is not None:
        query: dict[str, Any] = {"_id": strategy.coerce_id_fn(id)}
    elif sku is not None:
        query = {"sku": sku}
    else:
        query = {"ranking.game_percentile": {"$ne": None}}

    cursor = collection.find(query, strategy.projection).sort("name", ASCENDING)
    return [strategy.map_item(document) for document in cursor]

