from app.services.youtube_review_consensus import (
    MatchReviewedGame,
    YoutubeReviewConsensusService,
)
from app.services.youtube_video_sources import YoutubeSearchResult, YoutubeVideoChapter, YoutubeVideoDetail


class FakeSearchProvider:
    def search(self, query: str) -> list[YoutubeSearchResult]:
        assert "Ryzen 5 7600" in query
        assert "RTX 4070 Super" in query
        return [
            YoutubeSearchResult(
                title="RTX 4070 Super + Ryzen 5 7600 A Good Pair? 1440p Benchmark",
                url="https://www.youtube.com/watch?v=video1",
                channel="Channel A",
                snippet="Great combo for 1440p with DLSS in recent games.",
                duration_seconds=751,
            ),
            YoutubeSearchResult(
                title="Ryzen 5 7600 with RTX 4070 Super review and test in 1440p",
                url="https://www.youtube.com/watch?v=video2",
                channel="Channel B",
                snippet="Balanced setup and good pair for modern titles.",
                duration_seconds=602,
            ),
            YoutubeSearchResult(
                title="RTX 4070 Super + Ryzen 5 7600 benchmark 1080p 1440p 4K",
                url="https://www.youtube.com/watch?v=video3",
                channel="Channel C",
                snippet="DLSS and ray tracing tested across multiple resolutions.",
                duration_seconds=945,
            ),
        ]


class FakeVideoDetailProvider:
    def fetch(self, *, url: str, fallback_title: str, fallback_channel: str | None) -> YoutubeVideoDetail:
        video_id = url.split("=")[-1]
        details = {
            "video1": YoutubeVideoDetail(
                title=fallback_title,
                url=url,
                channel=fallback_channel,
                description="Good pair for 1440p gaming with DLSS enabled.",
                transcript="Cyberpunk 2077 1440p Avg FPS 90. Alan Wake 2 1440p Avg FPS 80.",
                chapters=(
                    YoutubeVideoChapter(title="Cyberpunk 2077 | 1440p", start_time=0.0, end_time=30.0),
                    YoutubeVideoChapter(title="Alan Wake 2 | 1440p", start_time=30.0, end_time=60.0),
                ),
            ),
            "video2": YoutubeVideoDetail(
                title=fallback_title,
                url=url,
                channel=fallback_channel,
                description="Balanced setup and good pair for modern titles.",
                transcript="Cyberpunk 2077 1440p Avg FPS 100. Black Myth: Wukong 1440p Avg FPS 75.",
                chapters=(
                    YoutubeVideoChapter(title="Cyberpunk 2077 | 1440p", start_time=0.0, end_time=30.0),
                    YoutubeVideoChapter(title="Black Myth: Wukong | 1440p", start_time=30.0, end_time=60.0),
                ),
            ),
            "video3": YoutubeVideoDetail(
                title=fallback_title,
                url=url,
                channel=fallback_channel,
                description="Cyberpunk 2077 | Alan Wake 2 | Black Myth: Wukong",
                transcript="",
                chapters=(
                    YoutubeVideoChapter(title="Cyberpunk 2077 | 1080p", start_time=0.0, end_time=30.0),
                    YoutubeVideoChapter(title="Cyberpunk 2077 | 1440p", start_time=30.0, end_time=60.0),
                    YoutubeVideoChapter(title="Black Myth: Wukong | 1440p", start_time=60.0, end_time=90.0),
                ),
            ),
        }
        return details[video_id]


class FakeOcrProvider:
    def analyze(self, detail: YoutubeVideoDetail) -> tuple[str, ...]:
        return ()


class FpsOnlyOcrProvider:
    def analyze(self, detail: YoutubeVideoDetail) -> tuple[str, ...]:
        return (
            "Cyberpunk 2077 1440p AVG FPS 92",
            "Alan Wake 2 1440p AVG FPS 74",
        )


def test_build_match_consensus_requires_relevant_pair_specific_videos() -> None:
    service = YoutubeReviewConsensusService(
        search_provider=FakeSearchProvider(),
        video_detail_provider=FakeVideoDetailProvider(),
        ocr_provider=FakeOcrProvider(),
    )

    result = service.build_match_consensus(
        cpu_name="AMD Ryzen 5 7600",
        gpu_name="GeForce RTX 4070 Super",
    )

    assert result is not None
    assert result.source_count == 3
    assert result.confidence == "medium"
    assert "1440p" in result.insight
    assert result.average_explicit_fps == 86.2
    assert result.tested_games == (
        MatchReviewedGame(name="Cyberpunk 2077", resolution="1440p", avg_fps=95.0),
        MatchReviewedGame(name="Black Myth: Wukong", resolution="1440p", avg_fps=75.0),
        MatchReviewedGame(name="Alan Wake 2", resolution="1440p", avg_fps=80.0),
    )
    assert {reference.url for reference in result.references} == {
        "https://www.youtube.com/watch?v=video1",
        "https://www.youtube.com/watch?v=video2",
        "https://www.youtube.com/watch?v=video3",
    }


def test_build_match_consensus_returns_none_when_evidence_is_insufficient() -> None:
    class WeakSearchProvider:
        def search(self, query: str) -> list[YoutubeSearchResult]:
            return [
                YoutubeSearchResult(
                    title="RTX 4070 Super review",
                    url="https://www.youtube.com/watch?v=video1",
                    channel="Channel A",
                    snippet="GPU only review.",
                    duration_seconds=751,
                )
            ]

    service = YoutubeReviewConsensusService(
        search_provider=WeakSearchProvider(),
        video_detail_provider=FakeVideoDetailProvider(),
        ocr_provider=FakeOcrProvider(),
    )

    result = service.build_match_consensus(
        cpu_name="AMD Ryzen 5 7600",
        gpu_name="GeForce RTX 4070 Super",
    )

    assert result is None


