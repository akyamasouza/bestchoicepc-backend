from typing import Any

from app.scripts.recalculate_rankings import recalculate_cpu_collection, recalculate_gpu_collection


class FakeCollection:
    def __init__(self, documents: list[dict[str, Any]]):
        self.documents = documents
        self.updated: list[tuple[dict[str, Any], dict[str, Any]]] = []
        self.unset_queries: list[tuple[dict[str, Any], dict[str, Any]]] = []

    def find(self, *_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
        return self.documents

    def find_one(self, *_args: Any, **_kwargs: Any) -> dict[str, Any] | None:
        return self.documents[0] if self.documents else None

    def update_one(self, query: dict[str, Any], update: dict[str, Any]) -> None:
        self.updated.append((query, update))

    def update_many(self, query: dict[str, Any], update: dict[str, Any]) -> None:
        self.unset_queries.append((query, update))


def test_recalculate_cpu_collection_uses_relative_performance_and_benchmark_estimates() -> None:
    collection = FakeCollection(
        [
            {
                "_id": 1,
                "name": "Intel Core i5-13400F",
                "benchmark": {
                    "techpowerup_relative_performance_applications": 67.6,
                    "single_thread_rating": 3714,
                },
            },
            {
                "_id": 2,
                "name": "Intel Core i5-12400F",
                "benchmark": {
                    "single_thread_rating": 3489,
                },
            },
        ]
    )

    updated, missing = recalculate_cpu_collection(collection=collection)

    assert updated == 2
    assert missing == 0

    rankings = {query["_id"]: update["$set"]["ranking"] for query, update in collection.updated}
    assert rankings[1]["game_score"] == 3714.0
    assert rankings[1]["game_percentile"] == 67.6
    assert rankings[1]["performance_tier"] == "C"
    assert rankings[2]["game_score"] == 3489.0
    assert rankings[2]["game_percentile"] == 63.5
    assert rankings[2]["performance_tier"] == "D"


def test_recalculate_cpu_collection_unsets_missing_rankings() -> None:
    collection = FakeCollection(
        [
            {"_id": "cpu-1", "benchmark": {}},
        ]
    )

    updated, missing = recalculate_cpu_collection(collection=collection)

    assert updated == 0
    assert missing == 1
    assert collection.unset_queries == [
        (
            {"_id": {"$in": ["cpu-1"]}},
            {"$unset": {"ranking": ""}},
        )
    ]


def test_recalculate_gpu_collection_uses_tomshardware_score_and_benchmark_estimates() -> None:
    collection = FakeCollection(
        [
            {
                "_id": 1,
                "name": "GeForce RTX 5090",
                "benchmark": {
                    "tomshardware_relative_performance_1080p_medium": 100.0,
                    "g3d_mark": 38975,
                },
            },
            {
                "_id": 2,
                "name": "GeForce RTX 4090",
                "benchmark": {
                    "g3d_mark": 38071,
                },
            },
        ]
    )

    updated, missing = recalculate_gpu_collection(collection=collection)

    assert updated == 2
    assert missing == 0

    rankings = {query["_id"]: update["$set"]["ranking"] for query, update in collection.updated}
    assert rankings[1]["game_score"] == 38975.0
    assert rankings[1]["game_percentile"] == 100.0
    assert rankings[1]["performance_tier"] == "S"
    assert rankings[2]["game_score"] == 38071.0
    assert rankings[2]["game_percentile"] == 97.68
    assert rankings[2]["performance_tier"] == "S"


def test_recalculate_gpu_collection_unsets_missing_rankings() -> None:
    collection = FakeCollection(
        [
            {"_id": "gpu-1", "benchmark": {}},
        ]
    )

    updated, missing = recalculate_gpu_collection(collection=collection)

    assert updated == 0
    assert missing == 1
    assert collection.unset_queries == [
        (
            {"_id": {"$in": ["gpu-1"]}},
            {"$unset": {"ranking": ""}},
        )
    ]
