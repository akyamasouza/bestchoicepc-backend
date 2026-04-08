from __future__ import annotations

import argparse

from app.core.database import close_mongo_client, get_daily_offer_collection
from app.services.entity_matcher import EntityMatcher


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audita daily_offers canonicas revalidando raw_text contra entity_sku/entity_name."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Marca ofertas invalidas como rejected sem deletar os documentos.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    matcher = EntityMatcher()
    collection = get_daily_offer_collection()
    invalid: list[tuple[object, str]] = []

    try:
        for offer in collection.find({
            "entity_id": {"$type": "string"},
            "entity_sku": {"$type": "string"},
            "entity_name": {"$type": "string"},
            "raw_text": {"$type": "string"},
        }):
            reason = matcher.mismatch_reason(
                entity_name=str(offer["entity_name"]),
                entity_id=str(offer["entity_sku"]),
                raw_text=str(offer["raw_text"]),
            )
            if reason is None:
                continue

            invalid.append((offer["_id"], reason))
            if args.apply:
                collection.update_one(
                    {"_id": offer["_id"]},
                    {
                        "$set": {
                            "status": "rejected",
                            "rejection_reason": reason,
                        },
                        "$unset": {
                            "entity_id": "",
                        },
                    },
                )
    finally:
        close_mongo_client()

    mode = "apply" if args.apply else "dry-run"
    print(f"Auditoria daily_offers ({mode}) concluida. invalidas={len(invalid)}")
    for offer_id, reason in invalid:
        print(f"- {offer_id}: {reason}")


if __name__ == "__main__":
    main()
