from pydantic import BaseModel, Field

from app.schemas.common import MatchResolution, MatchUseCase


class MatchRequest(BaseModel):
    use_case: MatchUseCase
    resolution: MatchResolution
    budget: float | None = Field(default=None, gt=0)
    owned_cpu_id: str | None = Field(default=None, min_length=1, max_length=64)
    owned_gpu_id: str | None = Field(default=None, min_length=1, max_length=64)
    limit: int = Field(default=10, ge=1, le=20)


class MatchComponentResponse(BaseModel):
    id: str
    name: str
    ranking_percentile: float
    price: float | None = None


class MatchItemResponse(BaseModel):
    cpu: MatchComponentResponse
    gpu: MatchComponentResponse
    score: float
    label: str
    purchase_price: float | None = None
    pair_price: float | None = None
    reasons: list[str]


class MatchListResponse(BaseModel):
    items: list[MatchItemResponse]
    total: int

