from fastapi import APIRouter, Depends, HTTPException
from pymongo.collection import Collection

from app.core.database import get_cpu_collection, get_daily_offer_collection, get_gpu_collection
from app.repositories.cpu_repository import CpuRepository
from app.repositories.daily_offer_repository import DailyOfferRepository
from app.repositories.gpu_repository import GpuRepository
from app.schemas.cpu import CpuListItem
from app.schemas.daily_offer import DailyOffer
from app.schemas.gpu import GpuListItem
from app.schemas.match import (
    MatchComponentResponse,
    MatchItemResponse,
    MatchListResponse,
    MatchRequest,
)
from app.services.match_service import (
    CpuMatchCandidate,
    GpuMatchCandidate,
    MatchQuery,
    MatchResult,
    MatchService,
    OfferSnapshot,
)


router = APIRouter(prefix="/matches", tags=["matches"])


def get_match_service() -> MatchService:
    return MatchService()


def get_cpu_repository(
    collection: Collection = Depends(get_cpu_collection),
) -> CpuRepository:
    return CpuRepository(collection)


def get_gpu_repository(
    collection: Collection = Depends(get_gpu_collection),
) -> GpuRepository:
    return GpuRepository(collection)


def get_daily_offer_repository(
    collection: Collection = Depends(get_daily_offer_collection),
) -> DailyOfferRepository:
    return DailyOfferRepository(collection)


@router.post("", response_model=MatchListResponse)
def list_matches(
    request: MatchRequest,
    service: MatchService = Depends(get_match_service),
    cpu_repository: CpuRepository = Depends(get_cpu_repository),
    gpu_repository: GpuRepository = Depends(get_gpu_repository),
    daily_offer_repository: DailyOfferRepository = Depends(get_daily_offer_repository),
) -> MatchListResponse:
    cpu_candidates = [_to_cpu_match_candidate(item) for item in cpu_repository.list_cpus()]
    gpu_candidates = [_to_gpu_match_candidate(item) for item in gpu_repository.list_gpus()]
    offer_snapshots = [
        *[_to_offer_snapshot(offer) for offer in daily_offer_repository.list_today(entity_type="cpu")],
        *[_to_offer_snapshot(offer) for offer in daily_offer_repository.list_today(entity_type="gpu")],
    ]

    try:
        matches = service.find_matches(
            cpus=cpu_candidates,
            gpus=gpu_candidates,
            offers=offer_snapshots,
            query=MatchQuery(
                use_case=request.use_case,
                resolution=request.resolution,
                budget=request.budget,
                owned_cpu_sku=request.owned_cpu_sku,
                owned_gpu_sku=request.owned_gpu_sku,
                limit=request.limit,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return MatchListResponse(
        items=[_to_match_item_response(match) for match in matches],
        total=len(matches),
    )


def _to_cpu_match_candidate(item: CpuListItem) -> CpuMatchCandidate:
    return CpuMatchCandidate(
        sku=item.sku,
        name=item.name,
        ranking_percentile=item.ranking.game_percentile if item.ranking is not None else None,
    )


def _to_gpu_match_candidate(item: GpuListItem) -> GpuMatchCandidate:
    return GpuMatchCandidate(
        sku=item.sku,
        name=item.name,
        ranking_percentile=item.ranking.game_percentile if item.ranking is not None else None,
        memory_size_mb=item.memory_size_mb,
    )


def _to_offer_snapshot(item: DailyOffer) -> OfferSnapshot:
    return OfferSnapshot(
        entity_type=item.entity_type,
        entity_sku=item.entity_sku,
        business_date=item.business_date,
        price_card=item.price_card,
        lowest_price_90d=item.lowest_price_90d,
        median_price_90d=item.median_price_90d,
    )


def _to_match_item_response(item: MatchResult) -> MatchItemResponse:
    return MatchItemResponse(
        cpu=MatchComponentResponse(
            sku=item.cpu.sku,
            name=item.cpu.name,
            ranking_percentile=item.cpu.ranking_percentile,
            price=item.cpu.price,
        ),
        gpu=MatchComponentResponse(
            sku=item.gpu.sku,
            name=item.gpu.name,
            ranking_percentile=item.gpu.ranking_percentile,
            price=item.gpu.price,
        ),
        score=item.score,
        label=item.label,
        purchase_price=item.purchase_price,
        pair_price=item.pair_price,
        reasons=list(item.reasons),
    )
