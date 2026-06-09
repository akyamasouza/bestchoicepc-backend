from __future__ import annotations

from dataclasses import dataclass

from app.schemas.common import EntityType


@dataclass(frozen=True, slots=True)
class HardwareEntityConfig:
    entity_type: EntityType
    collection_name: str
    required_fields: tuple[str, ...]
    supports_ranking: bool


HARDWARE_ENTITY_REGISTRY: dict[EntityType, HardwareEntityConfig] = {
    "cpu": HardwareEntityConfig(
        entity_type="cpu",
        collection_name="cpus",
        required_fields=("name", "sku"),
        supports_ranking=True,
    ),
    "gpu": HardwareEntityConfig(
        entity_type="gpu",
        collection_name="gpus",
        required_fields=("name", "sku"),
        supports_ranking=True,
    ),
    "ssd": HardwareEntityConfig(
        entity_type="ssd",
        collection_name="ssds",
        required_fields=("name", "sku", "brand"),
        supports_ranking=True,
    ),
    "ram": HardwareEntityConfig(
        entity_type="ram",
        collection_name="rams",
        required_fields=("name", "sku", "brand", "compatibility"),
        supports_ranking=False,
    ),
    "psu": HardwareEntityConfig(
        entity_type="psu",
        collection_name="psus",
        required_fields=("name", "sku", "brand"),
        supports_ranking=True,
    ),
    "motherboard": HardwareEntityConfig(
        entity_type="motherboard",
        collection_name="motherboards",
        required_fields=("name", "sku", "brand", "compatibility"),
        supports_ranking=False,
    ),
}


def get_hardware_entity_config(entity_type: EntityType) -> HardwareEntityConfig:
    try:
        return HARDWARE_ENTITY_REGISTRY[entity_type]
    except KeyError as exc:
        raise RuntimeError(f"Tipo de entidade nao suportado: {entity_type}") from exc