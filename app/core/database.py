from functools import lru_cache

from bson import ObjectId
from pymongo import MongoClient
from pymongo.database import Database

from app.core.config import settings
from app.repositories.protocols import CollectionProtocol


@lru_cache(maxsize=1)
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


def get_collection(name: str) -> CollectionProtocol:
    return get_database()[name]


def get_cpu_collection() -> CollectionProtocol:
    return get_collection("cpus")


def get_gpu_collection() -> CollectionProtocol:
    return get_collection("gpus")


def get_ssd_collection() -> CollectionProtocol:
    return get_collection("ssds")


def get_ram_collection() -> CollectionProtocol:
    return get_collection("rams")


def get_motherboard_collection() -> CollectionProtocol:
    return get_collection("motherboards")


def get_psu_collection() -> CollectionProtocol:
    return get_collection("psus")


def get_daily_offer_collection() -> CollectionProtocol:
    return get_collection("daily_offers")


def coerce_document_id(value: str) -> object:
    try:
        return ObjectId(value)
    except Exception:
        return value
