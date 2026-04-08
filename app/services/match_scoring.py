from __future__ import annotations

from dataclasses import dataclass
from math import log
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.match_service import CpuMatchCandidate, GpuMatchCandidate, MatchQuery, OfferSnapshot


@dataclass(frozen=True, slots=True)
class _ResolvedOffer:
    price: float
    lowest_price_90d: float | None
    median_price_90d: float | None


@dataclass(frozen=True, slots=True)
class ScoringBreakdown:
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


class MatchScoringPolicy:
    _USE_CASE_ALIASES = {
        "competitive": "competitive",
        "competitivo": "competitive",
        "aaa": "aaa",
        "hybrid": "hybrid",
        "jogar-e-trabalhar": "hybrid",
        "jogar e trabalhar": "hybrid",
        "mixed": "hybrid",
        "value": "value",
        "custo-beneficio": "value",
        "custo benefício": "value",
        "best_cost_benefit": "value",
    }
    _RESOLUTION_ALIASES = {
        "1080": "1080p",
        "1080p": "1080p",
        "1440": "1440p",
        "1440p": "1440p",
        "4k": "4k",
        "2160p": "4k",
    }
    _IDEAL_CPU_GPU_RATIO = {
        "competitive": {"1080p": 1.15, "1440p": 1.0, "4k": 0.85},
        "aaa": {"1080p": 1.0, "1440p": 0.88, "4k": 0.72},
        "hybrid": {"1080p": 1.05, "1440p": 0.92, "4k": 0.78},
        "value": {"1080p": 0.98, "1440p": 0.86, "4k": 0.74},
    }
    _PAIR_STRENGTH_WEIGHTS = {
        "competitive": {"1080p": (0.6, 0.4), "1440p": (0.5, 0.5), "4k": (0.35, 0.65)},
        "aaa": {"1080p": (0.45, 0.55), "1440p": (0.35, 0.65), "4k": (0.25, 0.75)},
        "hybrid": {"1080p": (0.5, 0.5), "1440p": (0.4, 0.6), "4k": (0.3, 0.7)},
        "value": {"1080p": (0.45, 0.55), "1440p": (0.35, 0.65), "4k": (0.25, 0.75)},
    }
    _RESOLUTION_FIT_TARGETS = {
        "competitive": {
            "1080p": {"cpu": (88.0, 96.0), "gpu": (76.0, 90.0)},
            "1440p": {"cpu": (82.0, 92.0), "gpu": (82.0, 92.0)},
            "4k": {"cpu": (76.0, 90.0), "gpu": (94.0, 100.0)},
        },
        "aaa": {
            "1080p": {"cpu": (78.0, 90.0), "gpu": (70.0, 84.0)},
            "1440p": {"cpu": (80.0, 90.0), "gpu": (82.0, 92.0)},
            "4k": {"cpu": (74.0, 88.0), "gpu": (95.0, 100.0)},
        },
        "hybrid": {
            "1080p": {"cpu": (82.0, 92.0), "gpu": (72.0, 86.0)},
            "1440p": {"cpu": (82.0, 92.0), "gpu": (80.0, 90.0)},
            "4k": {"cpu": (76.0, 90.0), "gpu": (92.0, 100.0)},
        },
        "value": {
            "1080p": {"cpu": (72.0, 84.0), "gpu": (62.0, 78.0)},
            "1440p": {"cpu": (76.0, 88.0), "gpu": (74.0, 88.0)},
            "4k": {"cpu": (72.0, 86.0), "gpu": (90.0, 98.0)},
        },
    }
    _FINAL_SCORE_WEIGHTS = {
        "competitive": (0.32, 0.23, 0.25, 0.1, 0.1),
        "aaa": (0.28, 0.22, 0.3, 0.1, 0.1),
        "hybrid": (0.3, 0.22, 0.28, 0.1, 0.1),
        "value": (0.2, 0.2, 0.35, 0.15, 0.1),
    }
    _MINIMUM_PERCENTILE_THRESHOLD = 20.0

    def normalize_use_case(self, value: str) -> str:
        normalized = value.strip().lower()
        return self._USE_CASE_ALIASES.get(normalized, "value")

    def normalize_resolution(self, value: str) -> str:
        normalized = value.strip().lower()
        return self._RESOLUTION_ALIASES.get(normalized, "1080p")

    def eligible_cpus(self, cpus: list[CpuMatchCandidate]) -> list[CpuMatchCandidate]:
        return [
            cpu for cpu in cpus
            if cpu.ranking_percentile is not None
            and cpu.ranking_percentile >= self._MINIMUM_PERCENTILE_THRESHOLD
        ]

    def eligible_gpus(self, gpus: list[GpuMatchCandidate]) -> list[GpuMatchCandidate]:
        return [
            gpu for gpu in gpus
            if gpu.ranking_percentile is not None
            and gpu.ranking_percentile >= self._MINIMUM_PERCENTILE_THRESHOLD
        ]

    @staticmethod
    def restrict_to_owned_cpu(cpus: list[CpuMatchCandidate], owned_cpu_id: str) -> list[CpuMatchCandidate]:
        owned = [cpu for cpu in cpus if cpu.id == owned_cpu_id]
        if not owned:
            raise ValueError(f"CPU ownada nao encontrada: {owned_cpu_id}")
        return owned

    @staticmethod
    def restrict_to_owned_gpu(gpus: list[GpuMatchCandidate], owned_gpu_id: str) -> list[GpuMatchCandidate]:
        owned = [gpu for gpu in gpus if gpu.id == owned_gpu_id]
        if not owned:
            raise ValueError(f"GPU ownada nao encontrada: {owned_gpu_id}")
        return owned

    def resolve_offers(self, offers: list[OfferSnapshot]) -> dict[tuple[str, str], _ResolvedOffer]:
        resolved: dict[tuple[str, str], OfferSnapshot] = {}

        for offer in offers:
            key = (offer.entity_type.lower(), offer.entity_id)
            current = resolved.get(key)
            if current is None:
                resolved[key] = offer
                continue

            if offer.business_date > current.business_date:
                resolved[key] = offer
                continue

            if offer.business_date == current.business_date and offer.price_card < current.price_card:
                resolved[key] = offer

        return {
            key: _ResolvedOffer(
                price=offer.price_card,
                lowest_price_90d=offer.lowest_price_90d,
                median_price_90d=offer.median_price_90d,
            )
            for key, offer in resolved.items()
        }

    def build_value_index(
        self,
        *,
        candidates: list[CpuMatchCandidate] | list[GpuMatchCandidate],
        entity_type: str,
        resolved_offers: dict[tuple[str, str], _ResolvedOffer],
    ) -> dict[str, float]:
        efficiencies: dict[str, float] = {}

        for candidate in candidates:
            offer = resolved_offers.get((entity_type, candidate.id))
            ranking_percentile = float(candidate.ranking_percentile or 0.0)
            if offer is None or offer.price <= 0:
                efficiencies[candidate.id] = 0.0
                continue

            efficiencies[candidate.id] = ranking_percentile / offer.price

        best_efficiency = max(efficiencies.values(), default=0.0)
        if best_efficiency <= 0:
            return {candidate.id: 50.0 for candidate in candidates}

        return {
            entity_id: round(max(35.0, (efficiency / best_efficiency) * 100), 2)
            for entity_id, efficiency in efficiencies.items()
        }

    def prefilter_by_budget(
        self,
        *,
        cpus: list[CpuMatchCandidate],
        gpus: list[GpuMatchCandidate],
        resolved_offers: dict[tuple[str, str], _ResolvedOffer],
        budget: float,
        owned_cpu_id: str | None,
        owned_gpu_id: str | None,
    ) -> tuple[list[CpuMatchCandidate], list[GpuMatchCandidate]]:
        if owned_cpu_id is not None and owned_gpu_id is not None:
            return cpus, gpus

        if owned_cpu_id is not None:
            filtered_gpus = [
                gpu for gpu in gpus
                if (offer := resolved_offers.get(("gpu", gpu.id))) is None
                or offer.price <= budget
            ]
            return cpus, filtered_gpus

        if owned_gpu_id is not None:
            filtered_cpus = [
                cpu for cpu in cpus
                if (offer := resolved_offers.get(("cpu", cpu.id))) is None
                or offer.price <= budget
            ]
            return filtered_cpus, gpus

        filtered_cpus = [
            cpu for cpu in cpus
            if (offer := resolved_offers.get(("cpu", cpu.id))) is None
            or offer.price <= budget
        ]
        filtered_gpus = [
            gpu for gpu in gpus
            if (offer := resolved_offers.get(("gpu", gpu.id))) is None
            or offer.price <= budget
        ]
        return filtered_cpus, filtered_gpus

    def score_pair(
        self,
        *,
        cpu: CpuMatchCandidate,
        gpu: GpuMatchCandidate,
        query: MatchQuery,
        use_case: str,
        resolution: str,
        resolved_offers: dict[tuple[str, str], _ResolvedOffer],
        cpu_value_index: dict[str, float],
        gpu_value_index: dict[str, float],
    ) -> ScoringBreakdown | None:
        cpu_offer = resolved_offers.get(("cpu", cpu.id))
        gpu_offer = resolved_offers.get(("gpu", gpu.id))

        pair_price = self._sum_prices(
            cpu_offer.price if cpu_offer is not None else None,
            gpu_offer.price if gpu_offer is not None else None,
        )
        purchase_price = self._resolve_purchase_price(
            cpu_offer=cpu_offer,
            gpu_offer=gpu_offer,
            owned_cpu_id=query.owned_cpu_id,
            owned_gpu_id=query.owned_gpu_id,
        )

        if query.budget is not None and (purchase_price is None or purchase_price > query.budget):
            return None

        cpu_score = float(cpu.ranking_percentile or 0.0)
        gpu_score = float(gpu.ranking_percentile or 0.0)
        strength_score = self._pair_strength_score(
            cpu_score=cpu_score,
            gpu_score=gpu_score,
            use_case=use_case,
            resolution=resolution,
        )
        balance_score = self._balance_score(
            cpu_score=cpu_score,
            gpu_score=gpu_score,
            use_case=use_case,
            resolution=resolution,
        )
        value_score = self._pair_value_score(
            cpu=cpu,
            gpu=gpu,
            query=query,
            cpu_value_index=cpu_value_index,
            gpu_value_index=gpu_value_index,
        )
        market_score = self._pair_market_score(
            cpu_offer=cpu_offer,
            gpu_offer=gpu_offer,
            query=query,
        )
        resolution_fit_score = self._resolution_fit_score(
            cpu_score=cpu_score,
            gpu_score=gpu_score,
            use_case=use_case,
            resolution=resolution,
        )
        vram_score = self._vram_score(memory_size_mb=gpu.memory_size_mb, resolution=resolution)
        targets = self.resolution_targets(use_case, resolution)

        weights = self._FINAL_SCORE_WEIGHTS[use_case]
        weighted_score = (
            weights[0] * strength_score
            + weights[1] * balance_score
            + weights[2] * resolution_fit_score
            + weights[3] * value_score
            + weights[4] * market_score
        )
        score = round(weighted_score * 0.9 + vram_score * 0.1, 2)

        return ScoringBreakdown(
            cpu_score=cpu_score,
            gpu_score=gpu_score,
            cpu_soft_cap=targets["cpu"][1],
            gpu_soft_cap=targets["gpu"][1],
            cpu_price=cpu_offer.price if cpu_offer is not None else None,
            gpu_price=gpu_offer.price if gpu_offer is not None else None,
            pair_price=pair_price,
            purchase_price=purchase_price,
            strength_score=strength_score,
            balance_score=balance_score,
            value_score=value_score,
            market_score=market_score,
            resolution_fit_score=resolution_fit_score,
            vram_score=vram_score,
            score=score,
            label=self.label_for_score(score),
        )

    @classmethod
    def resolution_targets(cls, use_case: str, resolution: str) -> dict[str, tuple[float, float]]:
        return cls._RESOLUTION_FIT_TARGETS[use_case][resolution]

    @staticmethod
    def label_for_score(score: float) -> str:
        if score >= 85:
            return "ideal"
        if score >= 75:
            return "forte"
        if score >= 65:
            return "aceitavel"
        return "situacional"

    @classmethod
    def _pair_strength_score(cls, *, cpu_score: float, gpu_score: float, use_case: str, resolution: str) -> float:
        cpu_weight, gpu_weight = cls._PAIR_STRENGTH_WEIGHTS[use_case][resolution]
        return round(cpu_score * cpu_weight + gpu_score * gpu_weight, 2)

    @classmethod
    def _balance_score(cls, *, cpu_score: float, gpu_score: float, use_case: str, resolution: str) -> float:
        if cpu_score <= 0 or gpu_score <= 0:
            return 0.0

        ideal_ratio = cls._IDEAL_CPU_GPU_RATIO[use_case][resolution]
        ratio = cpu_score / gpu_score
        distance = abs(log(ratio / ideal_ratio))
        return round(max(0.0, 100 - distance * 120), 2)

    @staticmethod
    def _pair_value_score(
        *,
        cpu: CpuMatchCandidate,
        gpu: GpuMatchCandidate,
        query: MatchQuery,
        cpu_value_index: dict[str, float],
        gpu_value_index: dict[str, float],
    ) -> float:
        if query.owned_cpu_id is not None and query.owned_gpu_id is not None:
            return 50.0
        if query.owned_cpu_id is not None:
            return gpu_value_index.get(gpu.id, 50.0)
        if query.owned_gpu_id is not None:
            return cpu_value_index.get(cpu.id, 50.0)

        return round((cpu_value_index.get(cpu.id, 50.0) + gpu_value_index.get(gpu.id, 50.0)) / 2, 2)

    @classmethod
    def _resolution_fit_score(cls, *, cpu_score: float, gpu_score: float, use_case: str, resolution: str) -> float:
        targets = cls._RESOLUTION_FIT_TARGETS[use_case][resolution]
        cpu_fit = cls._component_fit_score(
            score=cpu_score,
            ideal=targets["cpu"][0],
            soft_cap=targets["cpu"][1],
        )
        gpu_fit = cls._component_fit_score(
            score=gpu_score,
            ideal=targets["gpu"][0],
            soft_cap=targets["gpu"][1],
        )
        cpu_weight, gpu_weight = cls._PAIR_STRENGTH_WEIGHTS[use_case][resolution]
        return round(cpu_fit * cpu_weight + gpu_fit * gpu_weight, 2)

    @staticmethod
    def _component_fit_score(*, score: float, ideal: float, soft_cap: float) -> float:
        fit = 100 - abs(score - ideal) * 2.2
        if score > soft_cap:
            fit -= (score - soft_cap) * 4.5

        minimum_floor = max(0.0, ideal - 18)
        if score < minimum_floor:
            fit -= (minimum_floor - score) * 2.5

        return round(max(0.0, min(100.0, fit)), 2)

    @classmethod
    def _pair_market_score(
        cls,
        *,
        cpu_offer: _ResolvedOffer | None,
        gpu_offer: _ResolvedOffer | None,
        query: MatchQuery,
    ) -> float:
        scores: list[float] = []

        if query.owned_gpu_id is None:
            scores.append(cls._market_score_for_offer(cpu_offer))
        if query.owned_cpu_id is None:
            scores.append(cls._market_score_for_offer(gpu_offer))

        if not scores:
            return 50.0

        return round(sum(scores) / len(scores), 2)

    @staticmethod
    def _market_score_for_offer(offer: _ResolvedOffer | None) -> float:
        if offer is None:
            return 50.0

        current = offer.price
        lowest = offer.lowest_price_90d
        median = offer.median_price_90d

        if lowest is not None and current <= lowest:
            return 100.0

        if median is not None and current <= median:
            if lowest is None or median <= lowest:
                return 80.0

            spread = median - lowest
            proximity = 1 - ((current - lowest) / spread)
            return round(70 + max(0.0, proximity) * 20, 2)

        if median is not None and median > 0:
            premium_ratio = max(0.0, (current - median) / median)
            return round(max(20.0, 65 - premium_ratio * 100), 2)

        return 60.0

    @staticmethod
    def _vram_score(*, memory_size_mb: int | None, resolution: str) -> float:
        if memory_size_mb is None:
            return 60.0

        expected_mb = {
            "1080p": 8192,
            "1440p": 12288,
            "4k": 16384,
        }[resolution]
        if memory_size_mb >= expected_mb:
            return 100.0
        if memory_size_mb >= expected_mb * 0.75:
            return 75.0
        return 45.0

    @staticmethod
    def _sum_prices(first: float | None, second: float | None) -> float | None:
        if first is None or second is None:
            return None
        return round(first + second, 2)

    @classmethod
    def _resolve_purchase_price(
        cls,
        *,
        cpu_offer: _ResolvedOffer | None,
        gpu_offer: _ResolvedOffer | None,
        owned_cpu_id: str | None,
        owned_gpu_id: str | None,
    ) -> float | None:
        cpu_price = cpu_offer.price if cpu_offer is not None else None
        gpu_price = gpu_offer.price if gpu_offer is not None else None

        if owned_cpu_id is not None and owned_gpu_id is not None:
            return 0.0
        if owned_cpu_id is not None:
            return gpu_price
        if owned_gpu_id is not None:
            return cpu_price

        return cls._sum_prices(cpu_price, gpu_price)
