from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any, Protocol

from app.schemas.cpu import (
    CpuListItem,
    CpuListResponse,
    CpuRankingListItem,
    CpuRankingListResponse,
)
from app.schemas.gpu import (
    GpuListItem,
    GpuListResponse,
    GpuRankingListItem,
    GpuRankingListResponse,
)


ASCENDING = 1
DESCENDING = -1
DocumentIdCoercer = Callable[[str], object]


def identity_document_id(value: str) -> str:
    return value


class CursorProtocol(Protocol):
    """Contrato minimo de cursor usado pelos repositorios."""

    def sort(
        self,
        key_or_list: str | list[tuple[str, int]],
        direction: int | None = None,
    ) -> CursorProtocol: ...

    def skip(self, count: int) -> CursorProtocol: ...

    def limit(self, count: int) -> CursorProtocol: ...

    def __iter__(self) -> Iterator[dict[str, Any]]: ...


class CollectionProtocol(Protocol):
    """Contrato minimo de colecao usado pelos repositorios."""

    def count_documents(self, query: dict[str, Any]) -> int: ...

    def find(
        self,
        query: dict[str, Any],
        projection: dict[str, int] | None = None,
    ) -> CursorProtocol: ...

    def find_one(
        self,
        query: dict[str, Any],
        projection: dict[str, int] | None = None,
    ) -> dict[str, Any] | None: ...

    def create_index(
        self,
        keys: list[tuple[str, int]],
        unique: bool = False,
    ) -> Any: ...

    def update_one(
        self,
        query: dict[str, Any],
        update: dict[str, Any],
        upsert: bool = False,
    ) -> Any: ...

    def update_many(
        self,
        query: dict[str, Any],
        update: dict[str, Any],
    ) -> Any: ...

    def replace_one(
        self,
        query: dict[str, Any],
        replacement: dict[str, Any],
        upsert: bool = False,
    ) -> Any: ...


class CpuRepositoryProto(Protocol):
    """Contrato para repositorio de CPUs."""

    def list_cpus(
        self,
        *,
        brand: str | None = None,
        socket: str | None = None,
        q: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> CpuListResponse: ...

    def list_rankings(
        self,
        *,
        sort: str,
        brand: str | None = None,
        release_year: int | None = None,
        performance_tier: str | None = None,
        q: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> CpuRankingListResponse: ...

    def list_match_candidates(
        self,
        *,
        id: str | None = None,
        sku: str | None = None,
    ) -> list[CpuListItem]: ...


class GpuRepositoryProto(Protocol):
    """Contrato para repositorio de GPUs."""

    def list_gpus(
        self,
        *,
        brand: str | None = None,
        category: str | None = None,
        q: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> GpuListResponse: ...

    def list_rankings(
        self,
        *,
        sort: str,
        brand: str | None = None,
        category: str | None = None,
        release_year: int | None = None,
        performance_tier: str | None = None,
        q: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> GpuRankingListResponse: ...

    def list_match_candidates(
        self,
        *,
        id: str | None = None,
        sku: str | None = None,
    ) -> list[GpuListItem]: ...
