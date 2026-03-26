from __future__ import annotations

import argparse

from pymongo.collection import Collection

from app.core.database import get_cpu_collection, get_gpu_collection
from app.services.benchmark_ranking import BenchmarkRankingService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Recalcula ranking de benchmark para CPUs e GPUs.")
    parser.add_argument(
        "--entity-type",
        choices=("cpu", "gpu", "all"),
        default="all",
        help="Tipo de entidade a recalcular.",
    )
    return parser


def recalculate_collection(
    *,
    collection: Collection,
    score_field: str,
    label: str,
) -> tuple[int, int]:
    entries: list[tuple[str, float]] = []
    missing_ids: list[object] = []

    for document in collection.find({}, {"benchmark": 1}):
        benchmark = document.get("benchmark") or {}
        score = _resolve_score(benchmark, score_field)
        if score is None:
            missing_ids.append(document["_id"])
            continue

        entries.append((str(document["_id"]), float(score)))

    rankings = BenchmarkRankingService().build_rankings(entries)
    updated = 0

    for document_id, ranking in rankings.items():
        collection.update_one(
            {"_id": _coerce_id(collection, document_id)},
            {
                "$set": {
                    "ranking": {
                        "game_score": ranking.game_score,
                        "game_percentile": ranking.game_percentile,
                        "performance_tier": ranking.performance_tier,
                    }
                }
            },
        )
        updated += 1

    if missing_ids:
        collection.update_many({"_id": {"$in": missing_ids}}, {"$unset": {"ranking": ""}})

    print(f"{label}: {updated} documento(s) atualizado(s), {len(missing_ids)} sem score.")
    return updated, len(missing_ids)


def run(entity_type: str = "all") -> None:
    if entity_type in {"cpu", "all"}:
        recalculate_collection(
            collection=get_cpu_collection(),
            score_field="single_thread_rating",
            label="cpu",
        )

    if entity_type in {"gpu", "all"}:
        recalculate_collection(
            collection=get_gpu_collection(),
            score_field="g3d_mark",
            label="gpu",
        )


def _resolve_score(benchmark: dict[str, object], score_field: str) -> int | float | None:
    value = benchmark.get(score_field)
    if value is None:
        return None

    return int(value)


def _coerce_id(collection: Collection, value: str) -> object:
    sample = collection.find_one({}, {"_id": 1})
    if sample is None:
        return value

    sample_id = sample["_id"]
    try:
        return type(sample_id)(value)
    except Exception:
        return value


def main() -> None:
    args = build_parser().parse_args()
    run(entity_type=args.entity_type)


if __name__ == "__main__":
    main()
