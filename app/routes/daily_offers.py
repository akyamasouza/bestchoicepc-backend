from fastapi import APIRouter, Depends, Query
from pymongo.collection import Collection

from app.core.database import get_daily_offer_collection
from app.repositories.daily_offer_repository import DailyOfferRepository
from app.schemas.daily_offer import DailyOffer


router = APIRouter(prefix="/daily-offers", tags=["daily-offers"])


def get_daily_offer_repository(
    collection: Collection = Depends(get_daily_offer_collection),
) -> DailyOfferRepository:
    return DailyOfferRepository(collection)


@router.get("", response_model=list[DailyOffer])
def list_today_daily_offers(
    entity_type: str | None = Query(default=None),
    repository: DailyOfferRepository = Depends(get_daily_offer_repository),
) -> list[DailyOffer]:
    return repository.list_today(entity_type=entity_type)
