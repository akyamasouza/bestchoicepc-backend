from app.core.database import close_mongo_client, get_gpu_collection
from app.data.gpus_tomshardware import resolve_tomshardware_gpu_1080p_medium_score
from app.data.gpus import GPUS
from app.repositories.protocols import ASCENDING


def seed_gpus() -> int:
    collection = get_gpu_collection()
    collection.create_index([("sku", ASCENDING)], unique=True)

    upserted = 0

    for gpu in GPUS:
        tomshardware_score = resolve_tomshardware_gpu_1080p_medium_score(
            gpu.get("name"),
            gpu.get("other_names"),
            gpu.get("sku"),
        )
        benchmark = dict(gpu.get("benchmark", {}))
        benchmark["tomshardware_relative_performance_1080p_medium"] = tomshardware_score
        seeded_gpu = {
            **gpu,
            "benchmark": benchmark,
        }

        result = collection.update_one(
            {"sku": gpu["sku"]},
            {"$set": seeded_gpu},
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
