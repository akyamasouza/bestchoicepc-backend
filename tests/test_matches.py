from fastapi.testclient import TestClient

from app.main import app
from app.routes.matches import (
    get_cpu_repository,
    get_daily_offer_repository,
    get_gpu_repository,
    get_review_consensus_lookup_service,
)
from app.schemas.cpu import CpuListItem, CpuRanking
from app.schemas.daily_offer import DailyOffer
from app.schemas.gpu import GpuListItem, GpuRanking
from app.services.review_consensus_lookup import ReviewConsensusLookup
from app.services.youtube_review_consensus import (
    MatchReviewedGame,
    MatchReviewConsensus,
    YoutubeVideoReference,
)


class FakeCpuRepository:
    def __init__(self) -> None:
        self.last_requested_sku: str | None = None

    def list_match_candidates(self, *, sku: str | None = None) -> list[CpuListItem]:
        self.last_requested_sku = sku
        items = [
            CpuListItem(
                id="cpu-1",
                name="AMD Ryzen 5 7600",
                sku="ryzen-5-7600",
                socket="AM5",
                cores=6,
                threads=12,
                benchmark=None,
                ranking=CpuRanking(
                    game_score=100.0,
                    game_percentile=80.0,
                    performance_tier="B",
                ),
            ),
            CpuListItem(
                id="cpu-2",
                name="AMD Ryzen 7 7800X3D",
                sku="ryzen-7-7800x3d",
                socket="AM5",
                cores=8,
                threads=16,
                benchmark=None,
                ranking=CpuRanking(
                    game_score=120.0,
                    game_percentile=100.0,
                    performance_tier="S",
                ),
            ),
        ]
        if sku is None:
            return items
        return [item for item in items if item.sku == sku]


class FakeGpuRepository:
    def __init__(self) -> None:
        self.last_requested_sku: str | None = None

    def list_match_candidates(self, *, sku: str | None = None) -> list[GpuListItem]:
        self.last_requested_sku = sku
        items = [
            GpuListItem(
                id="gpu-1",
                name="GeForce RTX 4060",
                sku="rtx-4060",
                bus_interface="PCIe 4.0 x8",
                memory_size_mb=8192,
                core_clock_mhz=None,
                memory_clock_mhz=None,
                max_tdp_w=115,
                category="Desktop",
                benchmark=None,
                ranking=GpuRanking(
                    game_score=90.0,
                    game_percentile=62.0,
                    performance_tier="D",
                ),
            ),
            GpuListItem(
                id="gpu-2",
                name="GeForce RTX 4070 Super",
                sku="rtx-4070-super",
                bus_interface="PCIe 4.0 x16",
                memory_size_mb=12288,
                core_clock_mhz=None,
                memory_clock_mhz=None,
                max_tdp_w=220,
                category="Desktop",
                benchmark=None,
                ranking=GpuRanking(
                    game_score=115.0,
                    game_percentile=82.0,
                    performance_tier="A",
                ),
            ),
        ]
        if sku is None:
            return items
        return [item for item in items if item.sku == sku]


class FakeDailyOfferRepository:
    def list_today(self, entity_type: str | None = None) -> list[DailyOffer]:
        if entity_type == "cpu":
            return [
                DailyOffer(
                    business_date="2026-03-30",
                    entity_type="cpu",
                    entity_sku="ryzen-5-7600",
                    entity_name="AMD Ryzen 5 7600",
                    store="kabum",
                    store_display_name="KaBuM!",
                    price_card=1400.0,
                    installments=None,
                    source_url=None,
                    telegram_message_id=None,
                    telegram_message_url=None,
                    posted_at=None,
                    lowest_price_90d=1349.0,
                    median_price_90d=1499.0,
                    raw_text="cpu",
                ),
                DailyOffer(
                    business_date="2026-03-30",
                    entity_type="cpu",
                    entity_sku="ryzen-7-7800x3d",
                    entity_name="AMD Ryzen 7 7800X3D",
                    store="kabum",
                    store_display_name="KaBuM!",
                    price_card=2800.0,
                    installments=None,
                    source_url=None,
                    telegram_message_id=None,
                    telegram_message_url=None,
                    posted_at=None,
                    lowest_price_90d=2699.0,
                    median_price_90d=2999.0,
                    raw_text="cpu",
                ),
            ]

        if entity_type == "gpu":
            return [
                DailyOffer(
                    business_date="2026-03-30",
                    entity_type="gpu",
                    entity_sku="rtx-4060",
                    entity_name="GeForce RTX 4060",
                    store="kabum",
                    store_display_name="KaBuM!",
                    price_card=2100.0,
                    installments=None,
                    source_url=None,
                    telegram_message_id=None,
                    telegram_message_url=None,
                    posted_at=None,
                    lowest_price_90d=1999.0,
                    median_price_90d=2299.0,
                    raw_text="gpu",
                ),
                DailyOffer(
                    business_date="2026-03-30",
                    entity_type="gpu",
                    entity_sku="rtx-4070-super",
                    entity_name="GeForce RTX 4070 Super",
                    store="kabum",
                    store_display_name="KaBuM!",
                    price_card=3800.0,
                    installments=None,
                    source_url=None,
                    telegram_message_id=None,
                    telegram_message_url=None,
                    posted_at=None,
                    lowest_price_90d=3699.0,
                    median_price_90d=4099.0,
                    raw_text="gpu",
                ),
            ]

        return []