def test_build_match_consensus_can_use_ocr_observations_for_fps() -> None:
    class SearchProvider:
        def search(self, query: str) -> list[YoutubeSearchResult]:
            return [
                YoutubeSearchResult(
                    title="RTX 4070 Super + Ryzen 5 7600 benchmark 1440p",
                    url="https://www.youtube.com/watch?v=video1",
                    channel="Channel A",
                    snippet="Benchmark test.",
                    duration_seconds=700,
                ),
                YoutubeSearchResult(
                    title="Ryzen 5 7600 with RTX 4070 Super test 1440p",
                    url="https://www.youtube.com/watch?v=video2",
                    channel="Channel B",
                    snippet="Modern games test.",
                    duration_seconds=680,
                ),
            ]

    class SparseDetailProvider:
        def fetch(self, *, url: str, fallback_title: str, fallback_channel: str | None) -> YoutubeVideoDetail:
            return YoutubeVideoDetail(
                title=fallback_title,
                url=url,
                channel=fallback_channel,
                description="",
                transcript="",
                chapters=(
                    YoutubeVideoChapter(title="Cyberpunk 2077 | 1440p", start_time=0.0, end_time=30.0),
                    YoutubeVideoChapter(title="Alan Wake 2 | 1440p", start_time=30.0, end_time=60.0),
                ),
            )

    service = YoutubeReviewConsensusService(
        search_provider=SearchProvider(),
        video_detail_provider=SparseDetailProvider(),
        ocr_provider=FpsOnlyOcrProvider(),
    )

    result = service.build_match_consensus(
        cpu_name="AMD Ryzen 5 7600",
        gpu_name="GeForce RTX 4070 Super",
    )

    assert result is not None
    assert result.average_explicit_fps == 83.0
    assert MatchReviewedGame(
        name="Cyberpunk 2077",
        resolution="1440p",
        avg_fps=92.0,
    ) in result.tested_games
    assert MatchReviewedGame(
        name="Alan Wake 2",
        resolution="1440p",
        avg_fps=74.0,
    ) in result.tested_games


def test_build_match_consensus_accepts_partial_structured_evidence() -> None:
    class SearchProvider:
        def search(self, query: str) -> list[YoutubeSearchResult]:
            return [
                YoutubeSearchResult(
                    title="RTX 4070 Super + Ryzen 5 7600 benchmark 1440p",
                    url="https://www.youtube.com/watch?v=video1",
                    channel="Channel A",
                    snippet="Benchmark test.",
                    duration_seconds=700,
                ),
            ]

    class SparseDetailProvider:
        def fetch(self, *, url: str, fallback_title: str, fallback_channel: str | None) -> YoutubeVideoDetail:
            return YoutubeVideoDetail(
                title=fallback_title,
                url=url,
                channel=fallback_channel,
                description="Balanced setup in modern titles.",
                transcript="",
                chapters=(
                    YoutubeVideoChapter(title="Cyberpunk 2077 | 1440p", start_time=0.0, end_time=30.0),
                ),
            )

    attempt = YoutubeReviewConsensusService(
        search_provider=SearchProvider(),
        video_detail_provider=SparseDetailProvider(),
        ocr_provider=FpsOnlyOcrProvider(),
    ).build_match_consensus_attempt(
        cpu_name="AMD Ryzen 5 7600",
        gpu_name="GeForce RTX 4070 Super",
    )

    assert attempt.status == "ready"
    assert attempt.reason == "partial_evidence"
    assert attempt.review_consensus is not None
    assert attempt.review_consensus.confidence == "low"
    assert attempt.review_consensus.average_explicit_fps == 83.0


def test_build_match_consensus_supports_split_ocr_and_missing_avg_keyword() -> None:
    class SearchProvider:
        def search(self, query: str) -> list[YoutubeSearchResult]:
            return [
                YoutubeSearchResult(
                    title="RTX 4070 Super + Ryzen 5 7600 test",
                    url="https://www.youtube.com/watch?v=video1",
                    channel="Channel A",
                    snippet="Test.",
                    duration_seconds=700,
                ),
            ]

    class SparseDetailProvider:
        def fetch(self, *, url: str, fallback_title: str, fallback_channel: str | None) -> YoutubeVideoDetail:
            return YoutubeVideoDetail(
                title=fallback_title,
                url=url,
                channel=fallback_channel,
                description="",
                transcript="",
                chapters=(
                    YoutubeVideoChapter(title="Cyberpunk 2077 | 1440p", start_time=0.0, end_time=30.0),
                ),
            )

    class SplitOcrProvider:
        def analyze(self, detail: YoutubeVideoDetail) -> tuple[str, ...]:
            return (
                "Cyberpunk 2077\n1440p\n65 FPS",
            )

    service = YoutubeReviewConsensusService(
        search_provider=SearchProvider(),
        video_detail_provider=SparseDetailProvider(),
        ocr_provider=SplitOcrProvider(),
    )

    result = service.build_match_consensus(
        cpu_name="AMD Ryzen 5 7600",
        gpu_name="GeForce RTX 4070 Super",
    )

    assert result is not None
    assert result.average_explicit_fps == 65.0
    assert MatchReviewedGame(
        name="Cyberpunk 2077",
        resolution="1440p",
        avg_fps=65.0,
    ) in result.tested_games
