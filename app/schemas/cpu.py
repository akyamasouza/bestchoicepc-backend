from pydantic import BaseModel


class CpuBenchmark(BaseModel):
    multithread_rating: int | None = None
    single_thread_rating: int | None = None
    samples: int | None = None
    margin_for_error: str | None = None


class CpuRanking(BaseModel):
    game_score: float | None = None
    game_percentile: float | None = None
    performance_tier: str | None = None


class CpuListItem(BaseModel):
    id: str
    name: str
    sku: str
    socket: str | None = None
    cores: int | None = None
    threads: int | None = None
    benchmark: CpuBenchmark | None = None
    ranking: CpuRanking | None = None
