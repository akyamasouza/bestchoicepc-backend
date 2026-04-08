from __future__ import annotations

from typing import Literal


EntityType = Literal["cpu", "gpu", "ssd", "ram", "psu", "motherboard"]
MatchUseCase = Literal[
    "competitive",
    "competitivo",
    "aaa",
    "hybrid",
    "jogar-e-trabalhar",
    "jogar e trabalhar",
    "mixed",
    "value",
    "custo-beneficio",
    "custo benefício",
    "best_cost_benefit",
]
MatchResolution = Literal["1080", "1080p", "1440", "1440p", "4k", "2160p"]
PerformanceTier = Literal["S", "A", "B", "C", "D"]
