from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.match_scoring import ScoringBreakdown

if TYPE_CHECKING:
    from app.services.match_service import CpuMatchCandidate, GpuMatchCandidate, MatchQuery


class MatchReasonBuilder:
    def build(
        self,
        *,
        cpu: CpuMatchCandidate,
        gpu: GpuMatchCandidate,
        query: MatchQuery,
        resolution: str,
        breakdown: ScoringBreakdown,
    ) -> tuple[str, ...]:
        reasons: list[str] = []

        if breakdown.balance_score >= 80:
            reasons.append(f"equilibrio forte para {resolution}")
        elif breakdown.cpu_score > breakdown.gpu_score * 1.25:
            reasons.append("cpu acima do necessario para essa gpu")
        elif breakdown.gpu_score > breakdown.cpu_score * 1.35:
            reasons.append("gpu pode pedir uma cpu melhor")

        if breakdown.gpu_score > breakdown.gpu_soft_cap:
            reasons.append(f"gpu acima do necessario para {resolution}")
        elif breakdown.cpu_score > breakdown.cpu_soft_cap:
            reasons.append(f"cpu acima do necessario para {resolution}")
        elif breakdown.resolution_fit_score >= 85:
            reasons.append(f"faixa de desempenho adequada para {resolution}")

        if breakdown.market_score >= 75:
            reasons.append("preco atual bem posicionado no historico")
        elif breakdown.market_score < 45:
            reasons.append("preco atual pouco atrativo no historico")

        if breakdown.vram_score >= 90:
            reasons.append(f"vram adequada para {resolution}")
        elif breakdown.vram_score < 60:
            reasons.append(f"vram curta para {resolution}")

        if query.owned_cpu_id is not None or query.owned_gpu_id is not None:
            reasons.append("considera reaproveitamento da sua peca atual")

        if not reasons:
            reasons.append("combo dentro de um equilibrio pratico")

        return tuple(reasons)
