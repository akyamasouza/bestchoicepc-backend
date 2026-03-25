from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from app.services.telegram_search import TelegramChannelSearchService


def test_normalize_message_creates_expected_payload() -> None:
    message = SimpleNamespace(
        id=321,
        date=datetime(2026, 3, 25, 12, 30, tzinfo=UTC),
        message="  Oferta   Ryzen 7 9800X3D   por R$ 3.499  ",
        views=1500,
        forwards=42,
    )

    result = TelegramChannelSearchService.normalize_message(message, "@pcbuildwizard")

    assert result.id == 321
    assert result.date == 1774441800
    assert result.date_iso == "2026-03-25T12:30:00+00:00"
    assert result.text == "Oferta Ryzen 7 9800X3D por R$ 3.499"
    assert result.excerpt == "Oferta Ryzen 7 9800X3D por R$ 3.499"
    assert result.views == 1500
    assert result.forwards == 42
    assert result.url == "https://t.me/pcbuildwizard/321"


def test_normalize_message_handles_missing_text() -> None:
    message = SimpleNamespace(id=10, date=None, message="", views=None, forwards=None)

    result = TelegramChannelSearchService.normalize_message(message, "@pcbuildwizard")

    assert result.text == ""
    assert result.excerpt == ""
    assert result.date is None
    assert result.date_iso is None
    assert result.url == "https://t.me/pcbuildwizard/10"
