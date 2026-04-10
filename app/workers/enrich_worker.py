import json
import logging

import redis

from app.core.config import settings
from app.repositories.catalog_candidate_repository import CatalogCandidateRepository
from app.services.catalog_candidate_enricher import CatalogCandidateEnricher
from app.services.openrouter_product_normalizer import OpenRouterProductNormalizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    # Connect to Redis
    r = redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)
    pubsub = r.pubsub()
    pubsub.subscribe("candidate_events")

    # Initialize services
    candidate_repo = CatalogCandidateRepository()
    normalizer = OpenRouterProductNormalizer()
    enricher = CatalogCandidateEnricher()

    logger.info("Enrich worker listening for events...")

    for message in pubsub.listen():
        if message["type"] == "message":
            try:
                event = json.loads(message["data"])
                logger.info(f"Received event: {event}")

                if event["type"] == "candidates_created":
                    # Find pending candidates for entity_type
                    candidates = candidate_repo.find_pending_by_entity(event["entity_type"])
                    for candidate in candidates:
                        normalized = normalizer.normalize(candidate)
                        if normalized:
                            # Update candidate with normalized data
                            enricher.enrich_candidate(candidate, normalized)
                            logger.info(f"Enriched candidate {candidate.id}")
                        else:
                            logger.warning(f"Failed to normalize candidate {candidate.id}")
            except Exception as e:
                logger.error(f"Error processing event: {e}")

if __name__ == "__main__":
    main()