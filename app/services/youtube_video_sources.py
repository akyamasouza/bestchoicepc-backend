from __future__ import annotations

import html as html_lib
import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

try:
    from yt_dlp import YoutubeDL
except ImportError:  # pragma: no cover
    YoutubeDL = None

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:  # pragma: no cover
    YouTubeTranscriptApi = None


DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0"}
_LANGUAGE_PRIORITY = ("en", "en-US", "en-GB", "pt", "pt-BR", "pt-PT")
_CAPTION_EXT_PRIORITY = ("json3", "srv3", "vtt", "ttml")


@dataclass(frozen=True, slots=True)
class YoutubeSearchResult:
    title: str
    url: str
    channel: str | None
    snippet: str
    duration_seconds: int | None


@dataclass(frozen=True, slots=True)
class YoutubeVideoChapter:
    title: str
    start_time: float
    end_time: float | None = None


@dataclass(frozen=True, slots=True)
class YoutubeVideoDetail:
    title: str
    url: str
    channel: str | None
    description: str
    transcript: str
    chapters: tuple[YoutubeVideoChapter, ...]
    stream_url: str | None = None
    ocr_observations: tuple[str, ...] = ()


class YoutubeSearchProvider(Protocol):
    def search(self, query: str) -> list[YoutubeSearchResult]: ...


class YoutubeVideoDetailProvider(Protocol):
    def fetch(self, *, url: str, fallback_title: str, fallback_channel: str | None) -> YoutubeVideoDetail: ...


class YtDlpYoutubeSearchProvider:
    def __init__(self, *, timeout: float):
        self.timeout = timeout

    def search(self, query: str) -> list[YoutubeSearchResult]:
        if YoutubeDL is None:
            raise RuntimeError("yt-dlp indisponivel")

        with YoutubeDL(self._options(extract_flat=True)) as ydl:
            payload = ydl.extract_info(f"ytsearch8:{query}", download=False)

        results: list[YoutubeSearchResult] = []
        for entry in payload.get("entries") or []:
            if not isinstance(entry, dict):
                continue
            title = _safe_text(entry.get("title"))
            url = _safe_text(entry.get("url"))
            if not title or not url:
                continue
            results.append(
                YoutubeSearchResult(
                    title=title,
                    url=url if url.startswith("http") else f"https://www.youtube.com/watch?v={url}",
                    channel=_safe_text(entry.get("channel") or entry.get("uploader")) or None,
                    snippet=_safe_text(entry.get("description")),
                    duration_seconds=_coerce_duration_seconds(entry.get("duration")),
                )
            )
        return results

    def _options(self, *, extract_flat: bool) -> dict[str, Any]:
        return {
            "quiet": True,
            "skip_download": True,
            "noplaylist": True,
            "no_warnings": True,
            "extract_flat": extract_flat,
            "socket_timeout": self.timeout,
        }


