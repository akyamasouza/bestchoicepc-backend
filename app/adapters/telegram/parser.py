from __future__ import annotations

from datetime import UTC, datetime
import re
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.domain.normalization import normalize_store_name, store_from_url
from app.schemas.daily_offer import DailyOffer


class TelegramOfferParser:
    _PRICE_PATTERN = re.compile(r"R\$\s*([\d\.\,]+)")
    _INSTALLMENTS_PATTERN = re.compile(r"em\s+(\d+)\s+parcelas", re.IGNORECASE)
    _STORE_PATTERN = re.compile(r"Loja:\s*(.*?)\s+(https?://\S+)", re.IGNORECASE)
    _LOWEST_90D_PATTERN = re.compile(r"Menor preço em 90 dias:\s*R\$\s*([\d\.\,]+)", re.IGNORECASE)
    _MEDIAN_90D_PATTERN = re.compile(r"Mediana dos preços de 90 dias:\s*R\$\s*([\d\.\,]+)", re.IGNORECASE)
    _URL_PATTERN = re.compile(r"https?://\S+")

    def __init__(self, business_timezone: str | None = None) -> None:
        self.business_timezone = ZoneInfo(business_timezone or settings.business_timezone)

    def parse(
        self,
        message: dict[str, object],
        *,
        entity_type: str,
        entity_id: str,
        entity_sku: str,
        entity_name: str,
    ) -> DailyOffer:
        text = str(message.get("text") or "").strip()

        if not text:
            raise ValueError("Telegram message does not contain text.")

        store_display_name, source_url = self._parse_store_and_url(text)
        posted_at = self._parse_posted_at(message.get("date_iso"))

        return DailyOffer(
            business_date=posted_at.astimezone(self.business_timezone).date().isoformat(),
            entity_type=entity_type,
            entity_id=entity_id,
            entity_sku=entity_sku,
            entity_name=entity_name,
            store=normalize_store_name(store_display_name),
            store_display_name=store_display_name,
            price_card=self._parse_price(text),
            installments=self._parse_installments(text),
            source_url=source_url,
            telegram_message_id=self._parse_int(message.get("id")),
            telegram_message_url=self._parse_optional_str(message.get("url")),
            posted_at=posted_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            lowest_price_90d=self._parse_optional_price(self._LOWEST_90D_PATTERN, text),
            median_price_90d=self._parse_optional_price(self._MEDIAN_90D_PATTERN, text),
            raw_text=text,
        )

    def _parse_store_and_url(self, text: str) -> tuple[str, str | None]:
        match = self._STORE_PATTERN.search(text)
        if match is not None:
            return match.group(1).strip(), match.group(2).strip()

        url_match = self._URL_PATTERN.search(text)
        if url_match is None:
            raise ValueError("Could not extract store from Telegram message.")

        source_url = url_match.group(0).strip()
        store = store_from_url(source_url)
        if store is None:
            raise ValueError("Could not extract store from Telegram message.")

        return store, source_url

    def _parse_price(self, text: str) -> float:
        match = self._PRICE_PATTERN.search(text)
        if match is None:
            raise ValueError("Could not extract price from Telegram message.")

        return self._normalize_brl(match.group(1))

    def _parse_installments(self, text: str) -> int | None:
        match = self._INSTALLMENTS_PATTERN.search(text)
        if match is None:
            return None

        return int(match.group(1))

    def _parse_optional_price(self, pattern: re.Pattern[str], text: str) -> float | None:
        match = pattern.search(text)
        if match is None:
            return None

        return self._normalize_brl(match.group(1))

    def _parse_posted_at(self, value: object) -> datetime:
        if value is None:
            raise ValueError("Telegram message does not contain a valid date.")

        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=UTC)

            return value.astimezone(UTC)

        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)

    @staticmethod
    def _parse_int(value: object) -> int | None:
        if value is None:
            return None

        return int(value)

    @staticmethod
    def _parse_optional_str(value: object) -> str | None:
        if value is None:
            return None

        parsed = str(value).strip()
        return parsed or None

    @staticmethod
    def _normalize_brl(value: str) -> float:
        return float(value.replace(".", "").replace(",", "."))