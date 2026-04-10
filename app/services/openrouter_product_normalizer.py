from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Protocol

import httpx

from app.core.config import settings
from app.schemas.catalog_candidate import CatalogCandidate


class ProductIdentityNormalizerProtocol(Protocol):
    def normalize(self, candidate: CatalogCandidate) -> "NormalizedProductIdentity | None": ...


@dataclass(frozen=True, slots=True)
class NormalizedProductIdentity:
    proposed_name: str
    proposed_sku: str
    canonical_sku: str | None = None
    confidence: float | None = None
    source: str = "openrouter"
    model: str | None = None


class OpenRouterProductNormalizer:
    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    def normalize(self, candidate: CatalogCandidate) -> NormalizedProductIdentity | None:
        if not settings.openrouter_enabled:
            return None
        if not settings.openrouter_api_key or not settings.openrouter_model:
            return None

        payload = self._build_payload(candidate)
        response = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        message = ((data.get("choices") or [{}])[0].get("message") or {})
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            return None

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return None
        proposed_name = str(parsed.get("proposed_name") or "").strip()
        proposed_sku = str(parsed.get("proposed_sku") or "").strip()
        if not proposed_name or not proposed_sku:
            return None

        canonical_sku = parsed.get("canonical_sku")
        confidence = parsed.get("confidence")
        return NormalizedProductIdentity(
            proposed_name=proposed_name,
            proposed_sku=proposed_sku,
            canonical_sku=str(canonical_sku).strip() if canonical_sku else None,
            confidence=float(confidence) if confidence is not None else None,
            model=str(data.get("model") or settings.openrouter_model),
        )

    @staticmethod
    def _build_payload(candidate: CatalogCandidate) -> dict:
        return {
            "model": settings.openrouter_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Output only compact JSON. No reasoning. No markdown. No extra text. "
                        "Required keys: proposed_name, proposed_sku, canonical_sku, confidence. "
                        "Do not invent technical specs."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "entity_type": candidate.entity_type,
                            "raw_title": candidate.raw_title,
                            "raw_text": candidate.raw_text,
                            "proposed_name": candidate.proposed_name,
                            "related_catalog_entity_name": candidate.related_catalog_entity_name,
                            "related_catalog_entity_sku": candidate.related_catalog_entity_sku,
                            "product_url": candidate.product_url,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "max_tokens": 1200,
        }
