from __future__ import annotations

from app.services.entity_matcher import EntityMatcher


def test_accepts_exact_gpu_variant_match() -> None:
    matcher = EntityMatcher()

    reason = matcher.mismatch_reason(
        entity_name="GeForce RTX 5070 Ti",
        raw_text="Placa de Video PNY GeForce RTX 5070 Ti OC 16GB, 16 GB GDDR7, PCIe x16 5.0 R$ 6.599,00",
    )

    assert reason is None


def test_rejects_gpu_ti_offer_for_non_ti_model() -> None:
    matcher = EntityMatcher()

    reason = matcher.mismatch_reason(
        entity_name="GeForce RTX 5070",
        raw_text="Placa de Video PNY GeForce RTX 5070 Ti OC 16GB, 16 GB GDDR7, PCIe x16 5.0 R$ 6.599,00",
    )

    assert reason == "mensagem rejeitada por discriminadores conflitantes: ti"


def test_rejects_gpu_super_offer_for_base_model() -> None:
    matcher = EntityMatcher()

    reason = matcher.mismatch_reason(
        entity_name="GeForce RTX 4080",
        raw_text="Placa de Video ASUS GeForce RTX 4080 SUPER 16GB GDDR6X R$ 7.999,00",
    )

    assert reason == "mensagem rejeitada por discriminadores conflitantes: super"


def test_rejects_gpu_memory_mismatch() -> None:
    matcher = EntityMatcher()

    reason = matcher.mismatch_reason(
        entity_name="GeForce RTX 4060 Ti 8GB",
        raw_text="Placa de Video Galax GeForce RTX 4060 Ti 16GB GDDR6 R$ 3.299,00",
    )

    assert reason == "mensagem rejeitada por falta de memoria declarada: 8gb"


def test_rejects_xt_offer_for_xtx_model() -> None:
    matcher = EntityMatcher()

    reason = matcher.mismatch_reason(
        entity_name="Radeon RX 7900 XTX",
        raw_text="Placa de Video AMD Radeon RX 7900 XT 20GB GDDR6 R$ 5.999,00",
    )

    assert reason == "mensagem rejeitada por falta de discriminadores: xtx"


def test_rejects_cpu_f_variant_for_base_model() -> None:
    matcher = EntityMatcher()

    reason = matcher.mismatch_reason(
        entity_name="Intel Core i5-12400",
        raw_text="Processador Intel Core i5-12400F, 6-Core, 12-Threads, LGA1700 R$ 899,00",
    )

    assert reason == "mensagem rejeitada por discriminadores conflitantes: f"


def test_rejects_cpu_x3d_offer_for_x_model() -> None:
    matcher = EntityMatcher()

    reason = matcher.mismatch_reason(
        entity_name="AMD Ryzen 7 7800X",
        raw_text="Processador AMD Ryzen 7 7800X3D, 8-Core, AM5 R$ 2.399,00",
    )

    assert reason == "mensagem rejeitada por discriminadores conflitantes: x3d"

