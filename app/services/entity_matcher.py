from __future__ import annotations

import re


class EntityMatcher:
    _MODEL_SUFFIXES = ("x3d", "xtx", "super", "gre", "ti", "ks", "kf", "xt", "k", "f", "x")
    _PROTECTED_TOKENS = {"ti", "super", "xt", "xtx", "gre", "x3d", "ks", "kf", "k", "f", "x"}
    _STOPWORDS = {
        "amd",
        "intel",
        "nvidia",
        "geforce",
        "radeon",
        "graphics",
        "graphic",
        "placa",
        "video",
        "de",
        "do",
        "da",
        "oc",
        "gddr6",
        "gddr7",
        "desktop",
        "processor",
        "core",
        "ryzen",
        "series",
    }

    def mismatch_reason(self, *, entity_name: str, raw_text: str) -> str | None:
        title_tokens = set(self._tokenize(self._extract_title(raw_text)))
        entity_tokens = set(self._tokenize(entity_name))

        required_tokens = {
            token
            for token in entity_tokens
            if token not in self._STOPWORDS
            and token not in self._PROTECTED_TOKENS
            and not token.endswith("gb")
            and not token.isdigit()
        }

        missing_required = sorted(token for token in required_tokens if token not in title_tokens)
        if missing_required:
            return f"mensagem rejeitada por falta de tokens obrigatorios: {', '.join(missing_required)}"

        entity_variants = {token for token in entity_tokens if token in self._PROTECTED_TOKENS}
        title_variants = {token for token in title_tokens if token in self._PROTECTED_TOKENS}

        extra_variants = sorted(title_variants - entity_variants)
        missing_variants = sorted(entity_variants - title_variants)

        family_reason = self._variant_family_reason(
            missing_variants=missing_variants,
            extra_variants=extra_variants,
        )
        if family_reason is not None:
            return family_reason

        if extra_variants:
            return f"mensagem rejeitada por discriminadores conflitantes: {', '.join(extra_variants)}"
        if missing_variants:
            return f"mensagem rejeitada por falta de discriminadores: {', '.join(missing_variants)}"

        entity_memory = {token for token in entity_tokens if token.endswith("gb")}
        title_memory = {token for token in title_tokens if token.endswith("gb")}
        if entity_memory:
            missing_memory = sorted(entity_memory - title_memory)
            if missing_memory:
                return f"mensagem rejeitada por falta de memoria declarada: {', '.join(missing_memory)}"

            extra_memory = sorted(title_memory - entity_memory)
            if extra_memory:
                return f"mensagem rejeitada por memoria conflitante: {', '.join(extra_memory)}"

        return None

    @staticmethod
    def _extract_title(raw_text: str) -> str:
        return raw_text.split("R$", 1)[0].strip()

    @staticmethod
    def _variant_family_reason(*, missing_variants: list[str], extra_variants: list[str]) -> str | None:
        for missing in missing_variants:
            for extra in extra_variants:
                if missing.startswith(extra) or extra.startswith(missing):
                    if len(missing) > len(extra):
                        return f"mensagem rejeitada por falta de discriminadores: {missing}"

                    return f"mensagem rejeitada por discriminadores conflitantes: {extra}"

        return None

    @classmethod
    def _tokenize(cls, value: str) -> list[str]:
        normalized = value.lower()
        normalized = re.sub(r"(\d+)\s*gb\b", r"\1gb", normalized)

        for suffix in cls._MODEL_SUFFIXES:
            normalized = re.sub(rf"\b(\d+)({suffix})\b", rf"\1 \2", normalized)

        normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
        return [token for token in normalized.split() if token]
