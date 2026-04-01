from __future__ import annotations

from dataclasses import dataclass
from math import log


@dataclass(frozen=True, slots=True)
class CpuMatchCandidate:
    id: str
    name: str
    ranking_percentile: float | None



@dataclass(frozen=True, slots=True)
class GpuMatchCandidate:
    id: str
    name: str
    ranking_percentile: float | None
    memory_size_mb: int | None = None



@dataclass(frozen=True, slots=True)
class OfferSnapshot:
    entity_type: str
    entity_sku: str
    business_date: str
    price_card: float
    lowest_price_90d: float | None = None
    median_price_90d: float | None = None


@dataclass(frozen=True, slots=True)
class MatchQuery:
    use_case: str
    resolution: str
    budget: float | None = None
    owned_cpu_id: str | None = None
    owned_gpu_id: str | None = None
    limit: int = 10



@dataclass(frozen=True, slots=True)
class MatchComponent:
    id: str
    sku: str
    name: str
    ranking_percentile: float
    price: float | None



@dataclass(frozen=True, slots=True)
class MatchResult:
    cpu: MatchComponent
    gpu: MatchComponent
    score: float
    label: str
    purchase_price: float | None
    pair_price: float | None
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _ResolvedOffer:
    price: float
    lowest_price_90d: float | None
    median_price_90d: float | None


