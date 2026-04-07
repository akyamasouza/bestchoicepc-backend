from fastapi import APIRouter, Depends, Query

from app.core.database import get_motherboard_collection
from app.repositories.motherboard_repository import MotherboardRepository
from app.repositories.protocols import CollectionProtocol
from app.schemas.motherboard import MotherboardListResponse


router = APIRouter(prefix="/motherboards", tags=["motherboards"])


def get_motherboard_repository(
    collection: CollectionProtocol = Depends(get_motherboard_collection),
) -> MotherboardRepository:
    return MotherboardRepository(collection)


@router.get("", response_model=MotherboardListResponse)
def list_motherboards(
    brand: str | None = Query(default=None),
    cpu_brand: str | None = Query(default=None),
    socket: str | None = Query(default=None),
    chipset: str | None = Query(default=None),
    form_factor: str | None = Query(default=None),
    memory_generation: str | None = Query(default=None),
    wifi: bool | None = Query(default=None),
    bluetooth: bool | None = Query(default=None),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    repository: MotherboardRepository = Depends(get_motherboard_repository),
) -> MotherboardListResponse:
    return repository.list_motherboards(
        brand=brand,
        cpu_brand=cpu_brand,
        socket=socket,
        chipset=chipset,
        form_factor=form_factor,
        memory_generation=memory_generation,
        wifi=wifi,
        bluetooth=bluetooth,
        q=q,
        page=page,
        limit=limit,
    )
