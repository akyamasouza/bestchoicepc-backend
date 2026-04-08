from __future__ import annotations

from enum import StrEnum
from typing import Literal


EntityType = Literal["cpu", "gpu", "ssd", "ram", "psu", "motherboard"]


class MatchUseCase(StrEnum):
    COMPETITIVE = "competitive"
    AAA = "aaa"
    HYBRID = "hybrid"
    VALUE = "value"


_MATCH_USE_CASE_ALIASES: dict[str, MatchUseCase] = {
    "competitive": MatchUseCase.COMPETITIVE,
    "competitivo": MatchUseCase.COMPETITIVE,
    "aaa": MatchUseCase.AAA,
    "hybrid": MatchUseCase.HYBRID,
    "jogar-e-trabalhar": MatchUseCase.HYBRID,
    "jogar e trabalhar": MatchUseCase.HYBRID,
    "mixed": MatchUseCase.HYBRID,
    "value": MatchUseCase.VALUE,
    "custo-beneficio": MatchUseCase.VALUE,
    "custo benefício": MatchUseCase.VALUE,
    "best_cost_benefit": MatchUseCase.VALUE,
}


def parse_match_use_case(value: str | MatchUseCase) -> MatchUseCase:
    if isinstance(value, MatchUseCase):
        return value

    normalized = str(value).strip().lower()
    try:
        return _MATCH_USE_CASE_ALIASES[normalized]
    except KeyError as exc:
        allowed = ", ".join(use_case.value for use_case in MatchUseCase)
        raise ValueError(f"Unsupported match use case: {value}. Allowed canonical values: {allowed}") from exc


MatchResolution = Literal["1080", "1080p", "1440", "1440p", "4k", "2160p"]
PerformanceTier = Literal["S", "A", "B", "C", "D"]
