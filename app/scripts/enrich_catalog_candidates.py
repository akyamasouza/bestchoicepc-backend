from __future__ import annotations

import argparse

from app.core.database import close_mongo_client, get_catalog_candidate_collection, get_daily_offer_collection
from app.repositories.catalog_candidate_repository import CatalogCandidateRepository
from app.repositories.daily_offer_repository import DailyOfferRepository
from app.services.catalog_candidate_enricher import CatalogCandidateEnricher
from app.services.catalog_candidate_pipeline import CatalogCandidatePipelineService
from app.services.telegram_offer_parser import TelegramOfferParser


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enriquece candidatos de catalogo detectados via Telegram.")
    parser.add_argument(
        "--entity-type",
        choices=["cpu", "gpu", "ssd", "ram", "psu", "motherboard"],
        help="Filtra enriquecimento por tipo de entidade.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        pipeline = CatalogCandidatePipelineService(
            candidate_repository=CatalogCandidateRepository(get_catalog_candidate_collection()),
            daily_offer_repository=DailyOfferRepository(get_daily_offer_collection()),
            offer_parser=TelegramOfferParser(),
            enricher=CatalogCandidateEnricher(),
        )
        result = pipeline.enrich_pending_candidates(entity_type=args.entity_type)
        print(
            "Enriquecimento concluido. "
            f"enriquecidos={result.enriched}, "
            f"promovidos={result.promoted}, "
            f"ofertas_persistidas={result.offers_persisted}, "
            f"erros={len(result.errors)}"
        )
        for error in result.errors:
            print(f"- {error}")
    finally:
        close_mongo_client()


if __name__ == "__main__":
    main()
