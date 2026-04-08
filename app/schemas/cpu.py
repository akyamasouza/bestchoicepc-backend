from pydantic import BaseModel

from app.schemas.common import PerformanceTier


class CpuBenchmark(BaseModel):
    multithread_rating: int | None = None
    single_thread_rating: int | None = None
    techpowerup_relative_performance_applications: float | None = None
    samples: int | None = None
    margin_for_error: str | None = None


class CpuRanking(BaseModel):
    game_score: float | None = None
    game_percentile: float | None = None
    performance_tier: PerformanceTier | None = None


class CpuListItem(BaseModel):
    id: str
    name: str
    sku: str
    socket: str | None = None
    cores: int | None = None
    threads: int | None = None
    benchmark: CpuBenchmark | None = None
    ranking: CpuRanking | None = None


class CpuListResponse(BaseModel):
    items: list[CpuListItem]
    page: int
    limit: int
    total: int


class CpuRankingListItem(BaseModel):
    id: str
    name: str
    sku: str
    brand: str
    release_year: int | None = None
    ranking: CpuRanking | None = None


class CpuRankingListResponse(BaseModel):
    items: list[CpuRankingListItem]
    page: int
    limit: int
    total: int
