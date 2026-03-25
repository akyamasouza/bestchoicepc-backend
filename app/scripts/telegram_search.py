from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from app.services.telegram_search import TelegramChannelSearchService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Busca mensagens em um canal do Telegram usando a client API.")
    parser.add_argument("query", help="Texto a ser pesquisado no canal.")
    parser.add_argument("--channel", help="Canal ou @handle. Se omitido, usa TELEGRAM_DEFAULT_CHANNEL.")
    parser.add_argument("--limit", type=int, default=1, help="Quantidade maxima de mensagens.")
    parser.add_argument("--json", action="store_true", help="Imprime o resultado em JSON.")

    return parser


async def run(query: str, channel: str | None, limit: int, as_json: bool) -> int:
    service = TelegramChannelSearchService()

    try:
        results = await service.search_channel(query=query, channel=channel, limit=limit)
    finally:
        await service.close()

    if not results:
        print("No messages found for this query.")
        return 0

    if as_json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0

    for result in results:
        _print_message(result)

    return 0


def _print_message(result: dict[str, Any]) -> None:
    print()
    print(f"Message #{result['id']}")
    print(f"Date: {result.get('date_iso') or 'n/a'}")
    print(f"Views: {result.get('views') or 'n/a'}")
    print(f"Forwards: {result.get('forwards') or 'n/a'}")
    print(f"URL: {result.get('url') or 'n/a'}")
    print("Text:")
    print(result.get("excerpt") or "(empty)")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        return asyncio.run(
            run(
                query=args.query,
                channel=args.channel,
                limit=max(1, args.limit),
                as_json=args.json,
            )
        )
    except RuntimeError as exc:
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
