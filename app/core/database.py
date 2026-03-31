from functools import lru_cache

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from app.core.config import settings


@lru_cache
def get_mongo_client() -> MongoClient:
    return MongoClient(settings.mongo_uri)


def close_mongo_client() -> None:
    if get_mongo_client.cache_info().currsize == 0:
        return

    client = get_mongo_client()
    client.close()
    get_mongo_client.cache_clear()


def get_database() -> Database:
    return get_mongo_client()[settings.mongo_database]


def get_cpu_collection() -> Collection:
    return get_database()["cpus"]


def get_gpu_collection() -> Collection:
    return get_database()["gpus"]


def get_ssd_collection() -> Collection:
    return get_database()["ssds"]


def get_ram_collection() -> Collection:
    return get_database()["rams"]


def get_motherboard_collection() -> Collection:
    return get_database()["motherboards"]


def get_psu_collection() -> Collection:
    return get_database()["psus"]


def get_daily_offer_collection() -> Collection:
    return get_database()["daily_offers"]


def get_review_consensus_cache_collection() -> Collection:
    return get_database()["review_consensus_cache"]
