from fastapi import APIRouter, Depends
from pymongo.collection import Collection

from app.core.database import get_gpu_collection
from app.repositories.gpu_repository import GpuRepository
from app.schemas.gpu import GpuListItem


router = APIRouter(prefix="/gpus", tags=["gpus"])


def get_gpu_repository(
    collection: Collection = Depends(get_gpu_collection),
) -> GpuRepository:
    return GpuRepository(collection)


@router.get("", response_model=list[GpuListItem])
def list_gpus(repository: GpuRepository = Depends(get_gpu_repository)) -> list[GpuListItem]:
    return repository.list_gpus()
