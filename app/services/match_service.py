from __future__ import annotations

from dataclasses import dataclass

from app.services.match_reasons import MatchReasonBuilder
from app.services.match_scoring import MatchScoringPolicy


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
    entity_id: str
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


class MatchService:
    def __init__(
        self,
        *,
        scoring_policy: MatchScoringPolicy | None = None,
        reason_builder: MatchReasonBuilder | None = None,
    ) -> None:
        self._scoring_policy = scoring_policy or MatchScoringPolicy()
        self._reason_builder = reason_builder or MatchReasonBuilder()

    def find_matches(
        self,
        *,
        cpus: list[CpuMatchCandidate],
        gpus: list[GpuMatchCandidate],
        offers: list[OfferSnapshot],
        query: MatchQuery,
    ) -> list[MatchResult]:
        normalized_use_case = self._scoring_policy.normalize_use_case(query.use_case)
        normalized_resolution = self._scoring_policy.normalize_resolution(query.resolution)

        available_cpus = self._scoring_policy.eligible_cpus(cpus)
        available_gpus = self._scoring_policy.eligible_gpus(gpus)
        if not available_cpus or not available_gpus:
            return []

        if query.owned_cpu_id is not None:
            available_cpus = self._scoring_policy.restrict_to_owned_cpu(available_cpus, query.owned_cpu_id)
        if query.owned_gpu_id is not None:
            available_gpus = self._scoring_policy.restrict_to_owned_gpu(available_gpus, query.owned_gpu_id)

        resolved_offers = self._scoring_policy.resolve_offers(offers)
        cpu_value_index = self._scoring_policy.build_value_index(
            candidates=available_cpus,
            entity_type="cpu",
            resolved_offers=resolved_offers,
        )
        gpu_value_index = self._scoring_policy.build_value_index(
            candidates=available_gpus,
            entity_type="gpu",
            resolved_offers=resolved_offers,
        )

        if query.budget is not None:
            available_cpus, available_gpus = self._scoring_policy.prefilter_by_budget(
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
                breakdown = self._scoring_policy.score_pair(
                    cpu=cpu,
                    gpu=gpu,
                    query=query,
                    use_case=normalized_use_case,
                    resolution=normalized_resolution,
                    resolved_offers=resolved_offers,
                    cpu_value_index=cpu_value_index,
                    gpu_value_index=gpu_value_index,
                )
                if breakdown is None:
                    continue

                results.append(
                    MatchResult(
                        cpu=MatchComponent(
                            id=cpu.id,
                            name=cpu.name,
                            ranking_percentile=breakdown.cpu_score,
                            price=breakdown.cpu_price,
                        ),
                        gpu=MatchComponent(
                            id=gpu.id,
                            name=gpu.name,
                            ranking_percentile=breakdown.gpu_score,
                            price=breakdown.gpu_price,
                        ),
                        score=breakdown.score,
                        label=breakdown.label,
                        purchase_price=breakdown.purchase_price,
                        pair_price=breakdown.pair_price,
                        reasons=self._reason_builder.build(
                            cpu=cpu,
                            gpu=gpu,
                            query=query,
                            resolution=normalized_resolution,
                            breakdown=breakdown,
                        ),
                    )
                )

        results.sort(key=lambda item: (-item.score, item.purchase_price or float("inf"), item.cpu.name, item.gpu.name))
        return results[: query.limit]
