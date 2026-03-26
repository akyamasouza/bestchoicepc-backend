from pymongo import ASCENDING

from app.core.database import close_mongo_client, get_gpu_collection
from app.data.gpus import GPUS


def seed_gpus() -> int:
    collection = get_gpu_collection()
    collection.create_index([("sku", ASCENDING)], unique=True)

    upserted = 0

    for gpu in GPUS:
        result = collection.update_one(
            {"sku": gpu["sku"]},
            {"$set": gpu},
            upsert=True,
        )
        upserted += int(result.upserted_id is not None or result.modified_count > 0)

    return upserted


def main() -> None:
    try:
        count = seed_gpus()
        print(f"Seed concluido. {count} documento(s) inserido(s) ou atualizado(s).")
    finally:
        close_mongo_client()


if __name__ == "__main__":
    main()
