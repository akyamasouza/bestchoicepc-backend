from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pymongo.collection import Collection

from app.core.database import (
    get_cpu_collection,
    get_daily_offer_collection,
    get_gpu_collection,
    get_review_consensus_cache_collection,
)
from app.repositories.cpu_repository import CpuRepository
from app.repositories.daily_offer_repository import DailyOfferRepository
from app.repositories.gpu_repository import GpuRepository
from app.repositories.review_consensus_cache_repository import ReviewConsensusCacheRepository
from app.schemas.cpu import CpuListItem
from app.schemas.daily_offer import DailyOffer
from app.schemas.gpu import GpuListItem
from app.schemas.match import (
    MatchComponentResponse,
    MatchItemResponse,
    MatchListResponse,
    MatchReviewedGameResponse,
    MatchReviewConsensusLookupDetailResponse,
    MatchReviewConsensusLookupResponse,
    MatchReviewConsensusRequest,
    MatchReviewConsensusResponse,
    MatchReviewReferenceResponse,
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
from app.services.youtube_review_consensus import MatchReviewConsensus, YoutubeReviewConsensusService
from app.services.review_consensus_lookup import ReviewConsensusLookup, ReviewConsensusLookupService


router = APIRouter(prefix="/matches", tags=["matches"])


def get_match_service() -> MatchService:
    return MatchService()


def get_youtube_review_consensus_service() -> YoutubeReviewConsensusService:
    return YoutubeReviewConsensusService()


def get_review_consensus_cache_repository(
    collection: Collection = Depends(get_review_consensus_cache_collection),
) -> ReviewConsensusCacheRepository:
    return ReviewConsensusCacheRepository(collection)


def get_review_consensus_lookup_service(
    repository: ReviewConsensusCacheRepository = Depends(get_review_consensus_cache_repository),
    youtube_review_consensus_service: YoutubeReviewConsensusService = Depends(get_youtube_review_consensus_service),
) -> ReviewConsensusLookupService:
    return ReviewConsensusLookupService(repository, youtube_review_consensus_service)


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
    background_tasks: BackgroundTasks,
    service: MatchService = Depends(get_match_service),
    review_consensus_lookup_service: ReviewConsensusLookupService = Depends(get_review_consensus_lookup_service),
    cpu_repository: CpuRepository = Depends(get_cpu_repository),
    gpu_repository: GpuRepository = Depends(get_gpu_repository),
    daily_offer_repository: DailyOfferRepository = Depends(get_daily_offer_repository),
) -> MatchListResponse:
    cpu_candidates = [
        _to_cpu_match_candidate(item)
        for item in cpu_repository.list_match_candidates(sku=request.owned_cpu_sku)
    ]
    gpu_candidates = [
        _to_gpu_match_candidate(item)
        for item in gpu_repository.list_match_candidates(sku=request.owned_gpu_sku)
    ]

    if request.owned_cpu_sku is not None and not cpu_candidates:
        raise HTTPException(status_code=400, detail=f"CPU ownada nao encontrada: {request.owned_cpu_sku}")
    if request.owned_gpu_sku is not None and not gpu_candidates:
        raise HTTPException(status_code=400, detail=f"GPU ownada nao encontrada: {request.owned_gpu_sku}")

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

    review_consensus_lookup_by_pair: dict[tuple[str, str], ReviewConsensusLookup] = {}
    if request.include_review_consensus:
        for match in matches[: request.review_consensus_limit]:
            review_consensus_lookup_by_pair[(match.cpu.sku, match.gpu.sku)] = review_consensus_lookup_service.get_or_start_lookup(
                cpu_sku=match.cpu.sku,
                cpu_name=match.cpu.name,
                gpu_sku=match.gpu.sku,
                gpu_name=match.gpu.name,
                background_tasks=background_tasks,
            )

    return MatchListResponse(
        items=[
            _to_match_item_response(
                match,
                review_consensus_lookup=review_consensus_lookup_by_pair.get((match.cpu.sku, match.gpu.sku)),
            )
            for match in matches
        ],
        total=len(matches),
    )


@router.post("/review-consensus", response_model=MatchReviewConsensusLookupDetailResponse)
def get_match_review_consensus(
    request: MatchReviewConsensusRequest,
    background_tasks: BackgroundTasks,
    review_consensus_lookup_service: ReviewConsensusLookupService = Depends(get_review_consensus_lookup_service),
    cpu_repository: CpuRepository = Depends(get_cpu_repository),
    gpu_repository: GpuRepository = Depends(get_gpu_repository),
) -> MatchReviewConsensusLookupDetailResponse:
    cpu_candidates = cpu_repository.list_match_candidates(sku=request.cpu_sku)
    gpu_candidates = gpu_repository.list_match_candidates(sku=request.gpu_sku)

    if not cpu_candidates:
        raise HTTPException(status_code=400, detail=f"CPU nao encontrada: {request.cpu_sku}")
    if not gpu_candidates:
        raise HTTPException(status_code=400, detail=f"GPU nao encontrada: {request.gpu_sku}")

    cpu = cpu_candidates[0]
    gpu = gpu_candidates[0]
    lookup = review_consensus_lookup_service.get_or_start_lookup(
        cpu_sku=cpu.sku,
        cpu_name=cpu.name,
        gpu_sku=gpu.sku,
        gpu_name=gpu.name,
        background_tasks=background_tasks,
        force_refresh=request.refresh,
    )

    return MatchReviewConsensusLookupDetailResponse(
        cpu_sku=cpu.sku,
        gpu_sku=gpu.sku,
        lookup=_to_review_consensus_lookup_response(lookup),
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


def _to_match_item_response(
    item: MatchResult,
    *,
    review_consensus_lookup: ReviewConsensusLookup | None = None,
) -> MatchItemResponse:
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
        review_consensus=_to_review_consensus_response(
            review_consensus_lookup.review_consensus if review_consensus_lookup is not None else None
        ),
        review_consensus_status=review_consensus_lookup.status if review_consensus_lookup is not None else "not_requested",
        review_consensus_reason=review_consensus_lookup.reason if review_consensus_lookup is not None else None,
    )


def _to_review_consensus_response(
    value: MatchReviewConsensus | None,
) -> MatchReviewConsensusResponse | None:
    if value is None:
        return None

    return MatchReviewConsensusResponse(
        insight=value.insight,
        warnings=list(value.warnings),
        confidence=value.confidence,
        references=[
            MatchReviewReferenceResponse(
                title=reference.title,
                url=reference.url,
                channel=reference.channel,
            )
            for reference in value.references
        ],
        source_count=value.source_count,
        average_explicit_fps=value.average_explicit_fps,
        tested_games=[
            MatchReviewedGameResponse(
                name=game.name,
                resolution=game.resolution,
                avg_fps=game.avg_fps,
            )
            for game in value.tested_games
        ],
    )


def _to_review_consensus_lookup_response(
    value: ReviewConsensusLookup,
) -> MatchReviewConsensusLookupResponse:
    return MatchReviewConsensusLookupResponse(
        status=value.status,
        reason=value.reason,
        review_consensus=_to_review_consensus_response(value.review_consensus),
    )
