from app.core.database import close_mongo_client, get_ram_collection
from app.data.rams import RAMS
from app.repositories.protocols import ASCENDING


def seed_rams() -> int:
    collection = get_ram_collection()
    collection.create_index([("sku", ASCENDING)], unique=True)

    upserted = 0
    for ram in RAMS:
        result = collection.update_one(
            {"sku": ram["sku"]},
            {"$set": ram},
            upsert=True,
        )
        upserted += int(result.upserted_id is not None or result.modified_count > 0)

    return upserted


def main() -> None:
    try:
        count = seed_rams()
        print(f"Seed concluido. {count} documento(s) inserido(s) ou atualizado(s).")
    finally:
        close_mongo_client()


if __name__ == "__main__":
    main()
