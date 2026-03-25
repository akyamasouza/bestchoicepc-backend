from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import sys
from typing import Any

from telethon import TelegramClient, functions, types

from app.core.config import settings


@dataclass(slots=True)
class TelegramMessage:
    id: int | None
    date: int | None
    date_iso: str | None
    text: str
    excerpt: str
    views: int | None
    forwards: int | None
    url: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "date": self.date,
            "date_iso": self.date_iso,
            "text": self.text,
            "excerpt": self.excerpt,
            "views": self.views,
            "forwards": self.forwards,
            "url": self.url,
        }


class TelegramChannelSearchService:
    def __init__(
        self,
        *,
        api_id: int | None = None,
        api_hash: str | None = None,
        default_channel: str | None = None,
        session_path: str | None = None,
    ) -> None:
        self.api_id = api_id if api_id is not None else settings.telegram_api_id
        self.api_hash = api_hash if api_hash is not None else settings.telegram_api_hash
        self.default_channel = default_channel if default_channel is not None else settings.telegram_default_channel
        self.session_path = session_path if session_path is not None else settings.telegram_session_path
        self._client: TelegramClient | None = None

    async def search_channel(
        self,
        query: str,
        channel: str | None = None,
        limit: int = 1,
    ) -> list[dict[str, Any]]:
        resolved_channel = channel or self.default_channel

        if not resolved_channel:
            raise RuntimeError("Configure TELEGRAM_DEFAULT_CHANNEL before searching.")

        if not query.strip():
            raise RuntimeError("Provide a non-empty query before searching Telegram.")

        client = await self.client()
        peer = await client.get_input_entity(resolved_channel)

        result = await client(
            functions.messages.SearchRequest(
                peer=peer,
                q=query,
                filter=types.InputMessagesFilterEmpty(),
                min_date=0,
                max_date=0,
                offset_id=0,
                add_offset=0,
                limit=max(1, limit),
                max_id=0,
                min_id=0,
                hash=0,
            )
        )

        return [
            message.to_dict()
            for message in (
                self.normalize_message(raw_message, resolved_channel)
                for raw_message in result.messages
            )
            if message.text
        ]

    async def client(self) -> TelegramClient:
        if self._client is not None:
            return self._client

        if self.api_id is None or not self.api_hash:
            raise RuntimeError("Configure TELEGRAM_API_ID and TELEGRAM_API_HASH before using the Telegram API.")

        session_path = Path(self.session_path)
        session_path.parent.mkdir(parents=True, exist_ok=True)

        client = TelegramClient(str(session_path), self.api_id, self.api_hash)
        await client.connect()

        if not await client.is_user_authorized():
            await client.disconnect()
            raise RuntimeError(
                "Telegram session is not initialized. Run `python -m app.scripts.telegram_login` interactively first."
            )

        self._client = client

        return client

    async def login(self) -> None:
        if self.api_id is None or not self.api_hash:
            raise RuntimeError("Configure TELEGRAM_API_ID and TELEGRAM_API_HASH before using the Telegram API.")

        if not sys.stdin.isatty():
            raise RuntimeError("Interactive Telegram login requires a TTY.")

        session_path = Path(self.session_path)
        session_path.parent.mkdir(parents=True, exist_ok=True)

        client = TelegramClient(str(session_path), self.api_id, self.api_hash)

        try:
            await client.start()
        finally:
            await client.disconnect()

    async def close(self) -> None:
        if self._client is None:
            return

        await self._client.disconnect()
        self._client = None

    @staticmethod
    def normalize_message(message: Any, channel: str) -> TelegramMessage:
        text = TelegramChannelSearchService._normalize_text(getattr(message, "message", "") or "")
        message_id = getattr(message, "id", None)
        date = TelegramChannelSearchService._normalize_date(getattr(message, "date", None))
        channel_handle = channel.lstrip("@")

        return TelegramMessage(
            id=message_id,
            date=int(date.timestamp()) if date is not None else None,
            date_iso=date.isoformat() if date is not None else None,
            text=text,
            excerpt=TelegramChannelSearchService._excerpt(text),
            views=getattr(message, "views", None),
            forwards=getattr(message, "forwards", None),
            url=f"https://t.me/{channel_handle}/{message_id}" if channel_handle and message_id is not None else None,
        )

    @staticmethod
    def _normalize_text(text: str) -> str:
        return " ".join(text.split()).strip()

    @staticmethod
    def _excerpt(text: str, limit: int = 200) -> str:
        if len(text) <= limit:
            return text

        return text[: limit - 3].rstrip() + "..."

    @staticmethod
    def _normalize_date(value: Any) -> datetime | None:
        if value is None:
            return None

        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=UTC)

            return value.astimezone(UTC)

        return datetime.fromtimestamp(int(value), tz=UTC)
