from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Protocol

import httpx

from app.schemas.catalog_candidate import CatalogCandidate


class HtmlFetcherProtocol(Protocol):
    def fetch_text(self, url: str) -> str: ...


class HttpxHtmlFetcher:
    def __init__(self, timeout: float = 10.0) -> None:
        self.timeout = timeout

    def fetch_text(self, url: str) -> str:
        response = httpx.get(url, timeout=self.timeout, follow_redirects=True)
        response.raise_for_status()
        return response.text


@dataclass(frozen=True, slots=True)
class CatalogCandidateEnrichmentResult:
    data: dict[str, Any] | None
    error: str | None = None


class CatalogCandidateEnricher:
    _INVALID_PAGE_MARKERS = (
        "captcha",
        "access denied",
        "403 forbidden",
        "verify you are human",
        "verifique que voce e humano",
        "cloudflare",
    )
    _COMPOUND_MARKERS = (
        "recomendação de configuração",
        "recomendacao de configuracao",
        "configuração de pc",
        "configuracao de pc",
        "preço total",
        "preco total",
        "inscreva-se no nosso canal",
        "inscreva se no nosso canal",
        "youtube.com",
        "────────",
    )
    _STORE_SUFFIX_PATTERN = re.compile(
        r"\s*(?:\||-|–)\s*(?:kabum!?|amazon|pichau|terabyte(?:shop)?|waz|fan[aá]ticos por tecnologia).*?$",
        flags=re.IGNORECASE,
    )
    _CPU_NAME_PATTERN = re.compile(
        r"((?:AMD\s+Ryzen|Intel\s+Core(?:\s+Ultra)?(?:\s+i[3579])?)\s+[A-Za-z0-9\- ]*?\d{3,5}[A-Za-z]{0,3})",
        flags=re.IGNORECASE,
    )
    _GPU_NAME_PATTERN = re.compile(
        r"((?:GeForce\s+(?:RTX|GTX)|Radeon\s+RX)\s+[A-Za-z0-9\- ]*?\d{3,5}[A-Za-z]{0,4}(?:\s+(?:Ti|SUPER|XT|XTX|GRE))?)",
        flags=re.IGNORECASE,
    )
    _CANONICAL_SKU_PATTERNS = (
        re.compile(r"\b\d{3}-\d{9,}[A-Z]{2,4}\b"),
        re.compile(r"\bBX\d{8,}[A-Z]{0,3}\b", flags=re.IGNORECASE),
        re.compile(r"\bCM[A-Z0-9\-]{6,}\b", flags=re.IGNORECASE),
    )

    def __init__(self, fetcher: HtmlFetcherProtocol | None = None) -> None:
        self.fetcher = fetcher or HttpxHtmlFetcher()

    def enrich(self, candidate: CatalogCandidate) -> CatalogCandidateEnrichmentResult:
        if self._looks_like_compound_post(candidate.raw_text):
            return CatalogCandidateEnrichmentResult(data=None, error="candidate looks like a compound configuration post")

        if not candidate.product_url:
            return CatalogCandidateEnrichmentResult(data=None, error="candidate does not have product_url")

        try:
            html = self.fetcher.fetch_text(candidate.product_url)
        except Exception as exc:
            return CatalogCandidateEnrichmentResult(data=None, error=f"failed to fetch product page ({exc})")

        page_title = self._extract_page_title(html)
        if self._looks_like_invalid_page(page_title):
            return CatalogCandidateEnrichmentResult(data=None, error="product page is not a valid catalog page")

        canonical_sku = self._extract_canonical_sku(page_title or html)
        related_catalog_sku = self._normalize_sku(candidate.related_catalog_entity_sku)
        if canonical_sku is not None and canonical_sku.lower() == related_catalog_sku:
            return CatalogCandidateEnrichmentResult(data=None, error="candidate already exists canonically")

        proposed_name = self._resolve_name(candidate, page_title)
        if proposed_name is None:
            return CatalogCandidateEnrichmentResult(data=None, error="failed to extract product name from product page")

        if self._looks_like_invalid_page(proposed_name):
            return CatalogCandidateEnrichmentResult(data=None, error="product page is not a valid catalog page")

        if self._looks_like_compound_name(proposed_name):
            return CatalogCandidateEnrichmentResult(data=None, error="candidate name still looks like a compound configuration post")

        related_catalog_name = self._normalize_name(candidate.related_catalog_entity_name)
        if related_catalog_name and self._normalize_name(proposed_name) == related_catalog_name:
            return CatalogCandidateEnrichmentResult(data=None, error="candidate already exists canonically")

        proposed_sku = canonical_sku or self._slugify(proposed_name)
        if not proposed_sku:
            return CatalogCandidateEnrichmentResult(data=None, error="failed to derive canonical sku from product page")

        if self._normalize_sku(proposed_sku) == related_catalog_sku:
            return CatalogCandidateEnrichmentResult(data=None, error="candidate already exists canonically")

        enrichment: dict[str, Any] = {
            "proposed_name": proposed_name,
            "proposed_sku": proposed_sku,
            "product_url": candidate.product_url,
            "raw_title": candidate.raw_title,
            "page_title": self._strip_noise(page_title) if page_title is not None else None,
        }
        entity_data = self._extract_entity_data(candidate.entity_type, html, proposed_name)
        enrichment.update(entity_data)
        return CatalogCandidateEnrichmentResult(data=enrichment)

    def _resolve_name(self, candidate: CatalogCandidate, page_title: str | None) -> str | None:
        raw_title = self._clean_candidate_name(candidate.raw_title)
        if raw_title is not None:
            return raw_title

        proposed_name = self._clean_candidate_name(candidate.proposed_name)
        if proposed_name is not None:
            return proposed_name

        if page_title is None:
            return None

        normalized_page_title = self._normalize_name_from_page_title(page_title)
        return self._clean_candidate_name(normalized_page_title)

    def _extract_entity_data(self, entity_type: str, html: str, proposed_name: str) -> dict[str, Any]:
        if entity_type == "cpu":
            return {
                "socket": self._extract_first(r"\b(AM4|AM5|LGA\s?1700|LGA\s?1851)\b", html),
            }
        if entity_type == "gpu":
            return {
                "category": self._extract_gpu_category(proposed_name),
                "memory_size_mb": self._extract_gpu_memory_mb(html, proposed_name),
            }
        if entity_type == "ssd":
            return {
                "brand": self._brand_from_name(proposed_name),
                "capacity_gb": self._extract_capacity_gb(html, proposed_name),
                "interface": self._extract_first(r"(PCIe\s*4\.0|PCIe\s*5\.0|NVMe|SATA)", html),
            }
        if entity_type == "ram":
            return {
                "brand": self._brand_from_name(proposed_name),
                "generation": self._extract_first(r"\b(DDR4|DDR5)\b", html),
                "capacity_gb": self._extract_capacity_gb(html, proposed_name),
                "compatibility": {"desktop": True, "notebook": False, "platforms": []},
            }
        if entity_type == "psu":
            return {
                "brand": self._brand_from_name(proposed_name),
                "wattage_w": self._extract_int(r"(\d{3,4})\s*W\b", html),
                "efficiency_rating": self._extract_first(r"(80\+\s*(?:Bronze|Silver|Gold|Platinum|Titanium))", html),
            }
        if entity_type == "motherboard":
            return {
                "brand": self._brand_from_name(proposed_name),
                "socket": self._extract_first(r"\b(AM4|AM5|LGA\s?1700|LGA\s?1851)\b", html),
                "compatibility": {"desktop": True, "cpu_brands": [], "sockets": [], "memory_generations": []},
            }
        return {}

    @staticmethod
    def _extract_page_title(html: str) -> str | None:
        patterns = [
            r"<meta[^>]+property=[\"']og:title[\"'][^>]+content=[\"']([^\"']+)[\"']",
            r"<meta[^>]+name=[\"']title[\"'][^>]+content=[\"']([^\"']+)[\"']",
            r"<title>(.*?)</title>",
            r"<h1[^>]*>(.*?)</h1>",
        ]
        for pattern in patterns:
            match = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
            if match is None:
                continue
            value = CatalogCandidateEnricher._clean_html_text(match.group(1))
            if value:
                return value
        return None

    def _normalize_name_from_page_title(self, value: str) -> str | None:
        cleaned = self._strip_noise(value)
        if not cleaned:
            return None

        cpu_match = self._CPU_NAME_PATTERN.search(cleaned)
        if cpu_match is not None:
            return self._clean_html_text(cpu_match.group(1))

        gpu_match = self._GPU_NAME_PATTERN.search(cleaned)
        if gpu_match is not None:
            return self._clean_html_text(gpu_match.group(1))

        return cleaned

    def _clean_candidate_name(self, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = self._strip_noise(value)
        if not cleaned:
            return None
        if self._looks_like_invalid_page(cleaned):
            return None
        if self._looks_like_compound_name(cleaned):
            return None
        if not re.search(r"\d", cleaned):
            return None
        if len(cleaned) < 6:
            return None
        return cleaned

    @classmethod
    def _strip_noise(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = cls._clean_html_text(value)
        cleaned = cls._STORE_SUFFIX_PATTERN.sub("", cleaned)
        cleaned = re.sub(r"\s*\|\s*Fan[áa]ticos.*$", "", cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.strip(" -|–")
        return cleaned or None

    @classmethod
    def _looks_like_invalid_page(cls, value: str | None) -> bool:
        normalized = cls._normalize_name(value)
        if not normalized:
            return False
        return any(marker in normalized for marker in cls._INVALID_PAGE_MARKERS)

    @classmethod
    def _looks_like_compound_name(cls, value: str | None) -> bool:
        normalized = cls._normalize_name(value)
        if not normalized:
            return False
        return any(marker in normalized for marker in cls._COMPOUND_MARKERS)

    @classmethod
    def _looks_like_compound_post(cls, raw_text: str | None) -> bool:
        normalized = cls._normalize_name(raw_text)
        if not normalized:
            return False
        if any(marker in normalized for marker in cls._COMPOUND_MARKERS):
            return True
        return normalized.count("http") > 2

    @classmethod
    def _extract_canonical_sku(cls, text: str) -> str | None:
        for pattern in cls._CANONICAL_SKU_PATTERNS:
            match = pattern.search(text)
            if match is None:
                continue
            return cls._clean_html_text(match.group(0)).upper()
        return None

    @staticmethod
    def _extract_first(pattern: str, text: str) -> str | None:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match is None:
            return None
        return CatalogCandidateEnricher._clean_html_text(match.group(1))

    @staticmethod
    def _extract_int(pattern: str, text: str) -> int | None:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match is None:
            return None
        return int(match.group(1))

    def _extract_capacity_gb(self, html: str, proposed_name: str) -> int | None:
        for text in [proposed_name, html]:
            match = re.search(r"\b(\d{1,5})\s*(TB|GB)\b", text, flags=re.IGNORECASE)
            if match is None:
                continue
            amount = int(match.group(1))
            unit = match.group(2).upper()
            return amount * 1024 if unit == "TB" else amount
        return None

    def _extract_gpu_memory_mb(self, html: str, proposed_name: str) -> int | None:
        for text in [proposed_name, html]:
            match = re.search(r"\b(\d{1,2})\s*GB\b", text, flags=re.IGNORECASE)
            if match is None:
                continue
            return int(match.group(1)) * 1024
        return None

    @staticmethod
    def _extract_gpu_category(name: str) -> str | None:
        lowered = name.lower()
        if "geforce" in lowered or "rtx" in lowered or "gtx" in lowered:
            return "desktop"
        if "radeon" in lowered or re.search(r"\brx\b", lowered):
            return "desktop"
        return None

    @staticmethod
    def _brand_from_name(name: str) -> str | None:
        tokens = name.split()
        if not tokens:
            return None
        return tokens[0]

    @staticmethod
    def _clean_html_text(value: str) -> str:
        cleaned = re.sub(r"<[^>]+>", " ", value)
        cleaned = cleaned.replace("&nbsp;", " ").replace("&amp;", "&")
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    @classmethod
    def _normalize_name(cls, value: str | None) -> str:
        if value is None:
            return ""
        normalized = cls._clean_html_text(value).lower()
        normalized = normalized.replace("ç", "c").replace("ã", "a").replace("á", "a").replace("â", "a")
        normalized = normalized.replace("é", "e").replace("ê", "e").replace("í", "i")
        normalized = normalized.replace("ó", "o").replace("ô", "o").replace("ú", "u")
        normalized = normalized.replace("ª", "a")
        return normalized

    @classmethod
    def _normalize_sku(cls, value: str | None) -> str:
        normalized = cls._normalize_name(value)
        normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
        normalized = re.sub(r"-{2,}", "-", normalized)
        return normalized.strip("-")

    @staticmethod
    def _slugify(value: str) -> str:
        lowered = value.lower()
        lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
        lowered = re.sub(r"-{2,}", "-", lowered)
        return lowered.strip("-")
