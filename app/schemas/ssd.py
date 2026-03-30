from pydantic import BaseModel


class SsdBenchmark(BaseModel):
    ssd_tester_score: int | None = None


class SsdRanking(BaseModel):
    game_score: float | None = None
    game_percentile: float | None = None
    performance_tier: str | None = None


class SsdListItem(BaseModel):
    id: str
    name: str
    sku: str
    brand: str
    capacity_gb: int | None = None
    interface: str | None = None
    nand: str | None = None
    dram: bool | None = None
    benchmark: SsdBenchmark | None = None
    ranking: SsdRanking | None = None


class SsdListResponse(BaseModel):
    items: list[SsdListItem]
    page: int
    limit: int
    total: int


class SsdRankingListItem(BaseModel):
    id: str
    name: str
    sku: str
    brand: str
    capacity_gb: int | None = None
    interface: str | None = None
    ranking: SsdRanking | None = None


class SsdRankingListResponse(BaseModel):
    items: list[SsdRankingListItem]
    page: int
    limit: int
    total: int
