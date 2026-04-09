from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

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


def test_build_client_kwargs_ignores_missing_proxy_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    monkeypatch.delenv("HTTP_PROXY", raising=False)

    assert TelegramChannelSearchService._build_client_kwargs() == {}



def test_build_client_kwargs_uses_https_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://10.120.164.14:3128")
    monkeypatch.delenv("HTTP_PROXY", raising=False)

    assert TelegramChannelSearchService._build_client_kwargs() == {
        "proxy": {
            "proxy_type": "http",
            "addr": "10.120.164.14",
            "port": 3128,
            "username": None,
            "password": None,
        }
    }



def test_build_client_kwargs_rejects_invalid_proxy_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://10.120.164.14:not-a-port")
    monkeypatch.delenv("HTTP_PROXY", raising=False)

    with pytest.raises(RuntimeError, match="valid port"):
        TelegramChannelSearchService._build_client_kwargs()



def test_build_client_kwargs_rejects_unsupported_proxy_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "ftp://10.120.164.14:3128")
    monkeypatch.delenv("HTTP_PROXY", raising=False)

    with pytest.raises(RuntimeError, match="Unsupported Telegram proxy scheme"):
        TelegramChannelSearchService._build_client_kwargs()



def test_build_client_kwargs_falls_back_to_http_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    monkeypatch.setenv("HTTP_PROXY", "http://10.120.164.14:3128")

    assert TelegramChannelSearchService._build_client_kwargs() == {
        "proxy": {
            "proxy_type": "http",
            "addr": "10.120.164.14",
            "port": 3128,
            "username": None,
            "password": None,
        }
    }



def test_build_client_kwargs_keeps_proxy_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://usuario:senha@10.120.164.14:3128")
    monkeypatch.delenv("HTTP_PROXY", raising=False)

    assert TelegramChannelSearchService._build_client_kwargs() == {
        "proxy": {
            "proxy_type": "http",
            "addr": "10.120.164.14",
            "port": 3128,
            "username": "usuario",
            "password": "senha",
        }
    }



def test_create_client_passes_proxy_kwargs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://10.120.164.14:3128")
    monkeypatch.delenv("HTTP_PROXY", raising=False)
    captured: dict[str, object] = {}

    class FakeTelegramClient:
        def __init__(self, session: str, api_id: int, api_hash: str, **kwargs: object) -> None:
            captured["session"] = session
            captured["api_id"] = api_id
            captured["api_hash"] = api_hash
            captured["kwargs"] = kwargs

    monkeypatch.setattr("app.services.telegram_search.TelegramClient", FakeTelegramClient)

    client = TelegramChannelSearchService._create_client("session-file", 123, "hash")

    assert client is not None
    assert captured == {
        "session": "session-file",
        "api_id": 123,
        "api_hash": "hash",
        "kwargs": {
            "proxy": {
                "proxy_type": "http",
                "addr": "10.120.164.14",
                "port": 3128,
                "username": None,
                "password": None,
            }
        },
    }



def test_create_client_without_proxy_passes_no_extra_kwargs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    monkeypatch.delenv("HTTP_PROXY", raising=False)
    captured: dict[str, object] = {}

    class FakeTelegramClient:
        def __init__(self, session: str, api_id: int, api_hash: str, **kwargs: object) -> None:
            captured["session"] = session
            captured["api_id"] = api_id
            captured["api_hash"] = api_hash
            captured["kwargs"] = kwargs

    monkeypatch.setattr("app.services.telegram_search.TelegramClient", FakeTelegramClient)

    client = TelegramChannelSearchService._create_client("session-file", 123, "hash")

    assert client is not None
    assert captured == {
        "session": "session-file",
        "api_id": 123,
        "api_hash": "hash",
        "kwargs": {},
    }



def test_ensure_api_credentials_rejects_missing_values() -> None:
    with pytest.raises(RuntimeError, match="TELEGRAM_API_ID and TELEGRAM_API_HASH"):
        TelegramChannelSearchService._ensure_api_credentials(None, None)



def test_ensure_api_credentials_returns_values() -> None:
    assert TelegramChannelSearchService._ensure_api_credentials(123, "hash") == (123, "hash")



def test_session_path_returns_path() -> None:
    service = TelegramChannelSearchService(
        api_id=123,
        api_hash="hash",
        default_channel="@pcbuildwizard",
        session_path=".telegram/session",
    )

    assert service._session_path() == Path(".telegram/session")



def test_close_disconnects_cached_client() -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.disconnected = False

        async def disconnect(self) -> None:
            self.disconnected = True

    service = TelegramChannelSearchService(
        api_id=123,
        api_hash="hash",
        default_channel="@pcbuildwizard",
        session_path=".telegram/session",
    )
    fake_client = FakeClient()
    service._client = fake_client

    import asyncio

    asyncio.run(service.close())

    assert fake_client.disconnected is True
    assert service._client is None
