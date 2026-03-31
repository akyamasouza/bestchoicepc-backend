from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pymongo.collection import Collection

from app.services.youtube_review_consensus import MatchReviewConsensus


class ReviewConsensusCacheRepository:
    def __init__(self, collection: Collection):
        self.collection = collection

    def find_by_pair(self, *, cpu_sku: str, gpu_sku: str) -> dict[str, Any] | None:
        return self.collection.find_one({"pair_key": self._build_pair_key(cpu_sku=cpu_sku, gpu_sku=gpu_sku)})

    def mark_pending(
        self,
        *,
        cpu_sku: str,
        gpu_sku: str,
        reason: str = "processing_started",
    ) -> None:
        now = self._utcnow()
        self.collection.update_one(
            {"pair_key": self._build_pair_key(cpu_sku=cpu_sku, gpu_sku=gpu_sku)},
            {
                "$set": {
                    "pair_key": self._build_pair_key(cpu_sku=cpu_sku, gpu_sku=gpu_sku),
                    "cpu_sku": cpu_sku,
                    "gpu_sku": gpu_sku,
                    "status": "pending",
                    "reason": reason,
                    "review_consensus": None,
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "created_at": now,
                },
            },
            upsert=True,
        )

    def save_ready(
        self,
        *,
        cpu_sku: str,
        gpu_sku: str,
        review_consensus: MatchReviewConsensus,
    ) -> None:
        now = self._utcnow()
        self.collection.update_one(
            {"pair_key": self._build_pair_key(cpu_sku=cpu_sku, gpu_sku=gpu_sku)},
            {
                "$set": {
                    "pair_key": self._build_pair_key(cpu_sku=cpu_sku, gpu_sku=gpu_sku),
                    "cpu_sku": cpu_sku,
                    "gpu_sku": gpu_sku,
                    "status": "ready",
                    "reason": None,
                    "review_consensus": {
                        "insight": review_consensus.insight,
                        "warnings": list(review_consensus.warnings),
                        "confidence": review_consensus.confidence,
                        "references": [
                            {
                                "title": reference.title,
                                "url": reference.url,
                                "channel": reference.channel,
                            }
                            for reference in review_consensus.references
                        ],
                        "source_count": review_consensus.source_count,
                        "average_explicit_fps": review_consensus.average_explicit_fps,
                        "tested_games": [
                            {
                                "name": game.name,
                                "resolution": game.resolution,
                                "avg_fps": game.avg_fps,
                            }
                            for game in review_consensus.tested_games
                        ],
                    },
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "created_at": now,
                },
            },
            upsert=True,
        )

    def save_no_consensus(
        self,
        *,
        cpu_sku: str,
        gpu_sku: str,
        reason: str,
    ) -> None:
        self._save_terminal_status(
            cpu_sku=cpu_sku,
            gpu_sku=gpu_sku,
            status="no_consensus",
            reason=reason,
        )

    def save_error(
        self,
        *,
        cpu_sku: str,
        gpu_sku: str,
        reason: str,
    ) -> None:
        self._save_terminal_status(
            cpu_sku=cpu_sku,
            gpu_sku=gpu_sku,
            status="error",
            reason=reason,
        )

    def _save_terminal_status(
        self,
        *,
        cpu_sku: str,
        gpu_sku: str,
        status: str,
        reason: str,
    ) -> None:
        now = self._utcnow()
        self.collection.update_one(
            {"pair_key": self._build_pair_key(cpu_sku=cpu_sku, gpu_sku=gpu_sku)},
            {
                "$set": {
                    "pair_key": self._build_pair_key(cpu_sku=cpu_sku, gpu_sku=gpu_sku),
                    "cpu_sku": cpu_sku,
                    "gpu_sku": gpu_sku,
                    "status": status,
                    "reason": reason,
                    "review_consensus": None,
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "created_at": now,
                },
            },
            upsert=True,
        )

    @staticmethod
    def _build_pair_key(*, cpu_sku: str, gpu_sku: str) -> str:
        return f"{cpu_sku}__{gpu_sku}"

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(UTC)
