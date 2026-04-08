import asyncio
import logging
import sys
from typing import Any

from telethon import TelegramClient, events, functions

from app.core.config import settings
from app.core.database import (
    get_cpu_collection,
    get_daily_offer_collection,
    get_gpu_collection,
    get_motherboard_collection,
    get_psu_collection,
    get_ram_collection,
    get_ssd_collection,
)
from app.repositories.daily_offer_repository import DailyOfferRepository
from app.schemas.common import EntityType
from app.services.entity_matcher import EntityMatcher
from app.services.telegram_offer_parser import TelegramOfferParser
from app.services.telegram_topic_router import TelegramTopicRouter

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("telegram_listener")

class ReverseMatcher:
    def __init__(self):
        self.matcher = EntityMatcher()
        self.catalog_by_entity_type = self._load_catalog()
    
    def _load_catalog(self) -> dict[str, list[dict[str, Any]]]:
        logger.info("Carregando catalogo de hardwares em memoria...")
        catalog_by_entity_type: dict[str, list[dict[str, Any]]] = {}
        collections = {
            "cpu": get_cpu_collection(),
            "gpu": get_gpu_collection(),
            "motherboard": get_motherboard_collection(),
            "psu": get_psu_collection(),
            "ram": get_ram_collection(),
            "ssd": get_ssd_collection(),
        }
        for entity_type, col in collections.items():
            catalog_by_entity_type[entity_type] = []
            for item in col.find({}, {"sku": 1, "name": 1}):
                if "sku" in item and "name" in item:
                    catalog_by_entity_type[entity_type].append({
                        "entity_type": entity_type,
                        "entity_id": str(item["_id"]),
                        "sku": str(item["sku"]),
                        "name": str(item["name"]),
                    })

            # Ordenamos pelo tamanho do sku (descendente) para tentar matches mais especificos primeiro.
            catalog_by_entity_type[entity_type].sort(key=lambda x: len(x["sku"]), reverse=True)

        total_items = sum(len(items) for items in catalog_by_entity_type.values())
        logger.info("Catalogo carregado: %s itens na memoria.", total_items)
        return catalog_by_entity_type

    def find_match(self, raw_text: str, entity_type: EntityType | None = None) -> dict[str, Any] | None:
        """Busca no catalogo comparando match estrito com os tokens."""
        candidates = self._candidates(entity_type)
        for item in candidates:
            reason = self.matcher.mismatch_reason(
                entity_name=item["name"],
                entity_id=item["sku"],
                raw_text=raw_text,
            )
            if reason is None:
                return item
        return None

    def _candidates(self, entity_type: EntityType | None) -> list[dict[str, Any]]:
        if entity_type is not None:
            return self.catalog_by_entity_type.get(entity_type, [])

        return [
            item
            for catalog in self.catalog_by_entity_type.values()
            for item in catalog
        ]


class TelegramForumTopicResolver:
    def __init__(self, client: TelegramClient, channel: str) -> None:
        self.client = client
        self.channel = channel
        self._topic_titles_by_id: dict[int, str | None] = {}

    async def resolve_topic_title(self, message: Any) -> str | None:
        topic_id = self.extract_topic_id(message)
        if topic_id is None:
            return None

        if topic_id in self._topic_titles_by_id:
            return self._topic_titles_by_id[topic_id]

        try:
            result = await self.client(
                functions.messages.GetForumTopicsByIDRequest(
                    peer=self.channel,
                    topics=[topic_id],
                )
            )
        except Exception as exc:
            logger.warning("Nao foi possivel resolver topico do Telegram. topic_id=%s erro=%s", topic_id, exc)
            self._topic_titles_by_id[topic_id] = None
            return None

        for topic in getattr(result, "topics", []):
            if getattr(topic, "id", None) == topic_id or getattr(topic, "top_message", None) == topic_id:
                title = getattr(topic, "title", None)
                self._topic_titles_by_id[topic_id] = title
                return title

        self._topic_titles_by_id[topic_id] = None
        return None

    @staticmethod
    def extract_topic_id(message: Any) -> int | None:
        reply_to = getattr(message, "reply_to", None)
        if reply_to is None:
            return None

        topic_id = getattr(reply_to, "reply_to_top_id", None)
        if topic_id is not None:
            return int(topic_id)

        if getattr(reply_to, "forum_topic", False):
            reply_to_msg_id = getattr(reply_to, "reply_to_msg_id", None)
            return int(reply_to_msg_id) if reply_to_msg_id is not None else None

        return None

