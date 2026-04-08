from typing import Literal

from fastapi import APIRouter, Depends, Query

from app.core.database import get_ssd_collection
from app.repositories.protocols import CollectionProtocol
from app.repositories.ssd_repository import SsdRepository
from app.schemas.common import PerformanceTier
from app.schemas.ssd import SsdListResponse, SsdRankingListResponse


router = APIRouter(prefix="/ssds", tags=["ssds"])


def get_ssd_repository(
    collection: CollectionProtocol = Depends(get_ssd_collection),
) -> SsdRepository:
    return SsdRepository(collection)


@router.get("", response_model=SsdListResponse)
def list_ssds(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    repository: SsdRepository = Depends(get_ssd_repository),
) -> SsdListResponse:
    return repository.list_ssds(
        page=page,
        limit=limit,
    )


@router.get("/rankings", response_model=SsdRankingListResponse)
def list_ssd_rankings(
    sort: Literal["asc", "desc"] = Query(default="desc"),
    brand: str | None = Query(default=None, min_length=1, max_length=80),
    capacity_gb: int | None = Query(default=None, ge=1),
    interface: str | None = Query(default=None, min_length=1, max_length=80),
    performance_tier: PerformanceTier | None = Query(default=None),
    q: str | None = Query(default=None, min_length=1, max_length=120),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    repository: SsdRepository = Depends(get_ssd_repository),
) -> SsdRankingListResponse:
    return repository.list_rankings(
        sort=sort,
        brand=brand,
        capacity_gb=capacity_gb,
        interface=interface,
        performance_tier=performance_tier,
        q=q,
        page=page,
        limit=limit,
    )
