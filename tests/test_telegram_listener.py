from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.scripts.telegram_listener import ReverseMatcher, TelegramForumTopicResolver
from app.services.entity_matcher import EntityMatcher


class FakeTelegramClient:
    def __init__(self, topic_title: str) -> None:
        self.topic_title = topic_title
        self.calls = 0

    async def __call__(self, request: object) -> SimpleNamespace:
        self.calls += 1
        topic_id = request.topics[0]
        return SimpleNamespace(
            topics=[
                SimpleNamespace(
                    id=topic_id,
                    top_message=topic_id,
                    title=self.topic_title,
                )
            ]
        )


def test_extract_topic_id_uses_forum_reply_top_id() -> None:
    message = SimpleNamespace(reply_to=SimpleNamespace(reply_to_top_id=299, forum_topic=True))

    assert TelegramForumTopicResolver.extract_topic_id(message) == 299


def test_topic_resolver_caches_topic_title() -> None:
    client = FakeTelegramClient("PLACA-DE-VÍDEO")
    resolver = TelegramForumTopicResolver(client, "@pcbuildwizard")
    message = SimpleNamespace(reply_to=SimpleNamespace(reply_to_top_id=2242, forum_topic=True))

    first_result = asyncio.run(resolver.resolve_topic_title(message))
    second_result = asyncio.run(resolver.resolve_topic_title(message))

    assert first_result == "PLACA-DE-VÍDEO"
    assert second_result == "PLACA-DE-VÍDEO"
    assert client.calls == 1


def test_reverse_matcher_limits_candidates_by_topic_entity_type() -> None:
    matcher = ReverseMatcher.__new__(ReverseMatcher)
    matcher.matcher = EntityMatcher()
    matcher.catalog_by_entity_type = {
        "cpu": [
            {
                "entity_type": "cpu",
                "entity_id": "ryzen-7-9800x3d",
                "sku": "ryzen-7-9800x3d",
                "name": "AMD Ryzen 7 9800X3D",
            }
        ],
        "gpu": [],
        "ssd": [],
        "ram": [],
        "psu": [],
        "motherboard": [],
    }

    raw_text = "Processador AMD Ryzen 7 9800X3D R$ 2.799,99 Loja: Amazon"

    assert matcher.find_match(raw_text, entity_type="gpu") is None
    assert matcher.find_match(raw_text, entity_type="cpu") == matcher.catalog_by_entity_type["cpu"][0]
