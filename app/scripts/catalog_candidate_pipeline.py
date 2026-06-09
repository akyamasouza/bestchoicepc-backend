from __future__ import annotations

import argparse

from app.core.database import (
    close_mongo_client,
    get_catalog_candidate_collection,
    get_cpu_collection,
    get_daily_offer_collection,
    get_gpu_collection,
    get_motherboard_collection,
    get_psu_collection,
    get_ram_collection,
    get_ssd_collection,
)
from app.adapters.ai.enricher import CatalogCandidateEnricher
from app.adapters.mongodb.catalog_reader import MongoCatalogReader
from app.adapters.telegram.parser import TelegramOfferParser
from app.application.candidate_pipeline import CatalogCandidatePipelineService
from app.repositories.catalog_candidate_repository import CatalogCandidateRepository
from app.repositories.daily_offer_repository import DailyOfferRepository
from app.schemas.common import EntityType

_CATALOG_COLLECTIONS: dict[EntityType, object] = {
    "cpu": get_cpu_collection,
    "gpu": get_gpu_collection,
    "ssd": get_ssd_collection,
    "ram": get_ram_collection,
    "psu": get_psu_collection,
    "motherboard": get_motherboard_collection,
}


def _build_pipeline() -> CatalogCandidatePipelineService:
    collections = {k: getter() for k, getter in _CATALOG_COLLECTIONS.items()}
    catalog_reader = MongoCatalogReader(collections)
    return CatalogCandidatePipelineService(
        candidate_repository=CatalogCandidateRepository(get_catalog_candidate_collection()),
        daily_offer_repository=DailyOfferRepository(get_daily_offer_collection()),
        catalog_reader=catalog_reader,
        offer_parser=TelegramOfferParser(),
        enricher=CatalogCandidateEnricher(),
    )


def run_enrich(*, entity_type: EntityType | None = None) -> None:
    pipeline = _build_pipeline()
    result = pipeline.enrich_pending_candidates(entity_type=entity_type)
    print(
        "Enriquecimento concluido. "
        f"enriquecidos={result.enriched}, "
        f"erros={len(result.errors)}"
    )
    for error in result.errors:
        print(f"- {error}")


def run_promote(*, entity_type: EntityType, fingerprint: str) -> None:
    pipeline = _build_pipeline()
    result = pipeline.promote_candidate(entity_type=entity_type, fingerprint=fingerprint)
    print(
        "Promocao concluida. "
        f"promovidos={result.promoted}, "
        f"ofertas_persistidas={result.offers_persisted}, "
        f"erros={len(result.errors)}"
    )
    for error in result.errors:
        print(f"- {error}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pipeline de candidatos de catalogo detectados via Telegram.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    enrich_parser = subparsers.add_parser("enrich", help="Enriquece candidatos pendentes.")
    enrich_parser.add_argument(
        "--entity-type",
        choices=["cpu", "gpu", "ssd", "ram", "psu", "motherboard"],
        help="Filtra enriquecimento por tipo de entidade.",
    )

    promote_parser = subparsers.add_parser("promote", help="Promove candidato enriquecido para o catalogo canonico.")
    promote_parser.add_argument("--entity-type", choices=["cpu", "gpu", "ssd", "ram", "psu", "motherboard"], required=True)
    promote_parser.add_argument("--fingerprint", required=True, help="Fingerprint do candidato a promover.")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "enrich":
            run_enrich(entity_type=args.entity_type)
        elif args.command == "promote":
            run_promote(entity_type=args.entity_type, fingerprint=args.fingerprint)
    finally:
        close_mongo_client()


if __name__ == "__main__":
    main()