class YtDlpYoutubeVideoDetailProvider:
    def __init__(self, *, timeout: float):
        self.timeout = timeout

    def fetch(self, *, url: str, fallback_title: str, fallback_channel: str | None) -> YoutubeVideoDetail:
        if YoutubeDL is None:
            raise RuntimeError("yt-dlp indisponivel")

        with YoutubeDL(self._options()) as ydl:
            info = ydl.extract_info(url, download=False)

        description = _normalize_text(_safe_text(info.get("description")))
        chapters = tuple(
            YoutubeVideoChapter(
                title=_normalize_text(_safe_text(chapter.get("title"))),
                start_time=float(chapter.get("start_time") or 0.0),
                end_time=float(chapter["end_time"]) if chapter.get("end_time") is not None else None,
            )
            for chapter in info.get("chapters") or []
            if isinstance(chapter, dict) and _safe_text(chapter.get("title"))
        )
        video_id = _safe_text(info.get("id")) or url.rsplit("=", 1)[-1]
        transcript = self._extract_subtitle_text(info) or self._fetch_transcript(video_id)

        return YoutubeVideoDetail(
            title=_safe_text(info.get("title")) or fallback_title,
            url=url,
            channel=_safe_text(info.get("uploader") or info.get("channel")) or fallback_channel,
            description=description,
            transcript=transcript,
            chapters=chapters,
            stream_url=_safe_text(info.get("url")) or None,
        )

    def _options(self) -> dict[str, Any]:
        return {
            "quiet": True,
            "skip_download": True,
            "noplaylist": True,
            "no_warnings": True,
            "socket_timeout": self.timeout,
        }

    def _fetch_transcript(self, video_id: str) -> str:
        if YouTubeTranscriptApi is None:
            return ""
        try:
            fetched = YouTubeTranscriptApi().fetch(video_id, languages=_LANGUAGE_PRIORITY, preserve_formatting=False)
            raw_items = fetched.to_raw_data()
        except Exception:
            return ""

        parts = [
            _normalize_text(_safe_text(item.get("text")))
            for item in raw_items
            if isinstance(item, dict)
        ]
        return "\n".join(part for part in parts if part)

    def _extract_subtitle_text(self, info: dict[str, Any]) -> str:
        tracks = self._collect_caption_tracks(info)
        for url, ext in tracks:
            try:
                response = httpx.get(url, timeout=self.timeout, follow_redirects=True, headers=DEFAULT_HEADERS)
                response.raise_for_status()
            except httpx.HTTPError:
                continue
            text = self._parse_caption_payload(response.text, ext=ext)
            if text:
                return text
        return ""

    def _collect_caption_tracks(self, info: dict[str, Any]) -> list[tuple[str, str]]:
        tracks: list[tuple[int, int, str, str]] = []
        for group_name in ("subtitles", "automatic_captions"):
            groups = info.get(group_name)
            if not isinstance(groups, dict):
                continue
            for language, formats in groups.items():
                if not isinstance(formats, list):
                    continue
                language_priority = _language_priority(language)
                for format_item in formats:
                    if not isinstance(format_item, dict):
                        continue
                    url = _safe_text(format_item.get("url"))
                    ext = _safe_text(format_item.get("ext"))
                    if not url or ext not in _CAPTION_EXT_PRIORITY:
                        continue
                    tracks.append((language_priority, _CAPTION_EXT_PRIORITY.index(ext), url, ext))
        tracks.sort(key=lambda item: (item[0], item[1], item[2]))
        return [(url, ext) for _, _, url, ext in tracks]

    def _parse_caption_payload(self, payload: str, *, ext: str) -> str:
        if ext in {"json3", "srv3"}:
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                return ""
            parts: list[str] = []
            for event in data.get("events") or []:
                if not isinstance(event, dict):
                    continue
                for segment in event.get("segs") or []:
                    if not isinstance(segment, dict):
                        continue
                    text = _normalize_text(_safe_text(segment.get("utf8")))
                    if text:
                        parts.append(text)
            return "\n".join(parts)

        cleaned_lines: list[str] = []
        for line in payload.splitlines():
            line = line.strip()
            if not line or line == "WEBVTT" or "-->" in line or re.fullmatch(r"\d+", line):
                continue
            cleaned_lines.append(_normalize_text(line))
        return "\n".join(line for line in cleaned_lines if line)


def _safe_text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _normalize_text(value: str) -> str:
    if not value:
        return ""
    value = html_lib.unescape(value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = value.replace("\u200b", " ")
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _coerce_duration_seconds(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        parts = value.split(":")
        if not all(part.isdigit() for part in parts):
            return None
        seconds = 0
        for part in parts:
            seconds = seconds * 60 + int(part)
        return seconds
    return None


def _language_priority(language: str) -> int:
    normalized = language.lower()
    for index, prefix in enumerate(_LANGUAGE_PRIORITY):
        if normalized == prefix.lower() or normalized.startswith(prefix.lower()):
            return index
    return len(_LANGUAGE_PRIORITY)
