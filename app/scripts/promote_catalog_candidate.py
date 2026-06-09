from __future__ import annotations

import argparse

from app.core.database import close_mongo_client, get_catalog_candidate_collection, get_cpu_collection, get_daily_offer_collection, get_gpu_collection, get_motherboard_collection, get_psu_collection, get_ram_collection, get_ssd_collection
from app.repositories.catalog_candidate_repository import CatalogCandidateRepository
from app.repositories.daily_offer_repository import DailyOfferRepository
from app.schemas.common import EntityType
from app.services.catalog_candidate_enricher import CatalogCandidateEnricher
from app.services.catalog_candidate_pipeline import CatalogCandidatePipelineService
from app.services.catalog_reader import MongoCatalogReader
from app.services.telegram_offer_parser import TelegramOfferParser

_CATALOG_COLLECTIONS: dict[EntityType, object] = {
    "cpu": get_cpu_collection,
    "gpu": get_gpu_collection,
    "ssd": get_ssd_collection,
    "ram": get_ram_collection,
    "psu": get_psu_collection,
    "motherboard": get_motherboard_collection,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Promove um candidato de catalogo enriquecido para a colecao canonica.")
    parser.add_argument("--entity-type", choices=["cpu", "gpu", "ssd", "ram", "psu", "motherboard"], required=True)
    parser.add_argument("--fingerprint", required=True, help="Fingerprint do candidato a promover.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        collections = {k: getter() for k, getter in _CATALOG_COLLECTIONS.items()}
        catalog_reader = MongoCatalogReader(collections)
        pipeline = CatalogCandidatePipelineService(
            candidate_repository=CatalogCandidateRepository(get_catalog_candidate_collection()),
            daily_offer_repository=DailyOfferRepository(get_daily_offer_collection()),
            catalog_reader=catalog_reader,
            offer_parser=TelegramOfferParser(),
            enricher=CatalogCandidateEnricher(),
        )
        result = pipeline.promote_candidate(entity_type=args.entity_type, fingerprint=args.fingerprint)
        print(
            "Promocao concluida. "
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