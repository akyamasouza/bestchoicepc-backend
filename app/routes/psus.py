from typing import Literal

from fastapi import APIRouter, Depends, Query
from pymongo.collection import Collection

from app.core.database import get_psu_collection
from app.repositories.psu_repository import PsuRepository
from app.schemas.psu import PsuListResponse, PsuRankingListResponse


router = APIRouter(prefix="/psus", tags=["psus"])


def get_psu_repository(
    collection: Collection = Depends(get_psu_collection),
) -> PsuRepository:
    return PsuRepository(collection)


@router.get("", response_model=PsuListResponse)
def list_psus(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    repository: PsuRepository = Depends(get_psu_repository),
) -> PsuListResponse:
    return repository.list_psus(
        page=page,
        limit=limit,
    )


@router.get("/rankings", response_model=PsuRankingListResponse)
def list_psu_rankings(
    sort: Literal["asc", "desc"] = Query(default="desc"),
    brand: str | None = Query(default=None),
    wattage_w: int | None = Query(default=None, ge=1),
    form_factor: str | None = Query(default=None),
    atx_version: str | None = Query(default=None),
    performance_tier: str | None = Query(default=None, min_length=1, max_length=1),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    repository: PsuRepository = Depends(get_psu_repository),
) -> PsuRankingListResponse:
    return repository.list_rankings(
        sort=sort,
        brand=brand,
        wattage_w=wattage_w,
        form_factor=form_factor,
        atx_version=atx_version,
        performance_tier=performance_tier,
        q=q,
        page=page,
        limit=limit,
    )
