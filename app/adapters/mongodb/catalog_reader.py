"""MongoDB adapter that implements the CatalogReader port."""

from __future__ import annotations

from typing import Any

from app.domain.ports import CatalogReader
from app.repositories.protocols import ASCENDING, CollectionProtocol


class MongoCatalogReader:
    """Iterates catalog collections via MongoDB, implementing CatalogReader."""

    def __init__(self, collections: dict[str, CollectionProtocol]) -> None:
        self._collections = collections

    def iter_entities(
        self,
        *,
        entity_type: str,
        query: dict[str, Any] | None = None,
        projection: dict[str, int] | None = None,
    ) -> list[dict[str, Any]]:
        collection = self._collections.get(entity_type)
        if collection is None:
            return []
        cursor = collection.find(query or {}, projection)
        cursor = cursor.sort("name", ASCENDING)
        return list(cursor)

    def find_by_sku(self, *, entity_type: str, sku: str) -> dict[str, Any] | None:
        collection = self._collections.get(entity_type)
        if collection is None:
            return None
        return collection.find_one({"sku": sku})

    def upsert_entity(self, *, entity_type: str, document: dict[str, Any]) -> None:
        collection = self._collections.get(entity_type)
        if collection is None:
            return
        collection.update_one({"sku": document["sku"]}, {"$set": document}, upsert=True)