from typing import Literal

from fastapi import APIRouter, Depends, Query

from app.core.database import coerce_document_id, get_cpu_collection
from app.repositories.cpu_repository import CpuRepository
from app.repositories.protocols import CollectionProtocol
from app.schemas.common import PerformanceTier
from app.schemas.cpu import CpuListResponse, CpuRankingListResponse


router = APIRouter(prefix="/cpus", tags=["cpus"])


def get_cpu_repository(
    collection: CollectionProtocol = Depends(get_cpu_collection),
) -> CpuRepository:
    return CpuRepository(collection, document_id_coercer=coerce_document_id)


@router.get("", response_model=CpuListResponse)
def list_cpus(
    brand: str | None = Query(default=None, min_length=1, max_length=80),
    socket: str | None = Query(default=None, min_length=1, max_length=80),
    q: str | None = Query(default=None, min_length=1, max_length=120),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    repository: CpuRepository = Depends(get_cpu_repository),
) -> CpuListResponse:
    return repository.list_cpus(
        brand=brand,
        socket=socket,
        q=q,
        page=page,
        limit=limit,
    )


@router.get("/rankings", response_model=CpuRankingListResponse)
def list_cpu_rankings(
    sort: Literal["asc", "desc"] = Query(default="desc"),
    brand: str | None = Query(default=None, min_length=1, max_length=80),
    release_year: int | None = Query(default=None, ge=2000, le=2100),
    performance_tier: PerformanceTier | None = Query(default=None),
    q: str | None = Query(default=None, min_length=1, max_length=120),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    repository: CpuRepository = Depends(get_cpu_repository),
) -> CpuRankingListResponse:
    return repository.list_rankings(
        sort=sort,
        brand=brand,
        release_year=release_year,
        performance_tier=performance_tier,
        q=q,
        page=page,
        limit=limit,
    )
