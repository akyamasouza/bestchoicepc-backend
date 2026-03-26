from __future__ import annotations

import argparse
import asyncio

from app.core.database import close_mongo_client, get_cpu_collection, get_daily_offer_collection
from app.repositories.daily_offer_repository import DailyOfferRepository
from app.services.daily_offer_sync import DailyOfferSyncService
from app.services.telegram_offer_parser import TelegramOfferParser
from app.services.telegram_search import TelegramChannelSearchService


async def run(channel: str | None = None, limit: int = 1) -> int:
    telegram_search_service = TelegramChannelSearchService()
    daily_offer_repository = DailyOfferRepository(get_daily_offer_collection())
    sync_service = DailyOfferSyncService(
        cpu_collection=get_cpu_collection(),
        daily_offer_repository=daily_offer_repository,
        telegram_search_service=telegram_search_service,
        offer_parser=TelegramOfferParser(),
    )

    try:
        result = await sync_service.sync(channel=channel, limit=limit)
    finally:
        await telegram_search_service.close()

    print(
        "Sync concluido. "
        f"processadas={result.processed}, "
        f"encontradas={result.matched}, "
        f"persistidas={result.persisted}, "
        f"ignoradas={result.skipped}, "
        f"erros={len(result.errors)}"
    )

    for error in result.errors:
        print(f"- {error}")

    return 0 if not result.errors else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sincroniza ofertas diarias de CPUs a partir do Telegram.")
    parser.add_argument("--channel", help="Canal do Telegram. Se omitido, usa TELEGRAM_DEFAULT_CHANNEL.")
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="Quantidade maxima de mensagens por consulta. O padrao e 1.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        raise SystemExit(asyncio.run(run(channel=args.channel, limit=args.limit)))
    finally:
        close_mongo_client()


if __name__ == "__main__":
    main()