class MatchService:
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
    # Candidatos abaixo deste percentil nunca atingem score relevante em nenhum use_case
    _MINIMUM_PERCENTILE_THRESHOLD = 20.0

    def find_matches(
        self,
        *,
        cpus: list[CpuMatchCandidate],
        gpus: list[GpuMatchCandidate],
        offers: list[OfferSnapshot],
        query: MatchQuery,
    ) -> list[MatchResult]:
        normalized_use_case = self._normalize_use_case(query.use_case)
        normalized_resolution = self._normalize_resolution(query.resolution)

        available_cpus = [
            cpu for cpu in cpus
            if cpu.ranking_percentile is not None
            and cpu.ranking_percentile >= self._MINIMUM_PERCENTILE_THRESHOLD
        ]
        available_gpus = [
            gpu for gpu in gpus
            if gpu.ranking_percentile is not None
            and gpu.ranking_percentile >= self._MINIMUM_PERCENTILE_THRESHOLD
        ]
        if not available_cpus or not available_gpus:
            return []

        if query.owned_cpu_id is not None:
            available_cpus = self._restrict_to_owned_cpu(available_cpus, query.owned_cpu_id)
        if query.owned_gpu_id is not None:
            available_gpus = self._restrict_to_owned_gpu(available_gpus, query.owned_gpu_id)

        resolved_offers = self._resolve_offers(offers)
        cpu_value_index = self._build_value_index(
            candidates=available_cpus,
            entity_type="cpu",
            resolved_offers=resolved_offers,
        )
        gpu_value_index = self._build_value_index(
            candidates=available_gpus,
            entity_type="gpu",
            resolved_offers=resolved_offers,
        )

        # Pre-filtra pares cujo preco de compra ja excede o budget antes de calcular scores
        if query.budget is not None:
            available_cpus, available_gpus = self._prefilter_by_budget(
                cpus=available_cpus,
                gpus=available_gpus,
                resolved_offers=resolved_offers,
                budget=query.budget,
                owned_cpu_id=query.owned_cpu_id,
                owned_gpu_id=query.owned_gpu_id,
            )
            if not available_cpus or not available_gpus:
                return []

        results: list[MatchResult] = []

        for cpu in available_cpus:
            for gpu in available_gpus:
                result = self._build_result(
                    cpu=cpu,
                    gpu=gpu,
                    query=query,
                    use_case=normalized_use_case,
                    resolution=normalized_resolution,
                    resolved_offers=resolved_offers,
                    cpu_value_index=cpu_value_index,
                    gpu_value_index=gpu_value_index,
                )
                if result is not None:
                    results.append(result)

        results.sort(key=lambda item: (-item.score, item.purchase_price or float("inf"), item.cpu.name, item.gpu.name))
        return results[: query.limit]

    def _build_result(
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
    ) -> MatchResult | None:
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

        weights = self._FINAL_SCORE_WEIGHTS[use_case]
        weighted_score = (
            weights[0] * strength_score
            + weights[1] * balance_score
            + weights[2] * resolution_fit_score
            + weights[3] * value_score
            + weights[4] * market_score
        )
        score = round(weighted_score * 0.9 + vram_score * 0.1, 2)

        return MatchResult(
            cpu=MatchComponent(
                id=cpu.id,
                name=cpu.name,
                ranking_percentile=cpu_score,
                price=cpu_offer.price if cpu_offer is not None else None,
            ),
            gpu=MatchComponent(
                id=gpu.id,
                name=gpu.name,
                ranking_percentile=gpu_score,
                price=gpu_offer.price if gpu_offer is not None else None,
            ),

            score=score,
            label=self._label_for_score(score),
            purchase_price=purchase_price,
            pair_price=pair_price,
            reasons=self._build_reasons(
                cpu=cpu,
                gpu=gpu,
                query=query,
                resolution=resolution,
                balance_score=balance_score,
                resolution_fit_score=resolution_fit_score,
                market_score=market_score,
                vram_score=vram_score,
                use_case=use_case,
            ),
        )

    @staticmethod
    def _restrict_to_owned_cpu(cpus: list[CpuMatchCandidate], owned_cpu_id: str) -> list[CpuMatchCandidate]:
        owned = [cpu for cpu in cpus if cpu.id == owned_cpu_id]
        if not owned:
            raise ValueError(f"CPU ownada nao encontrada: {owned_cpu_id}")
        return owned


    @staticmethod
    def _restrict_to_owned_gpu(gpus: list[GpuMatchCandidate], owned_gpu_id: str) -> list[GpuMatchCandidate]:
        owned = [gpu for gpu in gpus if gpu.id == owned_gpu_id]
        if not owned:
            raise ValueError(f"GPU ownada nao encontrada: {owned_gpu_id}")
        return owned


    @staticmethod
    def _prefilter_by_budget(
        *,
        cpus: list[CpuMatchCandidate],
        gpus: list[GpuMatchCandidate],
        resolved_offers: dict[tuple[str, str], _ResolvedOffer],
        budget: float,
        owned_cpu_id: str | None,
        owned_gpu_id: str | None,
    ) -> tuple[list[CpuMatchCandidate], list[GpuMatchCandidate]]:

        """Remove CPUs/GPUs cujo preco individual ja excede o budget disponivel,
        eliminando pares impossiveis antes do loop de scoring."""
        if owned_cpu_id is not None and owned_gpu_id is not None:
            # Ambas ownadas: purchase_price sera 0, budget nunca excedido
            return cpus, gpus


        if owned_cpu_id is not None:
            # Apenas GPU precisa caber no budget

            filtered_gpus = [
                gpu for gpu in gpus
                if (offer := resolved_offers.get(("gpu", gpu.id))) is None
                or offer.price <= budget
            ]
            return cpus, filtered_gpus

        if owned_gpu_id is not None:
            # Apenas CPU precisa caber no budget
            filtered_cpus = [
                cpu for cpu in cpus
                if (offer := resolved_offers.get(("cpu", cpu.id))) is None
                or offer.price <= budget
            ]
            return filtered_cpus, gpus

        # Ambos precisam ser comprados: filtra candidatos cujo preco sozinho ja excede o budget
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

    @classmethod
    def _normalize_use_case(cls, value: str) -> str:
        normalized = value.strip().lower()
        return cls._USE_CASE_ALIASES.get(normalized, "value")

    @classmethod
    def _normalize_resolution(cls, value: str) -> str:
        normalized = value.strip().lower()
        return cls._RESOLUTION_ALIASES.get(normalized, "1080p")

    @staticmethod
    def _resolve_offers(offers: list[OfferSnapshot]) -> dict[tuple[str, str], _ResolvedOffer]:
        resolved: dict[tuple[str, str], OfferSnapshot] = {}

        for offer in offers:
            key = (offer.entity_type.lower(), offer.entity_sku)
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

    @staticmethod
    def _build_value_index(
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

    @staticmethod
    def _pair_market_score(
        *,
        cpu_offer: _ResolvedOffer | None,
        gpu_offer: _ResolvedOffer | None,
        query: MatchQuery,
    ) -> float:
        scores: list[float] = []

        if query.owned_gpu_id is None:
            scores.append(MatchService._market_score_for_offer(cpu_offer))
        if query.owned_cpu_id is None:
            scores.append(MatchService._market_score_for_offer(gpu_offer))


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

    @staticmethod
    def _resolve_purchase_price(
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


        return MatchService._sum_prices(cpu_price, gpu_price)

    @staticmethod
    def _label_for_score(score: float) -> str:
        if score >= 85:
            return "ideal"
        if score >= 75:
            return "forte"
        if score >= 65:
            return "aceitavel"
        return "situacional"

    @staticmethod
    def _build_reasons(
        *,
        cpu: CpuMatchCandidate,
        gpu: GpuMatchCandidate,
        query: MatchQuery,
        resolution: str,
        balance_score: float,
        resolution_fit_score: float,
        market_score: float,
        vram_score: float,
        use_case: str,
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        cpu_score = float(cpu.ranking_percentile or 0.0)
        gpu_score = float(gpu.ranking_percentile or 0.0)
        targets = MatchService._RESOLUTION_FIT_TARGETS[use_case][resolution]
        cpu_cap = targets["cpu"][1]
        gpu_cap = targets["gpu"][1]

        if balance_score >= 80:
            reasons.append(f"equilibrio forte para {resolution}")
        elif cpu_score > gpu_score * 1.25:
            reasons.append("cpu acima do necessario para essa gpu")
        elif gpu_score > cpu_score * 1.35:
            reasons.append("gpu pode pedir uma cpu melhor")

        if gpu_score > gpu_cap:
            reasons.append(f"gpu acima do necessario para {resolution}")
        elif cpu_score > cpu_cap:
            reasons.append(f"cpu acima do necessario para {resolution}")
        elif resolution_fit_score >= 85:
            reasons.append(f"faixa de desempenho adequada para {resolution}")

        if market_score >= 75:
            reasons.append("preco atual bem posicionado no historico")
        elif market_score < 45:
            reasons.append("preco atual pouco atrativo no historico")

        if vram_score >= 90:
            reasons.append(f"vram adequada para {resolution}")
        elif vram_score < 60:
            reasons.append(f"vram curta para {resolution}")

        if query.owned_cpu_id is not None or query.owned_gpu_id is not None:
            reasons.append("considera reaproveitamento da sua peca atual")


        if not reasons:
            reasons.append("combo dentro de um equilibrio pratico")

        return tuple(reasons)
