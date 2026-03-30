from app.services.match_service import (
    CpuMatchCandidate,
    GpuMatchCandidate,
    MatchQuery,
    MatchService,
    OfferSnapshot,
)


def test_match_service_prefers_balanced_pair_for_1440p_aaa() -> None:
    service = MatchService()

    matches = service.find_matches(
        cpus=[
            CpuMatchCandidate(
                sku="ryzen-5-7600",
                name="AMD Ryzen 5 7600",
                ranking_percentile=80.0,
            ),
            CpuMatchCandidate(
                sku="ryzen-7-7800x3d",
                name="AMD Ryzen 7 7800X3D",
                ranking_percentile=100.0,
            ),
        ],
        gpus=[
            GpuMatchCandidate(
                sku="rtx-4060",
                name="GeForce RTX 4060",
                ranking_percentile=62.0,
                memory_size_mb=8192,
            ),
            GpuMatchCandidate(
                sku="rtx-4070-super",
                name="GeForce RTX 4070 Super",
                ranking_percentile=82.0,
                memory_size_mb=12288,
            ),
        ],
        offers=[
            OfferSnapshot(
                entity_type="cpu",
                entity_sku="ryzen-5-7600",
                business_date="2026-03-30",
                price_card=1400.0,
                lowest_price_90d=1349.0,
                median_price_90d=1499.0,
            ),
            OfferSnapshot(
                entity_type="cpu",
                entity_sku="ryzen-7-7800x3d",
                business_date="2026-03-30",
                price_card=2800.0,
                lowest_price_90d=2699.0,
                median_price_90d=2999.0,
            ),
            OfferSnapshot(
                entity_type="gpu",
                entity_sku="rtx-4060",
                business_date="2026-03-30",
                price_card=2100.0,
                lowest_price_90d=1999.0,
                median_price_90d=2299.0,
            ),
            OfferSnapshot(
                entity_type="gpu",
                entity_sku="rtx-4070-super",
                business_date="2026-03-30",
                price_card=3800.0,
                lowest_price_90d=3699.0,
                median_price_90d=4099.0,
            ),
        ],
        query=MatchQuery(
            use_case="aaa",
            resolution="1440p",
            budget=5500.0,
        ),
    )

    assert matches[0].cpu.sku == "ryzen-5-7600"
    assert matches[0].gpu.sku == "rtx-4070-super"
    assert matches[0].label == "ideal"


def test_match_service_respects_owned_cpu_and_uses_gpu_only_budget() -> None:
    service = MatchService()

    matches = service.find_matches(
        cpus=[
            CpuMatchCandidate(
                sku="ryzen-5-7600",
                name="AMD Ryzen 5 7600",
                ranking_percentile=80.0,
            )
        ],
        gpus=[
            GpuMatchCandidate(
                sku="rtx-4060",
                name="GeForce RTX 4060",
                ranking_percentile=62.0,
                memory_size_mb=8192,
            ),
            GpuMatchCandidate(
                sku="rtx-4070-super",
                name="GeForce RTX 4070 Super",
                ranking_percentile=82.0,
                memory_size_mb=12288,
            ),
        ],
        offers=[
            OfferSnapshot(
                entity_type="cpu",
                entity_sku="ryzen-5-7600",
                business_date="2026-03-30",
                price_card=1400.0,
            ),
            OfferSnapshot(
                entity_type="gpu",
                entity_sku="rtx-4060",
                business_date="2026-03-30",
                price_card=2100.0,
            ),
            OfferSnapshot(
                entity_type="gpu",
                entity_sku="rtx-4070-super",
                business_date="2026-03-30",
                price_card=3800.0,
            ),
        ],
        query=MatchQuery(
            use_case="aaa",
            resolution="1440p",
            budget=4000.0,
            owned_cpu_sku="ryzen-5-7600",
        ),
    )

    assert matches[0].cpu.sku == "ryzen-5-7600"
    assert matches[0].gpu.sku == "rtx-4070-super"
    assert matches[0].purchase_price == 3800.0
    assert matches[0].pair_price == 5200.0


