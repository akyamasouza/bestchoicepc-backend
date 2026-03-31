from app.services.youtube_video_ocr import (
    FfmpegRapidOcrYoutubeVideoOcrProvider,
    _FrameMetrics,
)
from app.services.youtube_video_sources import YoutubeVideoChapter


def _build_provider(*, frames_per_chapter: int = 5) -> FfmpegRapidOcrYoutubeVideoOcrProvider:
    provider = object.__new__(FfmpegRapidOcrYoutubeVideoOcrProvider)
    provider.timeout = 60.0
    provider.frame_limit = 4
    provider.frames_per_chapter = frames_per_chapter
    provider.ocr_engine = None
    return provider


def test_select_samples_spreads_multiple_frames_inside_chapter() -> None:
    provider = _build_provider(frames_per_chapter=5)
    chapter = YoutubeVideoChapter(title="Cyberpunk 2077", start_time=10.0, end_time=40.0)

    samples = provider._select_samples(chapter)

    assert len(samples) == 5
    assert samples[0].timestamp_seconds >= 13.0
    assert samples[-1].timestamp_seconds <= 38.0
    assert samples[0].timestamp_seconds < samples[-1].timestamp_seconds


def test_extract_frame_metrics_prefers_anchored_fps_and_resolution() -> None:
    provider = _build_provider()

    metrics = provider._extract_frame_metrics(
        [
            "Cyberpunk 2077",
            "1440P ULTRA",
            "AVG",
            "92",
            "1% LOW",
            "74",
            "GPU 99%",
            "120W",
        ]
    )

    assert metrics.resolution == "1440p"
    assert metrics.avg_fps == 92.0
    assert metrics.one_percent_low_fps == 74.0


def test_build_observation_uses_median_and_drops_outliers() -> None:
    provider = _build_provider()

    assert provider._median_without_outliers([91.0, 92.0, 93.0, 250.0, 20.0]) == 92.0

    observation = provider._build_observation(
        "Alan Wake 2 | 1440p",
        _FrameMetrics(
            avg_fps=92.0,
            one_percent_low_fps=74.0,
            resolution="1440p",
            raw_lines=("AVG", "92", "1% LOW", "74"),
        ),
    )

    assert "1440p" in observation
    assert "AVG FPS 92" in observation
    assert "1% LOW FPS 74" in observation
