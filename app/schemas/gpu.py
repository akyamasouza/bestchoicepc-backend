from pydantic import BaseModel


class GpuBenchmark(BaseModel):
    g3d_mark: int | None = None
    g2d_mark: int | None = None
    samples: int | None = None


class GpuRanking(BaseModel):
    game_score: float | None = None
    game_percentile: float | None = None
    performance_tier: str | None = None


class GpuListItem(BaseModel):
    id: str
    name: str
    sku: str
    bus_interface: str | None = None
    memory_size_mb: int | None = None
    core_clock_mhz: int | None = None
    memory_clock_mhz: int | None = None
    max_tdp_w: int | None = None
    category: str | None = None
    benchmark: GpuBenchmark | None = None
    ranking: GpuRanking | None = None
