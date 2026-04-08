from app.services.telegram_topic_router import TelegramTopicRouter


def test_topic_router_maps_hardware_topics_from_forum_names() -> None:
    router = TelegramTopicRouter()

    assert router.resolve_entity_type("PROCESSADOR") == "cpu"
    assert router.resolve_entity_type("PLACA-DE-VIDEO") == "gpu"
    assert router.resolve_entity_type("PLACA-DE-VÍDEO") == "gpu"
    assert router.resolve_entity_type("SSD") == "ssd"
    assert router.resolve_entity_type("MEMÓRIA") == "ram"
    assert router.resolve_entity_type("PLACA-MÃE") == "motherboard"
    assert router.resolve_entity_type("FONTE-DE-ALIMENTAÇÃO") == "psu"


def test_topic_router_ignores_non_hardware_topics() -> None:
    router = TelegramTopicRouter()

    assert router.resolve_entity_type("CHAT-GERAL") is None
    assert router.resolve_entity_type("CUPOM-DE-DESCONTO") is None
    assert router.resolve_entity_type("REGRAS") is None
    assert router.resolve_entity_type(None) is None
