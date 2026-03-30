from pydantic import BaseModel, Field


class MatchRequest(BaseModel):
    use_case: str = Field(min_length=1)
    resolution: str = Field(min_length=1)
    budget: float | None = Field(default=None, gt=0)
    owned_cpu_sku: str | None = None
    owned_gpu_sku: str | None = None
    limit: int = Field(default=10, ge=1, le=20)


class MatchComponentResponse(BaseModel):
    sku: str
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
