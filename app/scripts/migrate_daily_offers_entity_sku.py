from __future__ import annotations

import argparse

from app.core.database import (
    close_mongo_client,
    get_cpu_collection,
    get_daily_offer_collection,
    get_gpu_collection,
    get_motherboard_collection,
    get_psu_collection,
    get_ram_collection,
    get_ssd_collection,
)
from app.services.daily_offer_legacy_migrator import DailyOfferLegacyMigrator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preenche entity_id e entity_sku em daily_offers legados usando match contra o catalogo."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica as atualizacoes. Sem esta flag, roda em modo dry-run.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    migrator = DailyOfferLegacyMigrator(
        daily_offer_collection=get_daily_offer_collection(),
        catalog_collections={
            "cpu": get_cpu_collection(),
            "gpu": get_gpu_collection(),
            "ssd": get_ssd_collection(),
            "ram": get_ram_collection(),
            "psu": get_psu_collection(),
            "motherboard": get_motherboard_collection(),
        },
    )

    try:
        result = migrator.migrate(apply=args.apply)
    finally:
        close_mongo_client()

    mode = "apply" if args.apply else "dry-run"
    print(
        f"Migracao daily_offers entity_sku ({mode}) concluida. "
        f"analisadas={result.scanned}, "
        f"migraveis={result.migrated}, "
        f"sem_match={result.unresolved}, "
        f"erros={len(result.errors)}"
    )
    for error in result.errors:
        print(f"- {error}")


if __name__ == "__main__":
    main()
