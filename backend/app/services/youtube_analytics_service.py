"""YouTube Analytics API (interactive reports). OAuth-only; results cached in PostgreSQL."""
import statistics
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.errors import AppError
from app.repositories import analytics_repository as cache_repo
from app.schemas.analytics import BreakdownRow, Insights, Metrics, TimeseriesPoint
from app.schemas.retention import ObservedDropOff, RetentionPoint
from app.services.youtube_client import google_request

METRIC_FIELDS = {
    "views": "views",
    "engagedViews": "engaged_views",
    "estimatedMinutesWatched": "watch_time_minutes",
    "averageViewDuration": "average_view_duration_seconds",
    "averageViewPercentage": "average_view_percentage",
    "likes": "likes",
    "comments": "comments",
    "shares": "shares",
    "subscribersGained": "subscribers_gained",
    "subscribersLost": "subscribers_lost",
}
INT_FIELDS = {"views", "engaged_views", "likes", "comments", "shares", "subscribers_gained", "subscribers_lost"}

OVERVIEW_METRICS = [
    "views", "engagedViews", "estimatedMinutesWatched", "averageViewDuration", "averageViewPercentage",
    "likes", "comments", "shares", "subscribersGained", "subscribersLost",
]
VIDEO_METRICS = [
    "views", "estimatedMinutesWatched", "averageViewDuration", "averageViewPercentage",
    "likes", "comments", "subscribersGained",
]
VIDEO_DETAIL_METRICS = VIDEO_METRICS + ["shares", "subscribersLost"]
TIMESERIES_METRICS = ["views", "estimatedMinutesWatched", "subscribersGained", "subscribersLost"]
RETENTION_FULL = ["audienceWatchRatio", "relativeRetentionPerformance", "startedWatching", "stoppedWatching"]
RETENTION_BASE = ["audienceWatchRatio", "relativeRetentionPerformance"]
BREAKDOWN_CHAIN = [
    ["views", "estimatedMinutesWatched", "averageViewDuration", "averageViewPercentage"],
    ["views", "estimatedMinutesWatched", "averageViewDuration"],
    ["views", "estimatedMinutesWatched"],
]
MAX_RANGE_DAYS = 3650


# ---------- pure helpers (unit-tested) ---------------------------------------
def validate_range(start: date | None, end: date | None, default_days: int = 28) -> tuple[date, date]:
    end = end or date.today()
    start = start or end - timedelta(days=default_days - 1)
    if start > end:
        raise AppError("INVALID_DATE_RANGE", "The start date must be on or before the end date.", 400)
    if end > date.today() + timedelta(days=1):
        raise AppError("INVALID_DATE_RANGE", "The end date can't be in the future.", 400)
    if (end - start).days > MAX_RANGE_DAYS:
        raise AppError("INVALID_DATE_RANGE", "That date range is too long.", 400)
    return start, end


def parse_rows(response: dict) -> list[dict[str, Any]]:
    """Analytics returns {columnHeaders:[{name}], rows:[[...]]}; turn it into a list of dicts."""
    names = [h["name"] for h in response.get("columnHeaders", [])]
    return [dict(zip(names, row)) for row in response.get("rows", []) or []]


def to_metrics(row: dict[str, Any] | None) -> Metrics:
    m: dict[str, Any] = {}
    for api_name, field in METRIC_FIELDS.items():
        if row and row.get(api_name) is not None:
            v = row[api_name]
            m[field] = int(round(v)) if field in INT_FIELDS else float(v)
    g, l = m.get("subscribers_gained"), m.get("subscribers_lost")
    if g is not None and l is not None:
        m["net_subscribers"] = g - l
    return Metrics(**m)


def to_timeseries(rows: list[dict]) -> list[TimeseriesPoint]:
    pts = []
    for r in rows:
        g, l = r.get("subscribersGained"), r.get("subscribersLost")
        pts.append(
            TimeseriesPoint(
                date=str(r["day"]),
                views=_i(r.get("views")),
                watch_time_minutes=_f(r.get("estimatedMinutesWatched")),
                subscribers_gained=_i(g),
                subscribers_lost=_i(l),
                net_subscribers=(int(g) - int(l)) if g is not None and l is not None else None,
            )
        )
    return pts


