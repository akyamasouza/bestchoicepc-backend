from typing import Literal

from fastapi import APIRouter, Depends, Query

from app.core.database import coerce_document_id, get_gpu_collection
from app.repositories.gpu_repository import GpuRepository
from app.repositories.protocols import CollectionProtocol
from app.schemas.gpu import GpuListResponse, GpuRankingListResponse


router = APIRouter(prefix="/gpus", tags=["gpus"])


def get_gpu_repository(
    collection: CollectionProtocol = Depends(get_gpu_collection),
) -> GpuRepository:
    return GpuRepository(collection, document_id_coercer=coerce_document_id)


@router.get("", response_model=GpuListResponse)
def list_gpus(
    brand: str | None = Query(default=None),
    category: str | None = Query(default=None),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    repository: GpuRepository = Depends(get_gpu_repository),
) -> GpuListResponse:
    return repository.list_gpus(
        brand=brand,
        category=category,
        q=q,
        page=page,
        limit=limit,
    )


@router.get("/rankings", response_model=GpuRankingListResponse)
def list_gpu_rankings(
    sort: Literal["asc", "desc"] = Query(default="desc"),
    brand: str | None = Query(default=None),
    category: str | None = Query(default=None),
    release_year: int | None = Query(default=None, ge=2000, le=2100),
    performance_tier: str | None = Query(default=None, min_length=1, max_length=1),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    repository: GpuRepository = Depends(get_gpu_repository),
) -> GpuRankingListResponse:
    return repository.list_rankings(
        sort=sort,
        brand=brand,
        category=category,
        release_year=release_year,
        performance_tier=performance_tier,
        q=q,
        page=page,
        limit=limit,
    )
