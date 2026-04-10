import asyncio
import json
import logging
from datetime import datetime

import redis

from app.core.config import settings
from app.services.daily_offer_pipeline import DailyOfferPipeline, TelegramSearchStrategy
from app.services.telegram_search import TelegramChannelSearchService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    # Connect to Redis
    r = redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)

    # Initialize services
    telegram_service = TelegramChannelSearchService()
    search_strategy = TelegramSearchStrategy(telegram_service)
    pipeline = DailyOfferPipeline(search_strategy=search_strategy)

    # Run for each entity type (could be configurable)
    entity_types = ["cpu", "gpu", "ssd", "ram", "psu", "motherboard"]
    for entity_type in entity_types:
        try:
            result = await pipeline.run(entity_type=entity_type, limit=10)  # Adjust limit
            logger.info(f"Sync for {entity_type}: {result}")

            # Publish event if candidates created
            if result.candidates_created > 0:
                event = {
                    "type": "candidates_created",
                    "entity_type": entity_type,
                    "count": result.candidates_created,
                    "timestamp": datetime.utcnow().isoformat(),
                }
                r.publish("candidate_events", json.dumps(event))
                logger.info(f"Published event: {event}")
        except Exception as e:
            logger.error(f"Error syncing {entity_type}: {e}")

    await telegram_service.close()

if __name__ == "__main__":
    asyncio.run(main())