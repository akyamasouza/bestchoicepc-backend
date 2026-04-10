import json

import httpx

from app.services.openrouter_product_normalizer import OpenRouterProductNormalizer
from tests.test_catalog_candidate_enricher import build_candidate


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


def test_normalizer_parses_valid_json(monkeypatch) -> None:
    monkeypatch.setattr("app.services.openrouter_product_normalizer.settings.openrouter_enabled", True)
    monkeypatch.setattr("app.services.openrouter_product_normalizer.settings.openrouter_api_key", "key")
    monkeypatch.setattr("app.services.openrouter_product_normalizer.settings.openrouter_model", "glm-5.1")

    def fake_post(*_args, **_kwargs):
        return FakeResponse(
            {
                "model": "z-ai/glm-5.1-20260406",
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "proposed_name": "AMD Ryzen 7 9800X3D",
                                    "proposed_sku": "amd-ryzen-7-9800x3d",
                                    "canonical_sku": "100-100001084WOF",
                                    "confidence": 0.96,
                                }
                            )
                        }
                    }
                ],
            }
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    identity = OpenRouterProductNormalizer().normalize(build_candidate("cpu", None, "AMD Ryzen 7 9800X3D"))

    assert identity is not None
    assert identity.proposed_name == "AMD Ryzen 7 9800X3D"
    assert identity.proposed_sku == "amd-ryzen-7-9800x3d"
    assert identity.canonical_sku == "100-100001084WOF"
    assert identity.model == "z-ai/glm-5.1-20260406"


def test_normalizer_returns_none_for_invalid_json(monkeypatch) -> None:
    monkeypatch.setattr("app.services.openrouter_product_normalizer.settings.openrouter_enabled", True)
    monkeypatch.setattr("app.services.openrouter_product_normalizer.settings.openrouter_api_key", "key")
    monkeypatch.setattr("app.services.openrouter_product_normalizer.settings.openrouter_model", "glm-5.1")

    def fake_post(*_args, **_kwargs):
        return FakeResponse({"choices": [{"message": {"content": "not-json"}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    identity = OpenRouterProductNormalizer().normalize(build_candidate("cpu", None, "AMD Ryzen 7 9800X3D"))

    assert identity is None
