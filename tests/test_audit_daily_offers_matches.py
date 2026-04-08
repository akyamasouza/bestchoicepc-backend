from __future__ import annotations

from app.services.entity_matcher import EntityMatcher


def test_audit_matcher_rejects_canonical_offer_with_wrong_numeric_gpu_model() -> None:
    matcher = EntityMatcher()

    reason = matcher.mismatch_reason(
        entity_name="GeForce RTX 5090",
        entity_id="geforce-rtx-5090",
        raw_text=(
            "Placa de Video Palit GeForce RTX 5060 White OC, 8 GB GDDR7, "
            "PCIe x8 5.0 R$ 2.600,00 Loja: KaBuM!"
        ),
    )

    assert reason == "mensagem rejeitada por falta de modelo numerico: 5090"
