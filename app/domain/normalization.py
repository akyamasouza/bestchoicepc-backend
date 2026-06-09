"""Consolidated normalization functions — single source of truth."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, unquote, urlparse

# ---------------------------------------------------------------------------
# Store name normalization
# ---------------------------------------------------------------------------

_STORE_ALIASES: dict[str, str] = {
    "amazon": "amazon",
    "amazoncombr": "amazon",
    "kabum": "kabum",
    "kabumcombr": "kabum",
    "kabumoficial": "kabum",
    "pichau": "pichau",
    "pichaucombr": "pichau",
    "terabyteshop": "terabyteshop",
    "terabyteshopcombr": "terabyteshop",
    "terabyte": "terabyteshop",
}

_KNOWN_STORES: set[str] = {"amazon", "kabum", "pichau", "terabyteshop"}

_STORE_SUFFIX_PATTERN = re.compile(
    r"\s*(?:\||-|–)\s*(?:kabum!?|amazon|pichau|terabyte(?:shop)?|waz|fan[aá]ticos por tecnologia).*?$",
    flags=re.IGNORECASE,
)


def normalize_store_name(store: str) -> str:
    """Normalize a store display name to its canonical form."""
    lowered = store.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "", lowered)
    return _STORE_ALIASES.get(normalized, normalized)


def store_from_url(url: str) -> str | None:
    """Extract the canonical store name from a URL, following affiliate redirects."""
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    candidates = [host]

    if "awin1.com" in host:
        query = parse_qs(parsed.query)
        redirected_url = query.get("ued", [None])[0]
        if redirected_url is not None:
            redirected = unquote(redirected_url)
            redirected_host = urlparse(redirected).netloc.lower()
            if redirected_host:
                candidates.insert(0, redirected_host)

    path = parsed.path.lower()
    if "amazon.com.br" in path:
        candidates.append("amazon.com.br")

    for candidate in candidates:
        candidate = re.sub(r"^www\.", "", candidate)
        normalized = re.sub(r"[^a-z0-9]+", "", candidate)
        store = normalize_store_name(normalized)
        if store in _KNOWN_STORES:
            return store

    return None


def strip_store_suffix(text: str) -> str:
    """Remove trailing store brand suffixes from a product name string."""
    return _STORE_SUFFIX_PATTERN.sub("", text).strip()


# ---------------------------------------------------------------------------
# Product name normalization (accent removal)
# ---------------------------------------------------------------------------

_ACCENT_MAP = str.maketrans(
    "çãáâéêíóôúª",
    "caaaeeiooua",
)


def normalize_product_name(value: str | None) -> str:
    """Lowercase, strip HTML, and remove Portuguese accents."""
    if value is None:
        return ""
    cleaned = clean_html_text(value)
    return cleaned.lower().translate(_ACCENT_MAP)


# ---------------------------------------------------------------------------
# SKU normalization / slugify
# ---------------------------------------------------------------------------

def normalize_sku(value: str | None) -> str:
    """Normalize a value into a URL-safe SKU slug (accent-strip + dash-join)."""
    normalized = normalize_product_name(value)
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized)
    return normalized.strip("-")


def slugify(value: str) -> str:
    """Convert a string to a URL-friendly slug."""
    lowered = value.lower()
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    lowered = re.sub(r"-{2,}", "-", lowered)
    return lowered.strip("-")


# ---------------------------------------------------------------------------
# Whitespace normalization
# ---------------------------------------------------------------------------

def normalize_whitespace(value: str) -> str:
    """Collapse whitespace and non-breaking spaces, trim."""
    return " ".join(value.replace("\xa0", " ").split()).strip()


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------

def clean_html_text(value: str) -> str:
    """Strip HTML tags, decode common HTML entities, collapse whitespace."""
    cleaned = re.sub(r"<[^>]+>", " ", value)
    cleaned = cleaned.replace("&nbsp;", " ").replace("&amp;", "&")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def fix_mojibake(value: str) -> str:
    """Heuristically re-encode latin-1 text that was misread as UTF-8."""
    if not any(token in value for token in ("Ã", "Â", "¢", "Õ")):
        return value
    try:
        return value.encode("latin-1").decode("utf-8")
    except UnicodeError:
        return value