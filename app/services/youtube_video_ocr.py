from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from io import BytesIO
from statistics import median
from typing import Protocol

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None

try:
    from imageio_ffmpeg import get_ffmpeg_exe
except ImportError:  # pragma: no cover
    get_ffmpeg_exe = None

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

try:
    from rapidocr_onnxruntime import RapidOCR
except ImportError:  # pragma: no cover
    RapidOCR = None

from app.services.youtube_video_sources import YoutubeVideoChapter, YoutubeVideoDetail


class YoutubeVideoOcrProvider(Protocol):
    def analyze(self, detail: YoutubeVideoDetail) -> tuple[str, ...]: ...


class NoopYoutubeVideoOcrProvider:
    def analyze(self, detail: YoutubeVideoDetail) -> tuple[str, ...]:
        return ()


@dataclass(frozen=True, slots=True)
class _FrameSample:
    chapter: YoutubeVideoChapter
    timestamp_seconds: float


@dataclass(frozen=True, slots=True)
class _FrameMetrics:
    avg_fps: float | None = None
    one_percent_low_fps: float | None = None
    resolution: str | None = None
    raw_lines: tuple[str, ...] = ()


class FfmpegRapidOcrYoutubeVideoOcrProvider:
    def __init__(
        self,
        *,
        timeout: float = 60.0,
        frame_limit: int = 4,
        frames_per_chapter: int = 5,
    ):
        self.timeout = timeout
        self.frame_limit = frame_limit
        self.frames_per_chapter = frames_per_chapter
        self.ocr_engine = RapidOCR() if RapidOCR is not None else None

    def analyze(self, detail: YoutubeVideoDetail) -> tuple[str, ...]:
        if self.ocr_engine is None or get_ffmpeg_exe is None or Image is None or cv2 is None or np is None:
            return ()
        if not detail.stream_url or not detail.chapters:
            return ()

        observations: list[str] = []
        seen: set[str] = set()
        for chapter in detail.chapters[: self.frame_limit]:
            metrics = self._analyze_chapter(detail.stream_url, chapter)
            observation = self._build_observation(chapter.title, metrics)
            if observation and observation not in seen:
                observations.append(observation)
                seen.add(observation)
        return tuple(observations)

    def _analyze_chapter(self, stream_url: str, chapter: YoutubeVideoChapter) -> _FrameMetrics:
        frame_metrics: list[_FrameMetrics] = []
        for sample in self._select_samples(chapter):
            frame_bytes = self._extract_frame(stream_url, sample.timestamp_seconds)
            if not frame_bytes:
                continue
            metrics = self._extract_metrics(frame_bytes)
            if metrics is not None:
                frame_metrics.append(metrics)

        avg_values = self._collect_metric_values(frame_metrics, "avg_fps")
        one_percent_values = self._collect_metric_values(frame_metrics, "one_percent_low_fps")
        resolutions = [metrics.resolution for metrics in frame_metrics if metrics.resolution is not None]
        raw_lines: list[str] = []
        for metrics in frame_metrics:
            raw_lines.extend(metrics.raw_lines[:4])

        return _FrameMetrics(
            avg_fps=self._median_without_outliers(avg_values),
            one_percent_low_fps=self._median_without_outliers(one_percent_values),
            resolution=self._most_common(resolutions),
            raw_lines=tuple(dict.fromkeys(raw_lines)),
        )

    def _select_samples(self, chapter: YoutubeVideoChapter) -> list[_FrameSample]:
        samples: list[_FrameSample] = []
        if chapter.end_time is not None and chapter.end_time > chapter.start_time:
            span = chapter.end_time - chapter.start_time
            start = chapter.start_time + min(3.0, span * 0.15)
            end = chapter.end_time - min(2.0, span * 0.15)
            if end <= start:
                timestamps = [chapter.start_time + max(span / 2, 1.0)]
            else:
                timestamps = [
                    start + ((end - start) * index / max(self.frames_per_chapter - 1, 1))
                    for index in range(self.frames_per_chapter)
                ]
        else:
            timestamps = [chapter.start_time + 3.0 + (index * 1.5) for index in range(self.frames_per_chapter)]
        for timestamp in timestamps:
            samples.append(_FrameSample(chapter=chapter, timestamp_seconds=max(timestamp, 0.0)))
        return samples

    def _extract_frame(self, stream_url: str, timestamp_seconds: float) -> bytes | None:
        ffmpeg = get_ffmpeg_exe()
        command = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{timestamp_seconds:.2f}",
            "-i",
            stream_url,
            "-frames:v",
            "1",
            "-vf",
            "scale='min(1600,iw)':-1",
            "-f",
            "image2pipe",
            "-vcodec",
            "png",
            "-",
        ]
        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if completed.returncode != 0 or not completed.stdout:
            return None
        return completed.stdout

    def _extract_metrics(self, image_bytes: bytes) -> _FrameMetrics | None:
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        regions = self._build_regions(image)
        lines: list[str] = []
        seen: set[str] = set()
        for region in regions:
            for variant in self._build_variants(region):
                try:
                    result, _ = self.ocr_engine(variant)
                except Exception:
                    continue
                for item in result or []:
                    if not isinstance(item, (list, tuple)) or len(item) < 2:
                        continue
                    text = self._normalize_text(str(item[1]))
                    if text and text not in seen:
                        lines.append(text)
                        seen.add(text)

        if not lines:
            return None
        return self._extract_frame_metrics(lines)

    def _build_regions(self, image: Image.Image) -> list[Image.Image]:
        width, height = image.size
        return [
            image.crop((0, 0, int(width * 0.18), int(height * 0.75))),
            image.crop((0, int(height * 0.2), int(width * 0.2), int(height * 0.75))),
            image.crop((0, int(height * 0.35), int(width * 0.2), int(height * 0.8))),
            image.crop((int(width * 0.75), 0, width, int(height * 0.2))),
            image.crop((0, 0, int(width * 0.3), int(height * 0.3))),
        ]

    def _build_variants(self, region: Image.Image) -> list[bytes]:
        variants: list[bytes] = []
        rgb = np.array(region)
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        upscaled = cv2.resize(bgr, None, fx=5, fy=5, interpolation=cv2.INTER_CUBIC)

        variants.append(self._encode_png(upscaled))

        gray = cv2.cvtColor(upscaled, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 185, 255, cv2.THRESH_BINARY)
        variants.append(self._encode_png(binary))

        hsv = cv2.cvtColor(upscaled, cv2.COLOR_BGR2HSV)
        masks = (
            cv2.inRange(hsv, (35, 40, 90), (95, 255, 255)),
            cv2.inRange(hsv, (10, 40, 90), (30, 255, 255)),
            cv2.inRange(hsv, (0, 0, 160), (180, 80, 255)),
        )
        for mask in masks:
            cleaned = cv2.medianBlur(mask, 3)
            variants.append(self._encode_png(cleaned))

        return [variant for variant in variants if variant]

    @staticmethod
    def _encode_png(image: np.ndarray) -> bytes:
        success, encoded = cv2.imencode(".png", image)
        return encoded.tobytes() if success else b""

    def _build_observation(self, chapter_title: str, metrics: _FrameMetrics) -> str:
        payload_lines: list[str] = []
        if metrics.resolution is not None:
            payload_lines.append(metrics.resolution)
        if metrics.avg_fps is not None:
            payload_lines.append(f"AVG FPS {metrics.avg_fps:.1f}".rstrip("0").rstrip("."))
        if metrics.one_percent_low_fps is not None:
            payload_lines.append(f"1% LOW FPS {metrics.one_percent_low_fps:.1f}".rstrip("0").rstrip("."))
        if not payload_lines:
            payload_lines.extend(metrics.raw_lines[:6])
        if not payload_lines:
            return ""
        return f"{chapter_title}\n" + "\n".join(dict.fromkeys(payload_lines))

    @staticmethod
    def _normalize_text(value: str) -> str:
        value = re.sub(r"\s+", " ", value).strip()
        return value

    def _extract_frame_metrics(self, lines: list[str]) -> _FrameMetrics:
        avg_values = self._extract_metric_values(lines, anchors=("AVG", "AVGFPS", "FPS"))
        low_values = self._extract_metric_values(lines, anchors=("1%LOW", "1%LOWFPS", "LOW1%"))
        resolution = self._extract_resolution(lines)
        return _FrameMetrics(
            avg_fps=self._median_without_outliers(avg_values),
            one_percent_low_fps=self._median_without_outliers(low_values),
            resolution=resolution,
            raw_lines=tuple(lines),
        )

    def _extract_metric_values(self, lines: list[str], *, anchors: tuple[str, ...]) -> list[float]:
        values: list[float] = []
        for index, line in enumerate(lines):
            upper = line.upper().replace(" ", "")
            if not any(anchor in upper for anchor in anchors):
                continue
            same_line_values = self._extract_numbers_from_line(line)
            if same_line_values:
                values.append(same_line_values[0])
                continue
            if following_value := self._extract_following_number(lines, index):
                values.append(following_value)
        return [value for value in values if 15 <= value <= 600]

    def _extract_following_number(self, lines: list[str], index: int) -> float | None:
        for line in lines[index + 1 : min(index + 3, len(lines))]:
            numbers = self._extract_numbers_from_line(line)
            if numbers:
                return numbers[0]
        return None

    @staticmethod
    def _extract_numbers_from_line(line: str) -> list[float]:
        return [float(match) for match in re.findall(r"\b(\d{2,3}(?:\.\d+)?)\b", line)]

    @staticmethod
    def _extract_resolution(lines: list[str]) -> str | None:
        combined = " ".join(lines).upper()
        if "2160P" in combined or "4K" in combined:
            return "4K"
        if "1440P" in combined:
            return "1440p"
        if "1080P" in combined:
            return "1080p"
        if "720P" in combined:
            return "720p"
        return None

    @staticmethod
    def _collect_metric_values(frame_metrics: list[_FrameMetrics], field_name: str) -> list[float]:
        return [
            float(value)
            for metrics in frame_metrics
            if (value := getattr(metrics, field_name)) is not None
        ]

    @staticmethod
    def _median_without_outliers(values: list[float]) -> float | None:
        if not values:
            return None
        values = sorted(values)
        if len(values) >= 4:
            inner = values[1:-1]
            if inner:
                values = inner
        return round(float(median(values)), 1)

    @staticmethod
    def _most_common(values: list[str]) -> str | None:
        if not values:
            return None
        counts: dict[str, int] = {}
        for value in values:
            counts[value] = counts.get(value, 0) + 1
        return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
