from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, field

from app.scripts import enrich_catalog_candidates, sync_daily_offers
from app.services.hardware_registry import HARDWARE_ENTITY_REGISTRY
from app.schemas.common import EntityType


@dataclass(slots=True)
class ProcessedEntityType:
    entity_type: EntityType


@dataclass(slots=True)
class RunCatalogCandidatePipelineResult:
    processed_entity_types: list[ProcessedEntityType] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


async def _run_sync(*, entity_type: EntityType, channel: str | None, limit: int) -> int:
    return await sync_daily_offers.run(entity_type=entity_type, channel=channel, limit=limit)


def run(*, entity_type: str = "all", channel: str | None = None, limit: int = 1) -> RunCatalogCandidatePipelineResult:
    if entity_type == "all":
        entity_types = list(HARDWARE_ENTITY_REGISTRY.keys())
    else:
        entity_types = [entity_type]

    result = RunCatalogCandidatePipelineResult()

    for current_entity_type in entity_types:
        try:
            sync_exit_code = asyncio.run(_run_sync(entity_type=current_entity_type, channel=channel, limit=limit))
        except Exception as exc:
            result.errors.append(f"{current_entity_type}: sync falhou com excecao ({exc})")
            continue

        if sync_exit_code != 0:
            result.errors.append(f"{current_entity_type}: sync concluiu com erros")
            continue

        enrichment_result = enrich_catalog_candidates.run(entity_type=current_entity_type)
        if enrichment_result.errors:
            result.errors.append(f"{current_entity_type}: enrichment concluiu com erros")
            continue

        result.processed_entity_types.append(ProcessedEntityType(entity_type=current_entity_type))

    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Executa sync e enriquecimento de candidatos por tipo de entidade.")
    parser.add_argument(
        "--entity-type",
        choices=[*HARDWARE_ENTITY_REGISTRY.keys(), "all"],
        default="all",
        help="Tipo de entidade a processar. Use 'all' para percorrer todas.",
    )
    parser.add_argument("--channel", help="Canal do Telegram. Se omitido, usa TELEGRAM_DEFAULT_CHANNEL.")
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="Quantidade maxima de mensagens por consulta. O padrao e 1.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run(entity_type=args.entity_type, channel=args.channel, limit=args.limit)
    print(
        "Pipeline concluido. "
        f"entidades_processadas={len(result.processed_entity_types)}, "
        f"erros={len(result.errors)}"
    )
    for error in result.errors:
        print(f"- {error}")
    raise SystemExit(0 if not result.errors else 1)


if __name__ == "__main__":
    main()
