from copy import deepcopy

from app.core.database import close_mongo_client, get_cpu_collection
from app.data.cpu_techpowerup import resolve_techpowerup_cpu_application_score
from app.data.cpus import CPUS
from app.repositories.protocols import ASCENDING
from app.services.cpu_ranking import CpuRankingEntry, CpuRankingService


def seed_cpus() -> int:
    collection = get_cpu_collection()
    collection.create_index([("sku", ASCENDING)], unique=True)

    upserted = 0
    seeded_documents = _build_seed_documents()

    for document in seeded_documents:
        result = collection.update_one(
            {"sku": document["sku"]},
            {"$set": document},
            upsert=True,
        )
        upserted += int(result.upserted_id is not None or result.modified_count > 0)

    return upserted


def _build_seed_documents() -> list[dict]:
    documents = [_build_cpu_document(cpu) for cpu in CPUS]
    rankings = CpuRankingService().build_rankings(
        [
            CpuRankingEntry(
                identifier=document["sku"],
                name=document["name"],
                benchmark_score=_coerce_score(document.get("benchmark"), "single_thread_rating"),
                techpowerup_score=_coerce_score(
                    document.get("benchmark"),
                    "techpowerup_relative_performance_applications",
                ),
            )
            for document in documents
        ]
    )

    for document in documents:
        ranking = rankings.get(document["sku"])
        if ranking is None:
            document.pop("ranking", None)
            continue

        document["ranking"] = {
            "game_score": ranking.game_score,
            "game_percentile": ranking.game_percentile,
            "performance_tier": ranking.performance_tier,
        }

    return documents


def _build_cpu_document(cpu: dict) -> dict:
    document = deepcopy(cpu)
    benchmark = dict(document.get("benchmark") or {})
    score = resolve_techpowerup_cpu_application_score(
        document.get("name"),
        document.get("other_names"),
    )

    if score is not None:
        benchmark["techpowerup_relative_performance_applications"] = score

    document["benchmark"] = benchmark
    return document


def _coerce_score(benchmark: dict | None, field: str) -> float | None:
    value = (benchmark or {}).get(field)
    if value is None:
        return None

    return float(value)


def main() -> None:
    try:
        count = seed_cpus()
        print(f"Seed concluido. {count} documento(s) inserido(s) ou atualizado(s).")
    finally:
        close_mongo_client()


if __name__ == "__main__":
    main()

