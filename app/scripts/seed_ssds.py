from app.core.database import close_mongo_client, get_ssd_collection
from app.data.ssds import SSDS
from app.repositories.protocols import ASCENDING
from app.services.ssd_ranking import SsdRankingEntry, SsdRankingService


def seed_ssds() -> int:
    collection = get_ssd_collection()
    collection.create_index([("sku", ASCENDING)], unique=True)

    ranking_service = SsdRankingService()
    rankings = ranking_service.build_rankings(
        [
            SsdRankingEntry(
                identifier=ssd["sku"],
                name=ssd["name"],
                ssd_tester_score=(ssd.get("benchmark") or {}).get("ssd_tester_score"),
            )
            for ssd in SSDS
        ]
    )

    upserted = 0

    for ssd in SSDS:
        ranking = rankings.get(ssd["sku"])
        seeded_ssd = {
            **ssd,
            "ranking": {
                "game_score": ranking.game_score,
                "game_percentile": ranking.game_percentile,
                "performance_tier": ranking.performance_tier,
            }
            if ranking is not None
            else None,
        }

        result = collection.update_one(
            {"sku": ssd["sku"]},
            {"$set": seeded_ssd},
            upsert=True,
        )
        upserted += int(result.upserted_id is not None or result.modified_count > 0)

    return upserted


def main() -> None:
    try:
        count = seed_ssds()
        print(f"Seed concluido. {count} documento(s) inserido(s) ou atualizado(s).")
    finally:
        close_mongo_client()


if __name__ == "__main__":
    main()
