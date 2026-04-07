import asyncio
import logging
import sys
from typing import Any

from telethon import TelegramClient, events

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
from app.services.entity_matcher import EntityMatcher
from app.services.telegram_offer_parser import TelegramOfferParser

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("telegram_listener")

class ReverseMatcher:
    def __init__(self):
        self.matcher = EntityMatcher()
        self.catalog = self._load_catalog()
    
    def _load_catalog(self) -> list[dict[str, Any]]:
        logger.info("Carregando catalogo de hardwares em memoria...")
        catalog = []
        collections = {
            "cpu": get_cpu_collection(),
            "gpu": get_gpu_collection(),
            "motherboard": get_motherboard_collection(),
            "psu": get_psu_collection(),
            "ram": get_ram_collection(),
            "ssd": get_ssd_collection(),
        }
        for entity_type, col in collections.items():
            for item in col.find({}, {"sku": 1, "name": 1}):
                if "sku" in item and "name" in item:
                    catalog.append({
                        "entity_type": entity_type,
                        "entity_id": str(item["_id"]),
                        "sku": str(item["sku"]),
                        "name": str(item["name"]),
                    })
        logger.info(f"Catalogo carregado: {len(catalog)} itens na memoria.")
        # Ordenamos pelo tamanho do sku (descendente) para tentar matches com SKUs maiores primeiro (mais específicos)
        catalog.sort(key=lambda x: len(x["sku"]), reverse=True)
        return catalog

    def find_match(self, raw_text: str) -> dict[str, Any] | None:
        """Busca O(N) no catalogo comparando match estrito com os tokens."""
        for item in self.catalog:
            reason = self.matcher.mismatch_reason(
                entity_name=item["name"],
                entity_id=item["sku"],
                raw_text=raw_text,
            )
            # Se a reason for None, significa match perfeitamente aceitavel
            if reason is None:
                return item
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
    offer_parser = TelegramOfferParser()
    repository = DailyOfferRepository(get_daily_offer_collection())
    repository.ensure_indexes()

    client = TelegramClient(settings.telegram_session_path, settings.telegram_api_id, settings.telegram_api_hash)
    
    # Event Listener passivo (push-based) para interceptar novas ofertas em tempo real
    @client.on(events.NewMessage(chats=[channel_to_listen]))
    async def handler(event):
        try:
            raw_text = getattr(event.message, "message", "")
            if not raw_text:
                return

            logger.info("Nova mensagem recebida. Analisando...")

            # 1. Reverse matching pra descobrir qual componente e
            match = reverse_matcher.find_match(raw_text)
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
