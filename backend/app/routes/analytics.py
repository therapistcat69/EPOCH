from datetime import date

from fastapi import APIRouter, Depends, Query

from app.deps import CreatorContext, creator_context
from app.errors import AppError
from app.repositories import video_repository
from app.routes.me_channel import to_owned_video
from app.schemas.analytics import (
    BreakdownResponse,
    Metrics,
    OverviewResponse,
    TimeseriesResponse,
    VideoDetailResponse,
    VideoRow,
    VideosResponse,
)
from app.schemas.ml import MLVideoFeatures, RetentionFeatures
from app.schemas.retention import RetentionResponse
from app.services import youtube_analytics_service as svc
from app.utils.youtube import is_valid_video_id

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

SortKey = "^(newest|oldest|views|highest_avp|lowest_avp|longest|shortest)$"


def _service(ctx: CreatorContext) -> svc.AnalyticsService:
    return svc.AnalyticsService(ctx.session, ctx.user.id, ctx.channel.youtube_channel_id, ctx.access_token)


async def _owned_video(ctx: CreatorContext, video_id: str):
    if not is_valid_video_id(video_id):
        raise AppError("INVALID_URL", "The video ID is malformed.", 400)
    v = await video_repository.get_video_by_yt_id(ctx.session, ctx.channel.youtube_channel_id, video_id)
    if v is None:
        raise AppError("VIDEO_NOT_FOUND", "That video isn't in your synced library. Try syncing first.", 404)
    return v


@router.get("/overview", response_model=OverviewResponse)
async def overview(
    start_date: date | None = None, end_date: date | None = None, refresh: bool = False,
    ctx: CreatorContext = Depends(creator_context),
):
    start, end = svc.validate_range(start_date, end_date)
    metrics, cached, at = await _service(ctx).overview(start, end, refresh)
    return OverviewResponse(start_date=start, end_date=end, metrics=metrics, cached=cached, fetched_at=at)


@router.get("/timeseries", response_model=TimeseriesResponse)
async def timeseries(
    start_date: date | None = None, end_date: date | None = None, refresh: bool = False,
    ctx: CreatorContext = Depends(creator_context),
):
    start, end = svc.validate_range(start_date, end_date)
    points, cached, at = await _service(ctx).timeseries(start, end, refresh)
    return TimeseriesResponse(start_date=start, end_date=end, points=points, cached=cached, fetched_at=at)


def _sort_rows(rows: list[VideoRow], sort: str) -> list[VideoRow]:
    def metric(attr):
        return lambda r: getattr(r.metrics, attr) if r.metrics and getattr(r.metrics, attr) is not None else None

    def by(key, reverse):  # rows with no data always sort last
        have = [r for r in rows if key(r) is not None]
        none = [r for r in rows if key(r) is None]
        return sorted(have, key=key, reverse=reverse) + none

    def ts(r):
        return r.video.published_at.timestamp() if r.video.published_at else None

    return {
        "newest": lambda: by(ts, True),
        "oldest": lambda: by(ts, False),
        "views": lambda: by(metric("views"), True),
        "highest_avp": lambda: by(metric("average_view_percentage"), True),
        "lowest_avp": lambda: by(metric("average_view_percentage"), False),
        "longest": lambda: by(lambda r: r.video.duration_seconds, True),
        "shortest": lambda: by(lambda r: r.video.duration_seconds, False),
    }[sort]()


@router.get("/videos", response_model=VideosResponse)
async def videos(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort: str = Query("newest", pattern=SortKey),
    search: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    refresh: bool = False,
    ctx: CreatorContext = Depends(creator_context),
):
    """Library merged with ONE batched Analytics report (top 200 videos by views in range)."""
    start, end = svc.validate_range(start_date, end_date)
    metrics_by_id, cached, at = await _service(ctx).videos(start, end, refresh)
    owned = await video_repository.list_channel_videos(ctx.session, ctx.channel.youtube_channel_id, search)
    rows = [VideoRow(video=to_owned_video(v), metrics=metrics_by_id.get(v.youtube_video_id)) for v in owned]
    rows = _sort_rows(rows, sort)
    insights = svc.compute_insights([r.metrics for r in rows if r.metrics])
    s = (page - 1) * limit
    return VideosResponse(
        start_date=start, end_date=end, cached=cached, fetched_at=at, items=rows[s : s + limit],
        total=len(rows), page=page, limit=limit, insights=insights,
    )


