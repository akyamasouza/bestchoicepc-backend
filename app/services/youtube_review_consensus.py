from __future__ import annotations

import json
import re
from dataclasses import dataclass
from json import JSONDecoder
from statistics import mean
from typing import Any
from urllib.parse import quote_plus

import httpx

from app.services.youtube_video_ocr import (
    FfmpegRapidOcrYoutubeVideoOcrProvider,
    YoutubeVideoOcrProvider,
)
from app.services.youtube_video_sources import (
    YoutubeSearchProvider,
    YoutubeSearchResult,
    YoutubeVideoDetail,
    YoutubeVideoDetailProvider,
    YtDlpYoutubeSearchProvider,
    YtDlpYoutubeVideoDetailProvider,
)


YOUTUBE_SEARCH_URL = "https://www.youtube.com/results"
DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0"}


@dataclass(frozen=True, slots=True)
class YoutubeVideoReference:
    title: str
    url: str
    channel: str | None = None


@dataclass(frozen=True, slots=True)
class MatchReviewedGame:
    name: str
    resolution: str | None
    avg_fps: float | None


@dataclass(frozen=True, slots=True)
class MatchReviewConsensus:
    insight: str
    warnings: tuple[str, ...]
    confidence: str
    references: tuple[YoutubeVideoReference, ...]
    source_count: int
    average_explicit_fps: float | None = None
    tested_games: tuple[MatchReviewedGame, ...] = ()


@dataclass(frozen=True, slots=True)
class MatchReviewConsensusAttempt:
    status: str
    reason: str | None
    review_consensus: MatchReviewConsensus | None


@dataclass(frozen=True, slots=True)
class _YoutubeVideoCandidate:
    title: str
    url: str
    channel: str | None
    snippet: str
    duration_seconds: int | None
    relevance_score: float


@dataclass(frozen=True, slots=True)
class _ReviewEnrichment:
    average_explicit_fps: float | None
    tested_games: tuple[MatchReviewedGame, ...]
    mentioned_resolutions: tuple[str, ...]