class FakeReviewConsensusLookupService:
    def get_or_start_lookup(
        self,
        *,
        cpu_sku: str,
        cpu_name: str,
        gpu_sku: str,
        gpu_name: str,
        background_tasks,
        force_refresh: bool = False,
    ) -> ReviewConsensusLookup:
        if "Ryzen 5 7600" not in cpu_name or "RTX 4070 Super" not in gpu_name:
            return ReviewConsensusLookup(
                status="no_consensus",
                reason="insufficient_evidence",
                review_consensus=None,
            )

        return ReviewConsensusLookup(
            status="ready",
            reason=None,
            review_consensus=MatchReviewConsensus(
                insight="Consenso dos reviews sugere que o par aparece como bem equilibrado. Nos trechos com FPS explicito, a media observada ficou em torno de 91.5 FPS.",
                warnings=("Os reviews destacam cenarios com DLSS.",),
                confidence="high",
                references=(
                    YoutubeVideoReference(
                        title="RTX 4070 Super + Ryzen 5 7600 benchmark",
                        url="https://www.youtube.com/watch?v=video-1",
                        channel="Channel 1",
                    ),
                    YoutubeVideoReference(
                        title="Ryzen 5 7600 with RTX 4070 Super review",
                        url="https://www.youtube.com/watch?v=video-2",
                        channel="Channel 2",
                    ),
                ),
                source_count=2,
                average_explicit_fps=91.5,
                tested_games=(
                    MatchReviewedGame(
                        name="Cyberpunk 2077",
                        resolution="1440p",
                        avg_fps=92.0,
                    ),
                    MatchReviewedGame(
                        name="Alan Wake 2",
                        resolution="1440p",
                        avg_fps=91.0,
                    ),
                ),
            ),
        )


