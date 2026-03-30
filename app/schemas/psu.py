from pydantic import BaseModel


class PsuBenchmark(BaseModel):
    cybenetics_score: float | None = None


class PsuRanking(BaseModel):
    game_score: float | None = None
    game_percentile: float | None = None
    performance_tier: str | None = None


class PsuListItem(BaseModel):
    id: str
    name: str
    sku: str
    brand: str
    wattage_w: int | None = None
    form_factor: str | None = None
    atx_version: str | None = None
    efficiency_rating: str | None = None
    noise_rating: str | None = None
    benchmark: PsuBenchmark | None = None
    ranking: PsuRanking | None = None


class PsuListResponse(BaseModel):
    items: list[PsuListItem]
    page: int
    limit: int
    total: int


class PsuRankingListItem(BaseModel):
    id: str
    name: str
    sku: str
    brand: str
    wattage_w: int | None = None
    form_factor: str | None = None
    atx_version: str | None = None
    efficiency_rating: str | None = None
    noise_rating: str | None = None
    ranking: PsuRanking | None = None


class PsuRankingListResponse(BaseModel):
    items: list[PsuRankingListItem]
    page: int
    limit: int
    total: int
