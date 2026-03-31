from pydantic import BaseModel, Field


class MatchRequest(BaseModel):
    use_case: str = Field(min_length=1)
    resolution: str = Field(min_length=1)
    budget: float | None = Field(default=None, gt=0)
    owned_cpu_sku: str | None = None
    owned_gpu_sku: str | None = None
    limit: int = Field(default=10, ge=1, le=20)
    include_review_consensus: bool = False
    review_consensus_limit: int = Field(default=1, ge=1, le=3)


class MatchComponentResponse(BaseModel):
    sku: str
    name: str
    ranking_percentile: float
    price: float | None = None


class MatchReviewReferenceResponse(BaseModel):
    title: str
    url: str
    channel: str | None = None

class MatchReviewedGameResponse(BaseModel):
    name: str
    resolution: str | None = None
    avg_fps: float | None = None


class MatchReviewConsensusResponse(BaseModel):
    insight: str
    warnings: list[str]
    confidence: str
    references: list[MatchReviewReferenceResponse]
    source_count: int
    average_explicit_fps: float | None = None
    tested_games: list[MatchReviewedGameResponse] = []


class MatchReviewConsensusLookupResponse(BaseModel):
    status: str
    reason: str | None = None
    review_consensus: MatchReviewConsensusResponse | None = None


class MatchItemResponse(BaseModel):
    cpu: MatchComponentResponse
    gpu: MatchComponentResponse
    score: float
    label: str
    purchase_price: float | None = None
    pair_price: float | None = None
    reasons: list[str]
    review_consensus: MatchReviewConsensusResponse | None = None
    review_consensus_status: str = "not_requested"
    review_consensus_reason: str | None = None


class MatchListResponse(BaseModel):
    items: list[MatchItemResponse]
    total: int


class MatchReviewConsensusRequest(BaseModel):
    cpu_sku: str = Field(min_length=1)
    gpu_sku: str = Field(min_length=1)
    refresh: bool = False


class MatchReviewConsensusLookupDetailResponse(BaseModel):
    cpu_sku: str
    gpu_sku: str
    lookup: MatchReviewConsensusLookupResponse
