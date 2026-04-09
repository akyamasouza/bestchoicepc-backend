from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.core.database import (
    get_cpu_collection,
    get_gpu_collection,
    get_motherboard_collection,
    get_psu_collection,
    get_ram_collection,
    get_ssd_collection,
)
from app.repositories.protocols import CollectionProtocol
from app.schemas.common import EntityType


@dataclass(frozen=True, slots=True)
class HardwareEntityConfig:
    entity_type: EntityType
    collection_name: str
    collection_getter: Callable[[], CollectionProtocol]
    required_fields: tuple[str, ...]
    supports_ranking: bool


HARDWARE_ENTITY_REGISTRY: dict[EntityType, HardwareEntityConfig] = {
    "cpu": HardwareEntityConfig(
        entity_type="cpu",
        collection_name="cpus",
        collection_getter=get_cpu_collection,
        required_fields=("name", "sku"),
        supports_ranking=True,
    ),
    "gpu": HardwareEntityConfig(
        entity_type="gpu",
        collection_name="gpus",
        collection_getter=get_gpu_collection,
        required_fields=("name", "sku"),
        supports_ranking=True,
    ),
    "ssd": HardwareEntityConfig(
        entity_type="ssd",
        collection_name="ssds",
        collection_getter=get_ssd_collection,
        required_fields=("name", "sku", "brand"),
        supports_ranking=True,
    ),
    "ram": HardwareEntityConfig(
        entity_type="ram",
        collection_name="rams",
        collection_getter=get_ram_collection,
        required_fields=("name", "sku", "brand", "compatibility"),
        supports_ranking=False,
    ),
    "psu": HardwareEntityConfig(
        entity_type="psu",
        collection_name="psus",
        collection_getter=get_psu_collection,
        required_fields=("name", "sku", "brand"),
        supports_ranking=True,
    ),
    "motherboard": HardwareEntityConfig(
        entity_type="motherboard",
        collection_name="motherboards",
        collection_getter=get_motherboard_collection,
        required_fields=("name", "sku", "brand", "compatibility"),
        supports_ranking=False,
    ),
}


def get_hardware_entity_config(entity_type: EntityType) -> HardwareEntityConfig:
    try:
        return HARDWARE_ENTITY_REGISTRY[entity_type]
    except KeyError as exc:
        raise RuntimeError(f"Tipo de entidade nao suportado: {entity_type}") from exc
