from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.video import OwnedVideo


class Envelope(BaseModel):
    start_date: date
    end_date: date
    cached: bool = False
    fetched_at: datetime | None = None


class Metrics(BaseModel):
    """Units: watch time in MINUTES, average_view_duration in SECONDS,
    average_view_percentage as a PERCENT (0-100), exactly as YouTube returns them."""

    views: int | None = None
    engaged_views: int | None = None
    watch_time_minutes: float | None = None
    average_view_duration_seconds: float | None = None
    average_view_percentage: float | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    subscribers_gained: int | None = None
    subscribers_lost: int | None = None
    net_subscribers: int | None = None  # gained - lost (computed)


class OverviewResponse(Envelope):
    metrics: Metrics


class TimeseriesPoint(BaseModel):
    date: str
    views: int | None = None
    watch_time_minutes: float | None = None
    subscribers_gained: int | None = None
    subscribers_lost: int | None = None
    net_subscribers: int | None = None


class TimeseriesResponse(Envelope):
    points: list[TimeseriesPoint]


class VideoRow(BaseModel):
    video: OwnedVideo
    metrics: Metrics | None = None  # None = YouTube returned no analytics row for this range


class Insights(BaseModel):
    """Descriptive statistics only (no ML)."""

    videos_analyzed: int
    average_view_percentage: float | None = None
    median_view_percentage: float | None = None
    average_view_duration_seconds: float | None = None
    median_view_duration_seconds: float | None = None
    average_views_per_video: float | None = None


class VideosResponse(Envelope):
    items: list[VideoRow]
    total: int
    page: int
    limit: int
    insights: Insights


class VideoDetailResponse(Envelope):
    video: OwnedVideo
    metrics: Metrics


class BreakdownRow(BaseModel):
    key: str
    views: int | None = None
    watch_time_minutes: float | None = None
    average_view_duration_seconds: float | None = None
    average_view_percentage: float | None = None


class BreakdownResponse(Envelope):
    dimension: str
    rows: list[BreakdownRow]
