"""Unified domain models — single source of truth (Pydantic v2)."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Match models (replace dataclasses from match_service.py)
# ---------------------------------------------------------------------------

class CpuMatchCandidate(BaseModel, frozen=True):
    id: str
    name: str
    ranking_percentile: float | None


class GpuMatchCandidate(BaseModel, frozen=True):
    id: str
    name: str
    ranking_percentile: float | None
    memory_size_mb: int | None = None


class OfferSnapshot(BaseModel, frozen=True):
    entity_type: str
    entity_id: str
    business_date: str
    price_card: float
    lowest_price_90d: float | None = None
    median_price_90d: float | None = None


class MatchQuery(BaseModel, frozen=True):
    use_case: str
    resolution: str
    budget: float | None = None
    owned_cpu_id: str | None = None
    owned_gpu_id: str | None = None
    limit: int = 10


class MatchComponent(BaseModel, frozen=True):
    id: str
    name: str
    ranking_percentile: float
    price: float | None


class MatchResult(BaseModel, frozen=True):
    cpu: MatchComponent
    gpu: MatchComponent
    score: float
    label: str
    purchase_price: float | None
    pair_price: float | None
    reasons: tuple[str, ...]


# ---------------------------------------------------------------------------
# Scoring models (replace dataclasses from match_scoring.py)
# ---------------------------------------------------------------------------

class _ResolvedOffer(BaseModel, frozen=True):
    price: float
    lowest_price_90d: float | None
    median_price_90d: float | None


class ScoringBreakdown(BaseModel, frozen=True):
    cpu_score: float
    gpu_score: float
    cpu_soft_cap: float
    gpu_soft_cap: float
    cpu_price: float | None
    gpu_price: float | None
    pair_price: float | None
    purchase_price: float | None
    strength_score: float
    balance_score: float
    value_score: float
    market_score: float
    resolution_fit_score: float
    vram_score: float
    score: float
    label: str


# ---------------------------------------------------------------------------
# Ranking models (replace dataclass from benchmark_ranking.py)
# ---------------------------------------------------------------------------

class BenchmarkRanking(BaseModel, frozen=True):
    game_score: float
    game_percentile: float
    performance_tier: str