def to_breakdown(rows: list[dict], dimension: str) -> list[BreakdownRow]:
    return [
        BreakdownRow(
            key=str(r[dimension]),
            views=_i(r.get("views")),
            watch_time_minutes=_f(r.get("estimatedMinutesWatched")),
            average_view_duration_seconds=_f(r.get("averageViewDuration")),
            average_view_percentage=_f(r.get("averageViewPercentage")),
        )
        for r in rows
    ]


def to_retention(rows: list[dict]) -> list[RetentionPoint]:
    """Raw points only: no smoothing or interpolation."""
    pts = [
        RetentionPoint(
            time_ratio=float(r["elapsedVideoTimeRatio"]),
            audience_watch_ratio=_f(r.get("audienceWatchRatio")),
            relative_retention_performance=_f(r.get("relativeRetentionPerformance")),
            started_watching=_f(r.get("startedWatching")),
            stopped_watching=_f(r.get("stoppedWatching")),
        )
        for r in rows
    ]
    return sorted(pts, key=lambda p: p.time_ratio)


def observed_drop_offs(
    points: list[RetentionPoint], duration_seconds: int | None, top: int = 3
) -> list[ObservedDropOff]:
    """Largest consecutive declines in audienceWatchRatio. Observed behaviour, not a prediction."""
    drops: list[ObservedDropOff] = []
    for a, b in zip(points, points[1:]):
        if a.audience_watch_ratio is None or b.audience_watch_ratio is None:
            continue
        d = a.audience_watch_ratio - b.audience_watch_ratio
        if d > 0:
            drops.append(
                ObservedDropOff(
                    from_ratio=a.time_ratio,
                    to_ratio=b.time_ratio,
                    from_seconds=a.time_ratio * duration_seconds if duration_seconds else None,
                    to_seconds=b.time_ratio * duration_seconds if duration_seconds else None,
                    drop=round(d, 6),
                )
            )
    return sorted(drops, key=lambda x: x.drop, reverse=True)[:top]


def compute_insights(metrics_list: list[Metrics]) -> Insights:
    def vals(attr: str) -> list[float]:
        return [getattr(m, attr) for m in metrics_list if getattr(m, attr) is not None]

    pct, dur, views = vals("average_view_percentage"), vals("average_view_duration_seconds"), vals("views")
    return Insights(
        videos_analyzed=len(metrics_list),
        average_view_percentage=statistics.fmean(pct) if pct else None,
        median_view_percentage=statistics.median(pct) if pct else None,
        average_view_duration_seconds=statistics.fmean(dur) if dur else None,
        median_view_duration_seconds=statistics.median(dur) if dur else None,
        average_views_per_video=statistics.fmean(views) if views else None,
    )


def _i(v: Any) -> int | None:
    return None if v is None else int(round(v))


def _f(v: Any) -> float | None:
    return None if v is None else float(v)


