from __future__ import annotations

import argparse

from pymongo.collection import Collection

from app.core.database import get_cpu_collection, get_gpu_collection
from app.services.benchmark_ranking import BenchmarkRankingService
from app.services.cpu_ranking import CpuRankingEntry, CpuRankingService


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
        recalculate_cpu_collection(collection=get_cpu_collection())

    if entity_type in {"gpu", "all"}:
        recalculate_collection(
            collection=get_gpu_collection(),
            score_field="g3d_mark",
            label="gpu",
        )


def recalculate_cpu_collection(*, collection: Collection) -> tuple[int, int]:
    entries: list[CpuRankingEntry] = []
    missing_ids: list[object] = []

    for document in collection.find({}, {"name": 1, "benchmark": 1}):
        benchmark = document.get("benchmark") or {}
        document_id = str(document["_id"])
        name = str(document.get("name") or document_id)
        benchmark_score = _resolve_score(benchmark, "single_thread_rating")
        techpowerup_score = _resolve_score(benchmark, "techpowerup_relative_performance_applications")

        if benchmark_score is None and techpowerup_score is None:
            missing_ids.append(document["_id"])
            continue

        entries.append(
            CpuRankingEntry(
                identifier=document_id,
                name=name,
                benchmark_score=float(benchmark_score) if benchmark_score is not None else None,
                techpowerup_score=float(techpowerup_score) if techpowerup_score is not None else None,
            )
        )

    rankings = CpuRankingService().build_rankings(entries)

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

    print(
        "cpu: "
        f"{updated} documento(s) atualizado(s), "
        f"{len(missing_ids)} sem score, "
        f"{sum(entry.techpowerup_score is not None for entry in entries)} com TechPowerUp, "
        f"{sum(entry.techpowerup_score is None for entry in entries)} estimados por benchmark."
    )
    return updated, len(missing_ids)


def _resolve_score(benchmark: dict[str, object], score_field: str) -> int | float | None:
    value = benchmark.get(score_field)
    if value is None:
        return None

    if isinstance(value, float):
        return value

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
