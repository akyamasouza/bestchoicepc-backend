from typing import Literal

from fastapi import APIRouter, Depends, Query
from pymongo.collection import Collection

from app.core.database import get_cpu_collection
from app.repositories.cpu_repository import CpuRepository
from app.schemas.cpu import CpuListItem, CpuListResponse, CpuRankingListResponse


router = APIRouter(prefix="/cpus", tags=["cpus"])


def get_cpu_repository(
    collection: Collection = Depends(get_cpu_collection),
) -> CpuRepository:
    return CpuRepository(collection)


@router.get("", response_model=CpuListResponse)
def list_cpus(
    brand: str | None = Query(default=None),
    socket: str | None = Query(default=None),
    q: str | None = Query(default=None),
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
    brand: str | None = Query(default=None),
    release_year: int | None = Query(default=None, ge=2000, le=2100),
    performance_tier: str | None = Query(default=None, min_length=1, max_length=1),
    q: str | None = Query(default=None),
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
