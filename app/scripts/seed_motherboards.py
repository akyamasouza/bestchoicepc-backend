from pymongo import ASCENDING

from app.core.database import close_mongo_client, get_motherboard_collection
from app.data.motherboards import MOTHERBOARDS


def seed_motherboards() -> int:
    collection = get_motherboard_collection()
    collection.create_index([("sku", ASCENDING)], unique=True)

    upserted = 0
    current_skus: list[str] = []
    for motherboard in MOTHERBOARDS:
        current_skus.append(motherboard["sku"])
        result = collection.replace_one(
            {"sku": motherboard["sku"]},
            motherboard,
            upsert=True,
        )
        upserted += int(result.upserted_id is not None or result.modified_count > 0)

    collection.delete_many({"sku": {"$nin": current_skus}})
    return upserted


def main() -> None:
    try:
        count = seed_motherboards()
        print(f"Seed concluido. {count} documento(s) inserido(s) ou atualizado(s).")
    finally:
        close_mongo_client()


if __name__ == "__main__":
    main()
