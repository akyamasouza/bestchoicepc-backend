from pymongo import ASCENDING

from app.core.database import close_mongo_client, get_psu_collection
from app.data.psus import PSUS
from app.services.psu_ranking import PsuRankingEntry, PsuRankingService


def seed_psus() -> int:
    collection = get_psu_collection()
    collection.create_index([("sku", ASCENDING)], unique=True)

    ranking_service = PsuRankingService()
    rankings = ranking_service.build_rankings(
        [
            PsuRankingEntry(
                identifier=psu["sku"],
                name=psu["name"],
                cybenetics_score=(psu.get("benchmark") or {}).get("cybenetics_score"),
            )
            for psu in PSUS
        ]
    )

    upserted = 0

    for psu in PSUS:
        ranking = rankings.get(psu["sku"])
        seeded_psu = {
            **psu,
            "ranking": {
                "game_score": ranking.game_score,
                "game_percentile": ranking.game_percentile,
                "performance_tier": ranking.performance_tier,
            }
            if ranking is not None
            else None,
        }

        result = collection.update_one(
            {"sku": psu["sku"]},
            {"$set": seeded_psu},
            upsert=True,
        )
        upserted += int(result.upserted_id is not None or result.modified_count > 0)

    return upserted


def main() -> None:
    try:
        count = seed_psus()
        print(f"Seed concluido. {count} documento(s) inserido(s) ou atualizado(s).")
    finally:
        close_mongo_client()


if __name__ == "__main__":
    main()