@router.get("/video/{video_id}", response_model=VideoDetailResponse)
async def video_detail(
    video_id: str, start_date: date | None = None, end_date: date | None = None, refresh: bool = False,
    ctx: CreatorContext = Depends(creator_context),
):
    v = await _owned_video(ctx, video_id)
    start, end = svc.validate_range(start_date, end_date)
    metrics, cached, at = await _service(ctx).video_detail(video_id, start, end, refresh)
    return VideoDetailResponse(start_date=start, end_date=end, video=to_owned_video(v), metrics=metrics, cached=cached, fetched_at=at)


async def _retention(ctx: CreatorContext, video_id: str, start_date, end_date, refresh: bool):
    v = await _owned_video(ctx, video_id)
    end = end_date or date.today()
    start = start_date or (v.published_at.date() if v.published_at else date(2005, 2, 14))
    start, end = svc.validate_range(start, end)
    points, cached, at = await _service(ctx).retention(video_id, start, end, refresh)
    if not points:
        raise AppError(
            "ANALYTICS_UNAVAILABLE",
            "YouTube has no audience retention data for this video yet (it may be too new or have too few views).",
            404,
        )
    return v, start, end, points, cached, at


@router.get("/video/{video_id}/retention", response_model=RetentionResponse)
async def retention(
    video_id: str, start_date: date | None = None, end_date: date | None = None, refresh: bool = False,
    ctx: CreatorContext = Depends(creator_context),
):
    v, start, end, points, cached, at = await _retention(ctx, video_id, start_date, end_date, refresh)
    return RetentionResponse(
        start_date=start, end_date=end, cached=cached, fetched_at=at, video_id=video_id,
        duration_seconds=v.duration_seconds, points=points,
        observed_drop_offs=svc.observed_drop_offs(points, v.duration_seconds),
        has_started_stopped=any(p.started_watching is not None for p in points),
    )


@router.get("/video/{video_id}/ml-features", response_model=MLVideoFeatures)
async def ml_features(video_id: str, ctx: CreatorContext = Depends(creator_context)):
    """The versioned feature contract for the ML team (no credentials, nothing fabricated)."""
    v = await _owned_video(ctx, video_id)
    start, end = svc.validate_range(v.published_at.date() if v.published_at else None, None)
    service = _service(ctx)
    metrics, _, _ = await service.video_detail(video_id, start, end)
    try:
        points, _, _ = await service.retention(video_id, start, end)
    except AppError:
        points = []
    pct = metrics.average_view_percentage
    return MLVideoFeatures(
        video_id=video_id, title=v.title, category=v.category_name, duration_seconds=v.duration_seconds,
        views=metrics.views, likes=metrics.likes, comments=metrics.comments,
        average_view_duration=metrics.average_view_duration_seconds,
        average_view_percentage=pct / 100 if pct is not None else None,
        retention=RetentionFeatures(
            time_ratio=[p.time_ratio for p in points],
            audience_watch_ratio=[p.audience_watch_ratio for p in points],
            relative_retention_performance=[p.relative_retention_performance for p in points],
        ),
        analytics_features=metrics.model_dump(exclude_none=True),
    )


def _breakdown(report_type: str, dimension: str):
    async def handler(
        start_date: date | None = None, end_date: date | None = None, video_id: str | None = None,
        refresh: bool = False, ctx: CreatorContext = Depends(creator_context),
    ):
        if video_id:
            await _owned_video(ctx, video_id)
        start, end = svc.validate_range(start_date, end_date)
        rows, cached, at = await _service(ctx).breakdown(report_type, dimension, start, end, video_id, refresh)
        return BreakdownResponse(start_date=start, end_date=end, dimension=dimension, rows=rows, cached=cached, fetched_at=at)

    return handler


for _path, _type, _dim in [
    ("/traffic-sources", "traffic_sources", "insightTrafficSourceType"),
    ("/geography", "geography", "country"),
    ("/devices", "devices", "deviceType"),
]:
    router.add_api_route(_path, _breakdown(_type, _dim), methods=["GET"], response_model=BreakdownResponse)
