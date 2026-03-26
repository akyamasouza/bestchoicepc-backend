from copy import deepcopy

from pymongo import ASCENDING

from app.core.database import close_mongo_client, get_cpu_collection
from app.data.cpus import CPUS
from app.data.cpu_techpowerup import resolve_techpowerup_cpu_application_score


def seed_cpus() -> int:
    collection = get_cpu_collection()
    collection.create_index([("sku", ASCENDING)], unique=True)

    upserted = 0

    for cpu in CPUS:
        document = _build_cpu_document(cpu)
        result = collection.update_one(
            {"sku": document["sku"]},
            {"$set": document},
            upsert=True,
        )
        upserted += int(result.upserted_id is not None or result.modified_count > 0)

    return upserted


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


def main() -> None:
    try:
        count = seed_cpus()
        print(f"Seed concluido. {count} documento(s) inserido(s) ou atualizado(s).")
    finally:
        close_mongo_client()


if __name__ == "__main__":
    main()

