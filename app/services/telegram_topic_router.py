from __future__ import annotations

import re
import unicodedata

from app.schemas.common import EntityType


DEFAULT_TELEGRAM_TOPIC_ENTITY_TYPES: dict[str, EntityType] = {
    "processador": "cpu",
    "processadores": "cpu",
    "placa de video": "gpu",
    "placas de video": "gpu",
    "ssd": "ssd",
    "memoria": "ram",
    "memorias": "ram",
    "placa mae": "motherboard",
    "placas mae": "motherboard",
    "fonte de alimentacao": "psu",
    "fontes de alimentacao": "psu",
}


class TelegramTopicRouter:
    def __init__(
        self,
        topic_entity_types: dict[str, EntityType] | None = None,
    ) -> None:
        self.topic_entity_types = {
            self.normalize_topic_name(topic_name): entity_type
            for topic_name, entity_type in (topic_entity_types or DEFAULT_TELEGRAM_TOPIC_ENTITY_TYPES).items()
        }

    def resolve_entity_type(self, topic_name: str | None) -> EntityType | None:
        if topic_name is None:
            return None

        return self.topic_entity_types.get(self.normalize_topic_name(topic_name))

    @staticmethod
    def normalize_topic_name(topic_name: str) -> str:
        without_accents = unicodedata.normalize("NFKD", topic_name)
        ascii_text = without_accents.encode("ascii", "ignore").decode("ascii")
        normalized = re.sub(r"[^a-zA-Z0-9]+", " ", ascii_text).lower()
        return " ".join(normalized.split())
