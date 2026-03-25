from __future__ import annotations

import asyncio

from app.services.telegram_search import TelegramChannelSearchService


async def run() -> int:
    service = TelegramChannelSearchService()
    await service.login()
    print("Telegram session initialized successfully.")
    return 0


def main() -> int:
    try:
        return asyncio.run(run())
    except RuntimeError as exc:
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
