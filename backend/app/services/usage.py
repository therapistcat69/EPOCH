"""Application-side API call counters (NOT Google's exact quota figures). Reset on server restart."""
from collections import Counter
from datetime import datetime, timezone

COUNTERS: Counter[str] = Counter()
_started = datetime.now(timezone.utc)

NAMES = (
    "youtube_search_calls",
    "youtube_video_calls",
    "youtube_other_calls",
    "analytics_calls",
    "groq_transcription_calls",
    "groq_report_calls",
)


def track(name: str, n: int = 1) -> None:
    COUNTERS[name] += n


def snapshot() -> dict:
    return {
        "counters": {n: COUNTERS.get(n, 0) for n in NAMES},
        "since": _started.isoformat(),
        "note": "Application-side counters since the server started; not Google Cloud's exact quota. "
        "search.list costs ~100 quota units per call, videos.list ~1.",
    }
