from app.services.openrouter_product_normalizer import OpenRouterProductNormalizer
from app.schemas.catalog_candidate import CatalogCandidate

from datetime import datetime

now = datetime.utcnow().isoformat() + "Z"
candidate = CatalogCandidate(
    entity_type="cpu",
    fingerprint="test-fingerprint",
    raw_title="AMD Ryzen 7 9800X3D",
    raw_text="Novo processador AMD",
    proposed_name="AMD Ryzen 7 9800X3D",
    first_seen=now,
    last_seen=now,
    # Outros campos opcionais
)

normalizer = OpenRouterProductNormalizer()
result = normalizer.normalize(candidate)
print(result)