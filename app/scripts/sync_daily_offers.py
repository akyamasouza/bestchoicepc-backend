from __future__ import annotations

import argparse
import asyncio

from app.core.database import (
    coerce_document_id,
    close_mongo_client,
    get_catalog_candidate_collection,
    get_daily_offer_collection,
)
from app.repositories.catalog_candidate_repository import CatalogCandidateRepository
from app.repositories.daily_offer_repository import DailyOfferRepository
from app.services.catalog_candidate_enricher import CatalogCandidateEnricher
from app.services.catalog_candidate_pipeline import CatalogCandidatePipelineService
from app.services.daily_offer_pipeline import DailyOfferPipeline, TelegramSearchStrategy
from app.services.daily_offer_sync import DailyOfferSyncService
from app.services.hardware_registry import get_hardware_entity_config
from app.services.telegram_offer_parser import TelegramOfferParser
from app.services.telegram_search import TelegramChannelSearchService


def get_catalog_collection(entity_type: str):
    return get_hardware_entity_config(entity_type).collection_getter()


async def run(entity_type: str = "cpu", channel: str | None = None, limit: int = 1, object_id: str | None = None) -> int:
    telegram_search_service = TelegramChannelSearchService()
    search_strategy = TelegramSearchStrategy(telegram_search_service)

    # New pipeline
    pipeline = DailyOfferPipeline(search_strategy=search_strategy)

    try:
        result = await pipeline.run(entity_type=entity_type, channel=channel, limit=limit)
    finally:
        await telegram_search_service.close()

    print(
        "Sync concluido. "
        f"processadas={result.processed}, "
        f"encontradas={result.matched}, "
        f"candidatos_criados={result.candidates_created}, "
        f"persistidas={result.persisted}, "
        f"erros={len(result.errors)}"
    )

    for error in result.errors:
        print(f"- {error}")

    return 0 if not result.errors else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sincroniza ofertas diarias por tipo de entidade a partir do Telegram.")
    parser.add_argument(
        "--entity-type",
        choices=["cpu", "gpu", "ssd", "ram", "psu", "motherboard"],
        default="cpu",
        help="Tipo de entidade a sincronizar. O padrao e cpu.",
    )
    parser.add_argument("--channel", help="Canal do Telegram. Se omitido, usa TELEGRAM_DEFAULT_CHANNEL.")
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="Quantidade maxima de mensagens por consulta. O padrao e 1.",
    )
    parser.add_argument(
        "--id",
        help="ObjectId exato do produto no MongoDB para sincronizar isoladamente.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        raise SystemExit(asyncio.run(run(
            entity_type=args.entity_type, 
            channel=args.channel, 
            limit=args.limit, 
            object_id=args.id
        )))
    finally:
        close_mongo_client()


if __name__ == "__main__":
    main()
