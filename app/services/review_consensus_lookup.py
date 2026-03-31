from __future__ import annotations

from dataclasses import dataclass

from fastapi import BackgroundTasks

from app.repositories.review_consensus_cache_repository import ReviewConsensusCacheRepository
from app.services.youtube_review_consensus import (
    MatchReviewConsensus,
    MatchReviewedGame,
    YoutubeVideoReference,
    YoutubeReviewConsensusService,
)


@dataclass(frozen=True, slots=True)
class ReviewConsensusLookup:
    status: str
    reason: str | None
    review_consensus: MatchReviewConsensus | None


class ReviewConsensusLookupService:
    def __init__(
        self,
        repository: ReviewConsensusCacheRepository,
        youtube_review_consensus_service: YoutubeReviewConsensusService,
    ):
        self.repository = repository
        self.youtube_review_consensus_service = youtube_review_consensus_service

    def get_or_start_lookup(
        self,
        *,
        cpu_sku: str,
        cpu_name: str,
        gpu_sku: str,
        gpu_name: str,
        background_tasks: BackgroundTasks,
        force_refresh: bool = False,
    ) -> ReviewConsensusLookup:
        current = None if force_refresh else self.repository.find_by_pair(cpu_sku=cpu_sku, gpu_sku=gpu_sku)
        if current is None:
            self.repository.mark_pending(
                cpu_sku=cpu_sku,
                gpu_sku=gpu_sku,
                reason="processing_started" if not force_refresh else "refresh_requested",
            )
            background_tasks.add_task(
                self.refresh_lookup,
                cpu_sku=cpu_sku,
                cpu_name=cpu_name,
                gpu_sku=gpu_sku,
                gpu_name=gpu_name,
            )
            return ReviewConsensusLookup(
                status="pending",
                reason="processing_started" if not force_refresh else "refresh_requested",
                review_consensus=None,
            )

        return self._to_lookup(current)

    def refresh_lookup(
        self,
        *,
        cpu_sku: str,
        cpu_name: str,
        gpu_sku: str,
        gpu_name: str,
    ) -> None:
        attempt = self.youtube_review_consensus_service.build_match_consensus_attempt(
            cpu_name=cpu_name,
            gpu_name=gpu_name,
        )
        if attempt.status == "ready" and attempt.review_consensus is not None:
            self.repository.save_ready(
                cpu_sku=cpu_sku,
                gpu_sku=gpu_sku,
                review_consensus=attempt.review_consensus,
            )
            return

        if attempt.status == "no_consensus":
            self.repository.save_no_consensus(
                cpu_sku=cpu_sku,
                gpu_sku=gpu_sku,
                reason=attempt.reason or "insufficient_evidence",
            )
            return

        self.repository.save_error(
            cpu_sku=cpu_sku,
            gpu_sku=gpu_sku,
            reason=attempt.reason or "processing_failed",
        )

    def _to_lookup(self, document: dict) -> ReviewConsensusLookup:
        review_consensus = None
        raw_review_consensus = document.get("review_consensus")
        if isinstance(raw_review_consensus, dict):
            tested_games = []
            for game in raw_review_consensus.get("tested_games", []):
                if not isinstance(game, dict):
                    continue
                tested_games.append(
                    MatchReviewedGame(
                        name=game.get("name", ""),
                        resolution=game.get("resolution"),
                        avg_fps=game.get("avg_fps"),
                    )
                )

            review_consensus = MatchReviewConsensus(
                insight=raw_review_consensus.get("insight", ""),
                warnings=tuple(raw_review_consensus.get("warnings", [])),
                confidence=raw_review_consensus.get("confidence", "low"),
                references=tuple(),
                source_count=raw_review_consensus.get("source_count", 0),
                average_explicit_fps=raw_review_consensus.get("average_explicit_fps"),
                tested_games=tuple(tested_games),
            )
            references = []
            for reference in raw_review_consensus.get("references", []):
                if not isinstance(reference, dict):
                    continue

                references.append(
                    YoutubeVideoReference(
                        title=reference.get("title", ""),
                        url=reference.get("url", ""),
                        channel=reference.get("channel"),
                    )
                )
            review_consensus = MatchReviewConsensus(
                insight=review_consensus.insight,
                warnings=review_consensus.warnings,
                confidence=review_consensus.confidence,
                references=tuple(references),
                source_count=review_consensus.source_count,
                average_explicit_fps=review_consensus.average_explicit_fps,
                tested_games=review_consensus.tested_games,
            )

        return ReviewConsensusLookup(
            status=document.get("status", "error"),
            reason=document.get("reason"),
            review_consensus=review_consensus,
        )
