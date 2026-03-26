from fastapi import APIRouter, Depends
from pymongo.collection import Collection

from app.core.database import get_daily_cpu_offer_collection
from app.repositories.daily_cpu_offer_repository import DailyCpuOfferRepository
from app.schemas.daily_cpu_offer import DailyCpuOffer


router = APIRouter(prefix="/daily-cpu-offers", tags=["daily-cpu-offers"])


def get_daily_cpu_offer_repository(
    collection: Collection = Depends(get_daily_cpu_offer_collection),
) -> DailyCpuOfferRepository:
    return DailyCpuOfferRepository(collection)


@router.get("", response_model=list[DailyCpuOffer])
def list_today_daily_cpu_offers(
    repository: DailyCpuOfferRepository = Depends(get_daily_cpu_offer_repository),
) -> list[DailyCpuOffer]:
    return repository.list_today()
