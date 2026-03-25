from fastapi import APIRouter, Depends
from pymongo.collection import Collection

from app.core.database import get_cpu_collection
from app.repositories.cpu_repository import CpuRepository
from app.schemas.cpu import CpuListItem


router = APIRouter(prefix="/cpus", tags=["cpus"])


def get_cpu_repository(
    collection: Collection = Depends(get_cpu_collection),
) -> CpuRepository:
    return CpuRepository(collection)


@router.get("", response_model=list[CpuListItem])
def list_cpus(repository: CpuRepository = Depends(get_cpu_repository)) -> list[CpuListItem]:
    return repository.list_cpus()
