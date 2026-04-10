from __future__ import annotations

from app.schemas.catalog_candidate import CatalogCandidate
from app.services.catalog_candidate_enricher import CatalogCandidateEnricher
from app.services.openrouter_product_normalizer import NormalizedProductIdentity


class FakeNormalizer:
    def __init__(self, identity: NormalizedProductIdentity | None = None, error: Exception | None = None) -> None:
        self.identity = identity
        self.error = error

    def normalize(self, _candidate: CatalogCandidate) -> NormalizedProductIdentity | None:
        if self.error is not None:
            raise self.error
        return self.identity


class FailingFetcher:
    def fetch_text(self, _url: str) -> str:
        raise AssertionError("fetcher should not be used")


class ErrorFetcher:
    def fetch_text(self, _url: str) -> str:
        raise RuntimeError("boom")


class FakeFetcher:
    def __init__(self, html_by_url: dict[str, str]) -> None:
        self.html_by_url = html_by_url

    def fetch_text(self, url: str) -> str:
        return self.html_by_url[url]


def build_candidate(entity_type: str, product_url: str | None, proposed_name: str | None = None, raw_text: str = "Mensagem qualquer") -> CatalogCandidate:
    return CatalogCandidate(
        entity_type=entity_type,
        fingerprint="fp-1",
        proposed_name=proposed_name or "SSD Kingston NV3 1TB",
        proposed_sku="ssd-kingston-nv3-1tb",
        raw_title=proposed_name or "SSD Kingston NV3 1TB",
        raw_text=raw_text,
        product_url=product_url,
        first_seen="2026-03-25T00:00:00Z",
        last_seen="2026-03-25T00:00:00Z",
        related_catalog_entity_name="",
        related_catalog_entity_sku="",
    )


def test_enrich_ssd_candidate_extracts_minimum_fields() -> None:
    enricher = CatalogCandidateEnricher(
        fetcher=FakeFetcher(
            {
                "https://example.com/ssd": """
                <html>
                    <head><title>SSD Kingston NV3 1TB NVMe PCIe 4.0 - Kabum</title></head>
                    <body><h1>SSD Kingston NV3 1TB NVMe PCIe 4.0</h1></body>
                </html>
                """
            }
        )
    )

    result = enricher.enrich(build_candidate("ssd", "https://example.com/ssd"))

    assert result.error is None
    assert result.data is not None
    assert result.data["proposed_name"] == "SSD Kingston NV3 1TB"
    assert result.data["proposed_sku"] == "ssd-kingston-nv3-1tb"
    assert result.data["brand"] == "SSD"
    assert result.data["capacity_gb"] == 1024
    assert result.data["interface"] == "NVMe"


def test_enrich_ram_candidate_extracts_generation_and_capacity() -> None:
    enricher = CatalogCandidateEnricher(
        fetcher=FakeFetcher(
            {
                "https://example.com/ram": "<html><head><title>Memoria Kingston Fury Beast 32GB DDR5 6000MHz</title></head></html>"
            }
        )
    )

    result = enricher.enrich(build_candidate("ram", "https://example.com/ram", "Memoria Kingston Fury Beast 32GB DDR5 6000MHz"))

    assert result.error is None
    assert result.data is not None
    assert result.data["generation"] == "DDR5"
    assert result.data["capacity_gb"] == 32
    assert result.data["compatibility"] == {"desktop": True, "notebook": False, "platforms": []}


def test_enrich_uses_ai_normalization_for_cpu_without_product_url() -> None:
    enricher = CatalogCandidateEnricher(
        fetcher=FailingFetcher(),
        normalizer=FakeNormalizer(
            NormalizedProductIdentity(
                proposed_name="AMD Ryzen 7 9800X3D",
                proposed_sku="amd-ryzen-7-9800x3d",
                canonical_sku="100-100001084WOF",
                confidence=0.97,
                model="z-ai/glm-5.1-20260406",
            )
        ),
    )
    candidate = CatalogCandidate(
        entity_type="cpu",
        fingerprint="fp-2",
        proposed_name="AMD Ryzen 7 9800X3D",
        proposed_sku="amd-ryzen-7-9800x3d",
        raw_title="AMD Ryzen 7 9800X3D",
        raw_text="Processador AMD Ryzen 7 9800X3D R$ 2.799,99",
        first_seen="2026-03-25T00:00:00Z",
        last_seen="2026-03-25T00:00:00Z",
    )

    result = enricher.enrich(candidate)

    assert result.error is None
    assert result.data is not None
    assert result.data["proposed_name"] == "AMD Ryzen 7 9800X3D"
    assert result.data["proposed_sku"] == "amd-ryzen-7-9800x3d"
    assert result.data["canonical_sku"] == "100-100001084WOF"
    assert result.data["ai_normalization"]["model"] == "z-ai/glm-5.1-20260406"


