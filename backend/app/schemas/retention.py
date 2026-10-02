from pydantic import BaseModel

from app.schemas.analytics import Envelope


class RetentionPoint(BaseModel):
    time_ratio: float
    audience_watch_ratio: float | None = None
    relative_retention_performance: float | None = None
    started_watching: float | None = None
    stopped_watching: float | None = None


class ObservedDropOff(BaseModel):
    """An OBSERVED decline between two consecutive raw points. Not a prediction."""

    from_ratio: float
    to_ratio: float
    from_seconds: float | None = None
    to_seconds: float | None = None
    drop: float  # decrease in audience_watch_ratio (absolute, 0-1 scale)


class RetentionResponse(Envelope):
    video_id: str
    duration_seconds: int | None = None
    points: list[RetentionPoint]  # raw YouTube values, unsmoothed
    observed_drop_offs: list[ObservedDropOff]
    has_started_stopped: bool = False
    source: str = "youtube_analytics_api"
