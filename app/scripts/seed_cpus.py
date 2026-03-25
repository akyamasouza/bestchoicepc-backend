from pymongo import ASCENDING

from app.core.database import close_mongo_client, get_cpu_collection
from app.data.cpus import CPUS


def seed_cpus() -> int:
    collection = get_cpu_collection()
    collection.create_index([("sku", ASCENDING)], unique=True)

    upserted = 0

    for cpu in CPUS:
        result = collection.update_one(
            {"sku": cpu["sku"]},
            {"$set": cpu},
            upsert=True,
        )
        upserted += int(result.upserted_id is not None or result.modified_count > 0)

    return upserted


def main() -> None:
    try:
        count = seed_cpus()
        print(f"Seed concluido. {count} documento(s) inserido(s) ou atualizado(s).")
    finally:
        close_mongo_client()


if __name__ == "__main__":
    main()