def test_enrich_falls_back_when_ai_normalization_is_invalid() -> None:
    enricher = CatalogCandidateEnricher(
        fetcher=ErrorFetcher(),
        normalizer=FakeNormalizer(
            NormalizedProductIdentity(
                proposed_name="AMD Ryzen 7 9800",
                proposed_sku="amd-ryzen-7-9800",
                confidence=0.80,
            )
        ),
    )
    candidate = CatalogCandidate(
        entity_type="cpu",
        fingerprint="fp-2",
        proposed_name="AMD Ryzen 7 9800X3D",
        proposed_sku="amd-ryzen-7-9800x3d",
        raw_title="AMD Ryzen 7 9800X3D",
        raw_text="Processador AMD Ryzen 7 9800X3D R$ 2.799,99",
        product_url="https://example.com/cpu",
        first_seen="2026-03-25T00:00:00Z",
        last_seen="2026-03-25T00:00:00Z",
    )

    result = enricher.enrich(candidate)

    assert result.data is None
    assert result.error == "failed to fetch product page (boom)"


def test_enrich_returns_error_when_product_url_is_missing() -> None:
    enricher = CatalogCandidateEnricher(fetcher=FakeFetcher({}), normalizer=FakeNormalizer())
    candidate = CatalogCandidate(
        entity_type="cpu",
        fingerprint="fp-2",
        proposed_name="AMD Ryzen 7 9700X",
        proposed_sku="amd-ryzen-7-9700x",
        raw_title="AMD Ryzen 7 9700X",
        raw_text="Mensagem qualquer",
        first_seen="2026-03-25T00:00:00Z",
        last_seen="2026-03-25T00:00:00Z",
    )

    result = enricher.enrich(candidate)

    assert result.data is None
    assert result.error == "candidate does not have product_url"


def test_enrich_rejects_captcha_page() -> None:
    enricher = CatalogCandidateEnricher(
        fetcher=FakeFetcher({"https://example.com/captcha": "<html><head><title>Captcha Magalu</title></head></html>"})
    )

    result = enricher.enrich(build_candidate("cpu", "https://example.com/captcha", "AMD Ryzen 7 9700X"))

    assert result.data is None
    assert result.error == "product page is not a valid catalog page"


def test_enrich_rejects_compound_configuration_post() -> None:
    enricher = CatalogCandidateEnricher(fetcher=FakeFetcher({}))
    candidate = build_candidate(
        "cpu",
        None,
        proposed_name="Configuração de PC",
        raw_text="Recomendação de Configuração de PC - Preço Total: R$ 7.000 https://a https://b https://c",
    )

    result = enricher.enrich(candidate)

    assert result.data is None
    assert result.error == "candidate looks like a compound configuration post"


def test_enrich_prefers_cleaned_detection_name_over_store_suffix() -> None:
    enricher = CatalogCandidateEnricher(
        fetcher=FakeFetcher(
            {
                "https://example.com/ssd-clean": """
                <html>
                    <head><title>SSD Kingston NV3 1TB NVMe PCIe 4.0 - Kabum</title></head>
                    <body><h1>SSD Kingston NV3 1TB NVMe PCIe 4.0 - Kabum</h1></body>
                </html>
                """
            }
        )
    )

    result = enricher.enrich(build_candidate("ssd", "https://example.com/ssd-clean", "SSD Kingston NV3 1TB NVMe PCIe 4.0 - Kabum"))

    assert result.error is None
    assert result.data is not None
    assert result.data["proposed_name"] == "SSD Kingston NV3 1TB NVMe PCIe 4.0"
    assert result.data["proposed_sku"] == "ssd-kingston-nv3-1tb-nvme-pcie-4-0"


def test_enrich_rejects_existing_canonical_sku() -> None:
    enricher = CatalogCandidateEnricher(
        fetcher=FakeFetcher({"https://example.com/cpu": "<html><head><title>Processador AMD Ryzen 7 9800X3D - 100-100001084WOF</title></head></html>"})
    )
    candidate = build_candidate("cpu", "https://example.com/cpu", "AMD Ryzen 7 9800X3D")
    candidate.related_catalog_entity_sku = "100-100001084WOF"
    candidate.related_catalog_entity_name = "AMD Ryzen 7 9800X3D"

    result = enricher.enrich(candidate)

    assert result.data is None
    assert result.error == "candidate already exists canonically"