class YoutubeReviewConsensusService:
    _POSITIVE_PHRASES = (
        "GOOD PAIR",
        "GOOD COMBO",
        "BALANCED",
        "GREAT PAIR",
        "GREAT COMBO",
        "WELL MATCHED",
    )
    _NEGATIVE_PHRASES = (
        "BOTTLENECK",
        "OVERKILL",
        "NOT WORTH",
        "BAD PAIR",
        "BAD COMBO",
    )
    _QUALITY_HINTS = ("TEST", "BENCHMARK", "REVIEW", "GAMES", "1440P", "1080P", "4K", "2160P")
    _BANNED_HINTS = ("SHORTS", "RUMOR", "RUMOUR", "LEAK", "NEWS", "TOP 5", "TOP 10", " VS ")
    _GAME_TITLES = (
        "Cyberpunk 2077",
        "Alan Wake 2",
        "Black Myth: Wukong",
        "Black Myth Wukong",
        "The Last of Us Part I",
        "The Last of Us Part II",
        "Forza Horizon 5",
        "Starfield",
        "Hogwarts Legacy",
        "Red Dead Redemption 2",
        "Red Dead Redemption II",
        "Silent Hill 2",
        "Counter-Strike 2",
        "Counter Strike 2",
        "CS 2",
        "Call of Duty: Warzone",
        "Call of Duty Warzone",
        "Warzone",
        "Spider-Man 2",
        "Marvel's Spider-Man 2",
        "God of War Ragnarok",
        "God of War",
        "A Plague Tale: Requiem",
        "Plague Tale Requiem",
        "Avatar: Frontiers of Pandora",
        "Avatar Frontiers of Pandora",
        "Dragon's Dogma 2",
        "Dragons Dogma 2",
        "S.T.A.L.K.E.R. 2",
        "STALKER 2",
        "Assassin's Creed Shadows",
        "Assassins Creed Shadows",
        "Ghost of Tsushima",
        "The Witcher 3",
        "Indiana Jones and the Great Circle",
        "Indiana Jones",
        "Fortnite",
        "Apex Legends",
        "Valorant",
        "PUBG",
        "Doom The Dark Ages",
        "Doom",
        "Mafia",
        "Monster Hunter Wilds",
        "Oblivion Remastered",
        "The Outer Worlds 2",
        "Wukong",
        "Expedition 33",
        "Palworld",
        "Far Cry 6",
        "Resident Evil 4",
        "Returnal",
        "F1 24",
        "Battlefield 2042",
        "ARC Raiders",
        "Marvel Rivals",
        "Rust",
    )

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        search_provider: YoutubeSearchProvider | None = None,
        video_detail_provider: YoutubeVideoDetailProvider | None = None,
        ocr_provider: YoutubeVideoOcrProvider | None = None,
    ):
        self.timeout = timeout
        self.search_provider = search_provider or YtDlpYoutubeSearchProvider(timeout=timeout)
        self.video_detail_provider = video_detail_provider or YtDlpYoutubeVideoDetailProvider(timeout=timeout)
        self.ocr_provider = ocr_provider or FfmpegRapidOcrYoutubeVideoOcrProvider(timeout=timeout)

    def build_match_consensus(self, *, cpu_name: str, gpu_name: str) -> MatchReviewConsensus | None:
        attempt = self.build_match_consensus_attempt(cpu_name=cpu_name, gpu_name=gpu_name)
        return attempt.review_consensus

    def build_match_consensus_attempt(
        self,
        *,
        cpu_name: str,
        gpu_name: str,
    ) -> MatchReviewConsensusAttempt:
        query = f"{cpu_name} {gpu_name}"
        try:
            candidates = self._search_candidates(query=query, cpu_name=cpu_name, gpu_name=gpu_name)
        except httpx.HTTPError:
            return MatchReviewConsensusAttempt(status="error", reason="youtube_unavailable", review_consensus=None)
        except (ValueError, json.JSONDecodeError):
            return MatchReviewConsensusAttempt(status="error", reason="parse_error", review_consensus=None)

        if not candidates:
            return MatchReviewConsensusAttempt(status="no_consensus", reason="insufficient_evidence", review_consensus=None)

        candidate_details = [
            (candidate, self._enrich_detail_with_ocr(self._fetch_video_detail(candidate)))
            for candidate in candidates[:6]
        ]
        candidate_details.sort(
            key=lambda item: (
                -(item[0].relevance_score + self._score_detail_evidence(item[0], item[1])),
                -item[0].relevance_score,
                item[0].title,
            )
        )
        selected_pairs = candidate_details[:3]
        if not selected_pairs:
            return MatchReviewConsensusAttempt(status="no_consensus", reason="insufficient_evidence", review_consensus=None)

        selected = [candidate for candidate, _ in selected_pairs]
        details = tuple(detail for _, detail in selected_pairs)
        enrichment = self._build_enrichment(selected=selected, details=details)
        if not self._has_structured_evidence(enrichment):
            return MatchReviewConsensusAttempt(status="no_consensus", reason="insufficient_evidence", review_consensus=None)

        confidence = "medium" if len(selected) >= 2 else "low"
        reason = None if len(selected) >= 2 else "partial_evidence"
        return MatchReviewConsensusAttempt(
            status="ready",
            reason=reason,
            review_consensus=MatchReviewConsensus(
                insight=self._build_insight(selected=selected, enrichment=enrichment),
                warnings=tuple(self._build_warnings(selected=selected, enrichment=enrichment)),
                confidence=confidence,
                references=tuple(
                    YoutubeVideoReference(title=item.title, url=item.url, channel=item.channel)
                    for item in selected
                ),
                source_count=len(selected),
                average_explicit_fps=enrichment.average_explicit_fps,
                tested_games=enrichment.tested_games,
            ),
        )

    def _search_candidates(self, *, query: str, cpu_name: str, gpu_name: str) -> list[_YoutubeVideoCandidate]:
        cpu_markers = self._extract_cpu_markers(cpu_name)
        gpu_markers = self._extract_gpu_markers(gpu_name)
        try:
            provider_results = self.search_provider.search(query)
        except Exception:
            provider_results = []

        if provider_results:
            candidates = [
                candidate
                for result in provider_results
                if (candidate := self._build_candidate_from_search_result(
                    result,
                    cpu_markers=cpu_markers,
                    gpu_markers=gpu_markers,
                )) is not None
            ]
            candidates.sort(key=lambda item: (-item.relevance_score, item.duration_seconds or 0, item.title))
            return candidates

        html = self._fetch_search_html(query)
        initial_data = self._extract_initial_data(html)
        candidates: list[_YoutubeVideoCandidate] = []
        for renderer in self._iter_video_renderers(initial_data):
            candidate = self._build_candidate(renderer, cpu_markers=cpu_markers, gpu_markers=gpu_markers)
            if candidate is not None:
                candidates.append(candidate)
        candidates.sort(key=lambda item: (-item.relevance_score, item.duration_seconds or 0, item.title))
        return candidates

    def _fetch_search_html(self, query: str) -> str:
        response = httpx.get(
            f"{YOUTUBE_SEARCH_URL}?search_query={quote_plus(query)}",
            timeout=self.timeout,
            follow_redirects=True,
            headers=DEFAULT_HEADERS,
        )
        response.raise_for_status()
        return response.text

    @staticmethod
    def _extract_initial_data(html: str) -> dict[str, Any]:
        return YoutubeReviewConsensusService._extract_json_payload(
            html,
            markers=("var ytInitialData = ", "ytInitialData = "),
        )

    @staticmethod
    def _extract_json_payload(html: str, *, markers: tuple[str, ...]) -> dict[str, Any]:
        start = -1
        for marker in markers:
            start = html.find(marker)
            if start >= 0:
                start = html.find("{", start)
                break
        if start < 0:
            raise ValueError("Nao foi possivel localizar o payload esperado na pagina do YouTube.")
        payload, _ = JSONDecoder().raw_decode(html[start:])
        return payload

    def _fetch_video_detail(self, candidate: _YoutubeVideoCandidate) -> YoutubeVideoDetail:
        try:
            return self.video_detail_provider.fetch(
                url=candidate.url,
                fallback_title=candidate.title,
                fallback_channel=candidate.channel,
            )
        except Exception:
            pass

        try:
            html = self._fetch_video_html(candidate.url)
            payload = self._extract_json_payload(
                html,
                markers=("var ytInitialPlayerResponse = ", "ytInitialPlayerResponse = "),
            )
            video_details = payload.get("videoDetails")
            if not isinstance(video_details, dict):
                raise ValueError("videoDetails ausente")
            return YoutubeVideoDetail(
                title=video_details.get("title") or candidate.title,
                url=candidate.url,
                channel=video_details.get("author") or candidate.channel,
                description=video_details.get("shortDescription") or "",
                transcript="",
                chapters=(),
            )
        except (httpx.HTTPError, ValueError, json.JSONDecodeError):
            return YoutubeVideoDetail(
                title=candidate.title,
                url=candidate.url,
                channel=candidate.channel,
                description=candidate.snippet,
                transcript="",
                chapters=(),
            )

    def _fetch_video_html(self, url: str) -> str:
        response = httpx.get(
            url,
            timeout=self.timeout,
            follow_redirects=True,
            headers=DEFAULT_HEADERS,
        )
        response.raise_for_status()
        return response.text

    def _enrich_detail_with_ocr(self, detail: YoutubeVideoDetail) -> YoutubeVideoDetail:
        try:
            observations = self.ocr_provider.analyze(detail)
        except Exception:
            observations = ()
        if not observations:
            return detail
        return YoutubeVideoDetail(
            title=detail.title,
            url=detail.url,
            channel=detail.channel,
            description=detail.description,
            transcript=detail.transcript,
            chapters=detail.chapters,
            stream_url=detail.stream_url,
            ocr_observations=observations,
        )

    def _score_detail_evidence(self, candidate: _YoutubeVideoCandidate, detail: YoutubeVideoDetail) -> float:
        units = self._split_analysis_units(
            candidate.title,
            candidate.snippet,
            detail.description,
            detail.transcript,
            *[chapter.title for chapter in detail.chapters],
            *detail.ocr_observations,
        )
        explicit_fps_hits = sum(self._extract_avg_fps(unit) is not None for unit in units)
        resolution_hits = sum(self._extract_resolution(unit) is not None for unit in units)
        games = {game_name for unit in units for game_name in self._extract_games(unit)}

        score = 0.0
        score += min(len(detail.chapters), 10)
        score += 12 if detail.transcript else 0
        score += min(len(games) * 4, 20)
        score += min(explicit_fps_hits * 8, 24)
        score += min(resolution_hits * 3, 9)
        return score

    def _build_enrichment(
        self,
        *,
        selected: list[_YoutubeVideoCandidate],
        details: tuple[YoutubeVideoDetail, ...],
    ) -> _ReviewEnrichment:
        mentioned_resolution_counts: dict[str, int] = {}
        game_buckets: dict[str, dict[str, Any]] = {}
        explicit_fps_values: list[float] = []

        for candidate, detail in zip(selected, details, strict=False):
            texts = (
                candidate.title,
                candidate.snippet,
                detail.description,
                detail.transcript,
                *[chapter.title for chapter in detail.chapters],
                *detail.ocr_observations,
            )
            
            current_game: str | None = None
            current_resolution: str | None = None
            
            for unit in self._split_analysis_units(*texts):
                resolution = self._extract_resolution(unit)
                if resolution is not None:
                    current_resolution = resolution
                    mentioned_resolution_counts[resolution] = mentioned_resolution_counts.get(resolution, 0) + 1

                avg_fps = self._extract_avg_fps(unit)
                if avg_fps is not None:
                    explicit_fps_values.append(avg_fps)

                matched_games = self._extract_games(unit)
                if matched_games:
                    current_game = matched_games[0] if len(matched_games) == 1 else None
                    for game_name in matched_games:
                        bucket = game_buckets.setdefault(
                            game_name,
                            {"count": 0, "resolutions": [], "fps_values": []},
                        )
                        bucket["count"] += 1
                        if resolution is not None:
                            bucket["resolutions"].append(resolution)
                        elif current_resolution is not None:
                            bucket["resolutions"].append(current_resolution)
                        
                        if avg_fps is not None and len(matched_games) == 1:
                            bucket["fps_values"].append(avg_fps)
                elif avg_fps is not None and current_game is not None:
                    bucket = game_buckets.setdefault(
                        current_game,
                        {"count": 0, "resolutions": [], "fps_values": []},
                    )
                    bucket["fps_values"].append(avg_fps)
                    if current_resolution is not None:
                        bucket["resolutions"].append(current_resolution)

        tested_games: list[MatchReviewedGame] = []
        for game_name, bucket in sorted(
            game_buckets.items(),
            key=lambda item: (-item[1]["count"], -len(item[1]["fps_values"]), item[0]),
        )[:5]:
            tested_games.append(
                MatchReviewedGame(
                    name=game_name,
                    resolution=self._most_common(bucket["resolutions"]),
                    avg_fps=round(mean(bucket["fps_values"]), 1) if bucket["fps_values"] else None,
                )
            )

        return _ReviewEnrichment(
            average_explicit_fps=round(mean(explicit_fps_values), 1) if explicit_fps_values else None,
            tested_games=tuple(tested_games),
            mentioned_resolutions=tuple(
                label
                for label, count in sorted(
                    mentioned_resolution_counts.items(),
                    key=lambda item: (-item[1], item[0]),
                )
                if count >= 1
            ),
        )

    def _build_candidate_from_search_result(
        self,
        result: YoutubeSearchResult,
        *,
        cpu_markers: tuple[str, ...],
        gpu_markers: tuple[str, ...],
    ) -> _YoutubeVideoCandidate | None:
        haystack = f"{result.title} {result.snippet}".upper()
        if any(hint in haystack for hint in self._BANNED_HINTS):
            return None
        if not self._matches_markers(haystack, cpu_markers) or not self._matches_markers(haystack, gpu_markers):
            return None
        if result.duration_seconds is not None and result.duration_seconds < 360:
            return None

        relevance_score = self._score_candidate(
            title=result.title,
            snippet=result.snippet,
            duration_seconds=result.duration_seconds,
            cpu_markers=cpu_markers,
            gpu_markers=gpu_markers,
        )
        if relevance_score <= 0:
            return None

        return _YoutubeVideoCandidate(
            title=result.title,
            url=result.url,
            channel=result.channel,
            snippet=result.snippet,
            duration_seconds=result.duration_seconds,
            relevance_score=relevance_score,
        )

    def _build_candidate(
        self,
        renderer: dict[str, Any],
        *,
        cpu_markers: tuple[str, ...],
        gpu_markers: tuple[str, ...],
    ) -> _YoutubeVideoCandidate | None:
        video_id = renderer.get("videoId")
        title = self._extract_runs_text(renderer.get("title"))
        if not video_id or not title:
            return None

        snippet = self._extract_runs_text(renderer.get("detailedMetadataSnippets")) or self._extract_runs_text(
            renderer.get("descriptionSnippet")
        )
        duration_text = self._extract_simple_text(renderer.get("lengthText"))
        duration_seconds = self._parse_duration_seconds(duration_text)
        return self._build_candidate_from_search_result(
            YoutubeSearchResult(
                title=title,
                url=f"https://www.youtube.com/watch?v={video_id}",
                channel=self._extract_runs_text(renderer.get("ownerText")) or self._extract_runs_text(renderer.get("longBylineText")) or None,
                snippet=snippet,
                duration_seconds=duration_seconds,
            ),
            cpu_markers=cpu_markers,
            gpu_markers=gpu_markers,
        )

    def _score_candidate(
        self,
        *,
        title: str,
        snippet: str,
        duration_seconds: int | None,
        cpu_markers: tuple[str, ...],
        gpu_markers: tuple[str, ...],
    ) -> float:
        title_upper = title.upper()
        snippet_upper = snippet.upper()
        score = 0.0

        if self._matches_markers(title_upper, cpu_markers):
            score += 35
        elif self._matches_markers(snippet_upper, cpu_markers):
            score += 20

        if self._matches_markers(title_upper, gpu_markers):
            score += 35
        elif self._matches_markers(snippet_upper, gpu_markers):
            score += 20

        score += sum(4 for hint in self._QUALITY_HINTS if hint in title_upper)
        score += sum(2 for hint in self._QUALITY_HINTS if hint in snippet_upper)

        if duration_seconds is not None and duration_seconds >= 600:
            score += 5

        return score

    def _build_insight(
        self,
        *,
        selected: list[_YoutubeVideoCandidate],
        enrichment: _ReviewEnrichment,
    ) -> str:
        fragments: list[str] = []
        if enrichment.mentioned_resolutions:
            if len(enrichment.mentioned_resolutions) == 1:
                fragments.append(f"Os reviews relevantes concentram os testes principalmente em {enrichment.mentioned_resolutions[0]}")
            else:
                fragments.append(f"Os reviews relevantes cobrem este par em {', '.join(enrichment.mentioned_resolutions[:3])}")
        else:
            fragments.append("Os reviews relevantes mostram benchmarks do par exato")

        if enrichment.average_explicit_fps is not None:
            fragments.append(
                f"nos trechos com FPS explicito, a media observada ficou em torno de {enrichment.average_explicit_fps:.1f} FPS"
            )
        if enrichment.tested_games:
            game_names = [game.name for game in enrichment.tested_games[:3]]
            if len(game_names) == 1:
                fragments.append(f"os jogos mais citados incluem {game_names[0]}")
            elif len(game_names) == 2:
                fragments.append(f"os jogos mais citados incluem {game_names[0]} e {game_names[1]}")
            else:
                fragments.append(f"os jogos mais citados incluem {game_names[0]}, {game_names[1]} e {game_names[2]}")

        return ". ".join(self._capitalize_fragment(fragment.rstrip(".")) for fragment in fragments) + "."

    def _build_warnings(
        self,
        *,
        selected: list[_YoutubeVideoCandidate],
        enrichment: _ReviewEnrichment,
    ) -> list[str]:
        warnings: list[str] = []
        combined_texts = [f"{candidate.title} {candidate.snippet}".upper() for candidate in selected]
        if sum(any(phrase in text for phrase in self._NEGATIVE_PHRASES) for text in combined_texts) >= 1:
            warnings.append("Pelo menos um review menciona risco de bottleneck ou overkill.")
        if enrichment.average_explicit_fps is None:
            warnings.append("Nem todos os videos permitem capturar FPS medio de forma confiavel.")
        return warnings

    @staticmethod
    def _iter_video_renderers(payload: Any):
        if isinstance(payload, dict):
            for key, value in payload.items():
                if key == "videoRenderer" and isinstance(value, dict):
                    yield value
                else:
                    yield from YoutubeReviewConsensusService._iter_video_renderers(value)
        elif isinstance(payload, list):
            for item in payload:
                yield from YoutubeReviewConsensusService._iter_video_renderers(item)

    @staticmethod
    def _extract_simple_text(value: Any) -> str:
        if not isinstance(value, dict):
            return ""
        if isinstance(value.get("simpleText"), str):
            return value["simpleText"]
        return YoutubeReviewConsensusService._extract_runs_text(value)

    @staticmethod
    def _extract_runs_text(value: Any) -> str:
        if isinstance(value, list):
            return " ".join(YoutubeReviewConsensusService._extract_runs_text(item) for item in value).strip()
        if not isinstance(value, dict):
            return ""
        if isinstance(value.get("text"), str):
            return value["text"]
        runs = value.get("runs")
        if isinstance(runs, list):
            return " ".join(item.get("text", "") for item in runs if isinstance(item, dict)).strip()
        if isinstance(value.get("simpleText"), str):
            return value["simpleText"]
        return ""

    @staticmethod
    def _parse_duration_seconds(value: str) -> int | None:
        if not value:
            return None
        parts = value.split(":")
        if not all(part.isdigit() for part in parts):
            return None
        seconds = 0
        for part in parts:
            seconds = seconds * 60 + int(part)
        return seconds

    @staticmethod
    def _split_analysis_units(*texts: str) -> list[str]:
        units: list[str] = []
        for text in texts:
            if not text:
                continue
            for line in text.replace("\r", "\n").split("\n"):
                for sentence in re.split(r"(?<=[.!?])\s+", line):
                    for segment in re.split(r"[|•]+", sentence):
                        cleaned = segment.strip(" -\t")
                        if cleaned:
                            units.append(cleaned)
        return units

    def _extract_games(self, text: str) -> list[str]:
        normalized = text.upper()
        matches: list[str] = []
        occupied_spans: list[tuple[int, int]] = []
        for game_name in sorted(self._GAME_TITLES, key=len, reverse=True):
            index = normalized.find(game_name.upper())
            if index < 0:
                continue
            span = (index, index + len(game_name))
            if any(start <= span[0] and end >= span[1] for start, end in occupied_spans):
                continue
            matches.append(game_name)
            occupied_spans.append(span)
        return matches

    @staticmethod
    def _extract_resolution(text: str) -> str | None:
        normalized = text.upper()
        if "2160P" in normalized:
            return "4K"
        for resolution in ("8K", "4K", "1440P", "1080P", "720P"):
            if resolution in normalized:
                return resolution.replace("P", "p") if resolution.endswith("P") else resolution
        return None

    @staticmethod
    def _extract_avg_fps(text: str) -> float | None:
        patterns = (
            r"\bAVG(?:ERAGE)?\s*FPS\s*[:=-]?\s*(\d{2,3}(?:\.\d+)?)\b",
            r"\b(\d{2,3}(?:\.\d+)?)\s*AVG\s*FPS\b",
            r"\bAVG\s*[:=-]?\s*(\d{2,3}(?:\.\d+)?)\b",
            r"\bFPS\s*[:=-]?\s*(\d{2,3}(?:\.\d+)?)\b",
            r"\b(\d{2,3}(?:\.\d+)?)\s*FPS\b",
        )
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match is not None:
                return float(match.group(1))
        return None

    @staticmethod
    def _most_common(values: list[str]) -> str | None:
        if not values:
            return None
        counts: dict[str, int] = {}
        for value in values:
            counts[value] = counts.get(value, 0) + 1
        return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]

    @staticmethod
    def _capitalize_fragment(text: str) -> str:
        if not text:
            return text
        return text[0].upper() + text[1:]

    @staticmethod
    def _has_structured_evidence(enrichment: _ReviewEnrichment) -> bool:
        return bool(
            enrichment.average_explicit_fps is not None
            or enrichment.tested_games
            or enrichment.mentioned_resolutions
        )

    @staticmethod
    def _matches_markers(haystack: str, markers: tuple[str, ...]) -> bool:
        return all(marker in haystack for marker in markers)

    @staticmethod
    def _extract_cpu_markers(name: str) -> tuple[str, ...]:
        normalized = name.upper()
        intel_match = re.search(r"\b(I[3579])[- ]?(\d{4,5}[A-Z]{0,3})\b", normalized)
        if intel_match is not None:
            return intel_match.group(1), intel_match.group(2)

        amd_match = re.search(r"\b(\d{4,5}(?:X3D|X|G|F|HX|HS)?)\b", normalized)
        if amd_match is not None:
            return (amd_match.group(1),)

        tokens = [token for token in re.findall(r"[A-Z0-9]+", normalized) if len(token) >= 4]
        return tuple(tokens[:1])

    @staticmethod
    def _extract_gpu_markers(name: str) -> tuple[str, ...]:
        normalized = name.upper()
        rtx_match = re.search(r"\b(RTX|GTX)\s*(\d{4})\s*(TI SUPER|SUPER|TI)?\b", normalized)
        if rtx_match is not None:
            markers = [rtx_match.group(1), rtx_match.group(2)]
            if rtx_match.group(3):
                markers.append(rtx_match.group(3))
            return tuple(markers)

        rx_match = re.search(r"\b(RX)\s*(\d{4})\s*(XT|GRE)?\b", normalized)
        if rx_match is not None:
            markers = [rx_match.group(1), rx_match.group(2)]
            if rx_match.group(3):
                markers.append(rx_match.group(3))
            return tuple(markers)

        tokens = [token for token in re.findall(r"[A-Z0-9]+", normalized) if len(token) >= 4]
        return tuple(tokens[:2])