def test_match_service_uses_value_and_market_signal_for_cost_benefit_queries() -> None:
    service = MatchService()

    matches = service.find_matches(
        cpus=[
            CpuMatchCandidate(
                sku="ryzen-5-7600",
                name="AMD Ryzen 5 7600",
                ranking_percentile=80.0,
            )
        ],
        gpus=[
            GpuMatchCandidate(
                sku="rx-7800-xt",
                name="Radeon RX 7800 XT",
                ranking_percentile=80.0,
                memory_size_mb=16384,
            ),
            GpuMatchCandidate(
                sku="rtx-4070",
                name="GeForce RTX 4070",
                ranking_percentile=80.0,
                memory_size_mb=12288,
            ),
        ],
        offers=[
            OfferSnapshot(
                entity_type="cpu",
                entity_sku="ryzen-5-7600",
                business_date="2026-03-30",
                price_card=1400.0,
                lowest_price_90d=1349.0,
                median_price_90d=1499.0,
            ),
            OfferSnapshot(
                entity_type="gpu",
                entity_sku="rx-7800-xt",
                business_date="2026-03-30",
                price_card=3200.0,
                lowest_price_90d=3099.0,
                median_price_90d=3499.0,
            ),
            OfferSnapshot(
                entity_type="gpu",
                entity_sku="rtx-4070",
                business_date="2026-03-30",
                price_card=4200.0,
                lowest_price_90d=3399.0,
                median_price_90d=3599.0,
            ),
        ],
        query=MatchQuery(
            use_case="custo-beneficio",
            resolution="1440p",
            budget=6000.0,
        ),
    )

    assert matches[0].gpu.sku == "rx-7800-xt"
    assert "preco atual bem posicionado no historico" in matches[0].reasons


def test_match_service_prefers_latest_business_date_when_resolving_offers() -> None:
    service = MatchService()

    matches = service.find_matches(
        cpus=[
            CpuMatchCandidate(
                sku="ryzen-5-7600",
                name="AMD Ryzen 5 7600",
                ranking_percentile=80.0,
            )
        ],
        gpus=[
            GpuMatchCandidate(
                sku="rtx-4070-super",
                name="GeForce RTX 4070 Super",
                ranking_percentile=82.0,
                memory_size_mb=12288,
            )
        ],
        offers=[
            OfferSnapshot(
                entity_type="cpu",
                entity_sku="ryzen-5-7600",
                business_date="2026-03-29",
                price_card=1200.0,
            ),
            OfferSnapshot(
                entity_type="cpu",
                entity_sku="ryzen-5-7600",
                business_date="2026-03-30",
                price_card=1400.0,
            ),
            OfferSnapshot(
                entity_type="gpu",
                entity_sku="rtx-4070-super",
                business_date="2026-03-29",
                price_card=3900.0,
            ),
            OfferSnapshot(
                entity_type="gpu",
                entity_sku="rtx-4070-super",
                business_date="2026-03-30",
                price_card=3800.0,
            ),
        ],
        query=MatchQuery(
            use_case="aaa",
            resolution="1440p",
            budget=6000.0,
        ),
    )

    assert matches[0].cpu.price == 1400.0
    assert matches[0].gpu.price == 3800.0
    assert matches[0].purchase_price == 5200.0


def test_match_service_penalizes_halo_gpu_for_1440p_without_price_data() -> None:
    service = MatchService()

    matches = service.find_matches(
        cpus=[
            CpuMatchCandidate(
                sku="i5-13600k",
                name="Intel Core i5-13600K",
                ranking_percentile=89.5,
            ),
            CpuMatchCandidate(
                sku="ryzen-5-7600",
                name="AMD Ryzen 5 7600",
                ranking_percentile=80.0,
            ),
        ],
        gpus=[
            GpuMatchCandidate(
                sku="rtx-4070-super",
                name="GeForce RTX 4070 Super",
                ranking_percentile=82.0,
                memory_size_mb=12288,
            ),
            GpuMatchCandidate(
                sku="rtx-5090",
                name="GeForce RTX 5090",
                ranking_percentile=100.0,
                memory_size_mb=32768,
            ),
        ],
        offers=[],
        query=MatchQuery(
            use_case="aaa",
            resolution="1440p",
            limit=5,
        ),
    )

    assert matches[0].gpu.sku == "rtx-4070-super"
    halo_match = next(match for match in matches if match.gpu.sku == "rtx-5090")
    assert halo_match.label != "ideal"
    assert "gpu acima do necessario para 1440p" in halo_match.reasons
