from fastapi import APIRouter, Depends, Query

from app.core.database import get_ram_collection
from app.repositories.ram_repository import RamRepository
from app.repositories.protocols import CollectionProtocol
from app.schemas.ram import RamListResponse


router = APIRouter(prefix="/rams", tags=["rams"])


def get_ram_repository(
    collection: CollectionProtocol = Depends(get_ram_collection),
) -> RamRepository:
    return RamRepository(collection)


@router.get("", response_model=RamListResponse)
def list_rams(
    brand: str | None = Query(default=None),
    generation: str | None = Query(default=None),
    form_factor: str | None = Query(default=None),
    device: str | None = Query(default=None),
    capacity_gb: int | None = Query(default=None, ge=1),
    module_count: int | None = Query(default=None, ge=1),
    speed_mhz: int | None = Query(default=None, ge=1),
    profile: str | None = Query(default=None),
    rgb: bool | None = Query(default=None),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    repository: RamRepository = Depends(get_ram_repository),
) -> RamListResponse:
    return repository.list_rams(
        brand=brand,
        generation=generation,
        form_factor=form_factor,
        device=device,
        capacity_gb=capacity_gb,
        module_count=module_count,
        speed_mhz=speed_mhz,
        profile=profile,
        rgb=rgb,
        q=q,
        page=page,
        limit=limit,
    )