# ---------- service ------------------------------------------------------------
class AnalyticsService:
    def __init__(self, session: AsyncSession, user_id: uuid.UUID, channel_id: str, access_token: str):
        self.session, self.user_id, self.channel_id, self.token = session, user_id, channel_id, access_token
        self.settings = get_settings()

    async def _raw(self, params: dict) -> list[dict]:
        resp = await google_request(
            "GET",
            f"{self.settings.analytics_api_base}/reports",
            params={"ids": "channel==MINE", **params},
            access_token=self.token,
            context="analytics",
        )
        return parse_rows(resp)

    async def query(
        self,
        report_type: str,
        start: date,
        end: date,
        metric_sets: list[list[str]],
        *,
        dimensions: str | None = None,
        filters: str | None = None,
        sort: str | None = None,
        max_results: int | None = None,
        video_id: str | None = None,
        refresh: bool = False,
    ) -> tuple[list[dict], bool, datetime]:
        """Cached query. Tries each metric set in order (some metrics aren't supported by every report)."""
        key = cache_repo.make_cache_key(self.user_id, report_type, video_id, start, end, f"{dimensions}|{filters}")
        if not refresh:
            hit = await cache_repo.get_cached(self.session, key, self.settings.analytics_cache_minutes)
            if hit is not None:
                fetched = hit.fetched_at if hit.fetched_at.tzinfo else hit.fetched_at.replace(tzinfo=timezone.utc)
                return list(hit.metrics or []), True, fetched

        rows: list[dict] | None = None
        last_err: AppError | None = None
        for metrics in metric_sets:
            params: dict[str, Any] = {"startDate": start.isoformat(), "endDate": end.isoformat(), "metrics": ",".join(metrics)}
            for k, v in (("dimensions", dimensions), ("filters", filters), ("sort", sort), ("maxResults", max_results)):
                if v is not None:
                    params[k] = v
            try:
                rows = await self._raw(params)
                break
            except AppError as exc:
                if exc.code != "ANALYTICS_UNAVAILABLE":
                    raise
                last_err = exc
        if rows is None:
            raise last_err or AppError("ANALYTICS_UNAVAILABLE", "Analytics unavailable for this report.", 400)

        await cache_repo.put_cached(
            self.session, key, user_id=self.user_id, channel_id=self.channel_id, video_id=video_id,
            report_type=report_type, start=start, end=end, metrics=rows,
        )
        await self.session.commit()
        return rows, False, datetime.now(timezone.utc)

    # -- reports ---------------------------------------------------------------
    async def overview(self, start: date, end: date, refresh: bool = False):
        # engagedViews isn't available everywhere, so fall back to the base set
        sets = [OVERVIEW_METRICS, [m for m in OVERVIEW_METRICS if m != "engagedViews"]]
        rows, cached, at = await self.query("overview", start, end, sets, refresh=refresh)
        return to_metrics(rows[0] if rows else None), cached, at

    async def timeseries(self, start: date, end: date, refresh: bool = False):
        rows, cached, at = await self.query(
            "timeseries", start, end, [TIMESERIES_METRICS], dimensions="day", sort="day", refresh=refresh
        )
        return to_timeseries(rows), cached, at

    async def videos(self, start: date, end: date, refresh: bool = False) -> tuple[dict[str, Metrics], bool, datetime]:
        """One batched report for all videos (top 200 by views in range), not one request per video."""
        rows, cached, at = await self.query(
            "videos", start, end, [VIDEO_METRICS], dimensions="video", sort="-views", max_results=200, refresh=refresh
        )
        return {str(r["video"]): to_metrics(r) for r in rows}, cached, at

    async def video_detail(self, video_id: str, start: date, end: date, refresh: bool = False):
        rows, cached, at = await self.query(
            "video_detail", start, end, [VIDEO_DETAIL_METRICS, VIDEO_METRICS],
            filters=f"video=={video_id}", video_id=video_id, refresh=refresh,
        )
        return to_metrics(rows[0] if rows else None), cached, at

    async def retention(self, video_id: str, start: date, end: date, refresh: bool = False):
        # Retention requires exactly one video ID, so it's only ever requested per selected video.
        rows, cached, at = await self.query(
            "retention", start, end, [RETENTION_FULL, RETENTION_BASE],
            dimensions="elapsedVideoTimeRatio", filters=f"video=={video_id}", sort="elapsedVideoTimeRatio",
            video_id=video_id, refresh=refresh,
        )
        return to_retention(rows), cached, at

    async def breakdown(self, report_type: str, dimension: str, start: date, end: date,
                        video_id: str | None = None, refresh: bool = False):
        rows, cached, at = await self.query(
            report_type, start, end, BREAKDOWN_CHAIN, dimensions=dimension,
            filters=f"video=={video_id}" if video_id else None, sort="-views", max_results=25,
            video_id=video_id, refresh=refresh,
        )
        return to_breakdown(rows, dimension), cached, at