async def main():
    if not settings.telegram_api_id or not settings.telegram_api_hash:
        logger.error("Variaveis TELEGRAM_API_ID e TELEGRAM_API_HASH precisam estar configuradas.")
        sys.exit(1)

    channel_to_listen = settings.telegram_default_channel
    if not channel_to_listen:
        logger.error("Variavel TELEGRAM_DEFAULT_CHANNEL precisa estar configurada.")
        sys.exit(1)

    logger.info(f"Inicializando listener Telegram-Push para o canal: {channel_to_listen}")

    reverse_matcher = ReverseMatcher()
    topic_router = TelegramTopicRouter()
    offer_parser = TelegramOfferParser()
    repository = DailyOfferRepository(get_daily_offer_collection())
    repository.ensure_indexes()

    client = TelegramClient(settings.telegram_session_path, settings.telegram_api_id, settings.telegram_api_hash)
    topic_resolver = TelegramForumTopicResolver(client, channel_to_listen)
    
    # Event Listener passivo (push-based) para interceptar novas ofertas em tempo real
    @client.on(events.NewMessage(chats=[channel_to_listen]))
    async def handler(event):
        try:
            raw_text = getattr(event.message, "message", "")
            if not raw_text:
                return

            topic_title = await topic_resolver.resolve_topic_title(event.message)
            entity_type = topic_router.resolve_entity_type(topic_title)

            if topic_title is not None and entity_type is None:
                logger.info("Mensagem ignorada: topico sem mapeamento de hardware. topico=%s", topic_title)
                return

            logger.info(
                "Nova mensagem recebida. Analisando. topico=%s entity_type=%s",
                topic_title or "sem_topico",
                entity_type or "auto",
            )

            # 1. Reverse matching descobre qual componente e; em forum reconhecido, limita a categoria do topico.
            match = reverse_matcher.find_match(raw_text, entity_type=entity_type)
            if not match:
                logger.info("Mensagem descartada: nenhum hardware compativel encontrado na base.")
                return

            logger.info(f"Match encontrado: {match['sku']} ({match['entity_type']})")

            # 2. Emulando a estrutura que o parser atual ja consome
            message_id = getattr(event.message, "id", None)
            date_iso = event.message.date.isoformat() if hasattr(event.message, "date") and event.message.date else None
            
            handle = channel_to_listen.lstrip('@')
            url = f"https://t.me/{handle}/{message_id}" if message_id else None

            message_data = {
                "id": message_id,
                "text": raw_text,
                "date_iso": date_iso,
                "url": url
            }

            # 3. Parse e extrai os precos e metadata
            offer = offer_parser.parse(
                message_data,
                entity_type=match["entity_type"],
                entity_id=match["entity_id"],
                entity_sku=match["sku"],
                entity_name=match["name"],
            )

            # 4. Upsert salva no mongodb para a API principal servir aos usuarios
            repository.upsert(offer)
            logger.info(f"🟢 Oferta gravada no BD! {match['sku']} - Loja: {offer.store} - R${offer.price_card}")

        except ValueError as e:
            logger.warning(f"🟡 Falha no parser de ofertas (provavelmente sem precos rastreaveis): {e}")
        except Exception as e:
            logger.exception(f"🔴 Erro inesperado no handler do listener: {e}")

    await client.start()
    logger.info("🚀 Worker Listener rodando... Aguardando Novas Ofertas ao vivo...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