def test_list_matches_returns_ranked_pairs() -> None:
    cpu_repository = FakeCpuRepository()
    gpu_repository = FakeGpuRepository()
    app.dependency_overrides[get_cpu_repository] = lambda: cpu_repository
    app.dependency_overrides[get_gpu_repository] = lambda: gpu_repository
    app.dependency_overrides[get_daily_offer_repository] = FakeDailyOfferRepository
    client = TestClient(app)

    response = client.post(
        "/matches",
        json={
            "use_case": "aaa",
            "resolution": "1440p",
            "budget": 5500,
            "limit": 3,
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()

    assert cpu_repository.last_requested_sku is None
    assert gpu_repository.last_requested_sku is None
    assert payload["total"] == 3
    assert len(payload["items"]) == 3
    top_match = payload["items"][0]

    assert top_match["cpu"] == {
        "sku": "ryzen-5-7600",
        "name": "AMD Ryzen 5 7600",
        "ranking_percentile": 80.0,
        "price": 1400.0,
    }
    assert top_match["gpu"] == {
        "sku": "rtx-4070-super",
        "name": "GeForce RTX 4070 Super",
        "ranking_percentile": 82.0,
        "price": 3800.0,
    }
    assert top_match["score"] >= 85
    assert top_match["label"] == "ideal"
    assert top_match["purchase_price"] == 5200.0
    assert top_match["pair_price"] == 5200.0
    assert "equilibrio forte para 1440p" in top_match["reasons"]
    assert "faixa de desempenho adequada para 1440p" in top_match["reasons"]
    assert "preco atual bem posicionado no historico" in top_match["reasons"]
    assert "vram adequada para 1440p" in top_match["reasons"]
    assert top_match["review_consensus"] is None
    assert top_match["review_consensus_status"] == "not_requested"
    assert top_match["review_consensus_reason"] is None


def test_list_matches_can_include_review_consensus() -> None:
    cpu_repository = FakeCpuRepository()
    gpu_repository = FakeGpuRepository()
    app.dependency_overrides[get_cpu_repository] = lambda: cpu_repository
    app.dependency_overrides[get_gpu_repository] = lambda: gpu_repository
    app.dependency_overrides[get_daily_offer_repository] = FakeDailyOfferRepository
    app.dependency_overrides[get_review_consensus_lookup_service] = FakeReviewConsensusLookupService
    client = TestClient(app)

    response = client.post(
        "/matches",
        json={
            "use_case": "aaa",
            "resolution": "1440p",
            "budget": 5500,
            "limit": 2,
            "include_review_consensus": True,
            "review_consensus_limit": 1,
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    top_match = payload["items"][0]

    assert top_match["review_consensus"] == {
        "insight": "Consenso dos reviews sugere que o par aparece como bem equilibrado. Nos trechos com FPS explicito, a media observada ficou em torno de 91.5 FPS.",
        "warnings": ["Os reviews destacam cenarios com DLSS."],
        "confidence": "high",
        "references": [
            {
                "title": "RTX 4070 Super + Ryzen 5 7600 benchmark",
                "url": "https://www.youtube.com/watch?v=video-1",
                "channel": "Channel 1",
            },
            {
                "title": "Ryzen 5 7600 with RTX 4070 Super review",
                "url": "https://www.youtube.com/watch?v=video-2",
                "channel": "Channel 2",
            },
        ],
        "source_count": 2,
        "average_explicit_fps": 91.5,
        "tested_games": [
            {
                "name": "Cyberpunk 2077",
                "resolution": "1440p",
                "avg_fps": 92.0,
            },
            {
                "name": "Alan Wake 2",
                "resolution": "1440p",
                "avg_fps": 91.0,
            },
        ],
    }
    assert top_match["review_consensus_status"] == "ready"
    assert top_match["review_consensus_reason"] is None
    assert payload["items"][1]["review_consensus"] is None
    assert payload["items"][1]["review_consensus_status"] == "not_requested"
    assert payload["items"][1]["review_consensus_reason"] is None


def test_list_matches_returns_bad_request_for_unknown_owned_cpu() -> None:
    cpu_repository = FakeCpuRepository()
    gpu_repository = FakeGpuRepository()
    app.dependency_overrides[get_cpu_repository] = lambda: cpu_repository
    app.dependency_overrides[get_gpu_repository] = lambda: gpu_repository
    app.dependency_overrides[get_daily_offer_repository] = FakeDailyOfferRepository
    client = TestClient(app)

    response = client.post(
        "/matches",
        json={
            "use_case": "aaa",
            "resolution": "1440p",
            "budget": 5500,
            "owned_cpu_sku": "cpu-inexistente",
        },
    )

    app.dependency_overrides.clear()

    assert cpu_repository.last_requested_sku == "cpu-inexistente"
    assert gpu_repository.last_requested_sku is None
    assert response.status_code == 400
    assert response.json() == {
        "detail": "CPU ownada nao encontrada: cpu-inexistente",
    }


def test_get_match_review_consensus_returns_lookup_payload() -> None:
    app.dependency_overrides[get_cpu_repository] = FakeCpuRepository
    app.dependency_overrides[get_gpu_repository] = FakeGpuRepository
    app.dependency_overrides[get_review_consensus_lookup_service] = FakeReviewConsensusLookupService
    client = TestClient(app)

    response = client.post(
        "/matches/review-consensus",
        json={
            "cpu_sku": "ryzen-5-7600",
            "gpu_sku": "rtx-4070-super",
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "cpu_sku": "ryzen-5-7600",
        "gpu_sku": "rtx-4070-super",
        "lookup": {
            "status": "ready",
            "reason": None,
            "review_consensus": {
                "insight": "Consenso dos reviews sugere que o par aparece como bem equilibrado. Nos trechos com FPS explicito, a media observada ficou em torno de 91.5 FPS.",
                "warnings": ["Os reviews destacam cenarios com DLSS."],
                "confidence": "high",
                "references": [
                    {
                        "title": "RTX 4070 Super + Ryzen 5 7600 benchmark",
                        "url": "https://www.youtube.com/watch?v=video-1",
                        "channel": "Channel 1",
                    },
                    {
                        "title": "Ryzen 5 7600 with RTX 4070 Super review",
                        "url": "https://www.youtube.com/watch?v=video-2",
                        "channel": "Channel 2",
                    },
                ],
                "source_count": 2,
                "average_explicit_fps": 91.5,
                "tested_games": [
                    {
                        "name": "Cyberpunk 2077",
                        "resolution": "1440p",
                        "avg_fps": 92.0,
                    },
                    {
                        "name": "Alan Wake 2",
                        "resolution": "1440p",
                        "avg_fps": 91.0,
                    },
                ],
            },
        },
    }
