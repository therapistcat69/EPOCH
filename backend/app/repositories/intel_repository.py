import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ChannelReport,
    ContentFeature,
    GenreBenchmark,
    TranscriptSegment,
    TrendSearchCache,
    TrendTopic,
    VideoReport,
    VideoRetentionPoint,
    VideoTranscript,
)
from app.schemas.transcript import SegmentIn, TranscriptData


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------- transcripts
async def save_transcript(session: AsyncSession, video_row_id: uuid.UUID, data: TranscriptData) -> VideoTranscript:
    """Replace any existing transcript for the video (idempotent)."""
    for old in (await session.execute(select(VideoTranscript).where(VideoTranscript.video_id == video_row_id))).scalars():
        await session.delete(old)
    await session.flush()
    status = "ready_estimated_timestamps" if data.timestamps_estimated else "ready"
    tr = VideoTranscript(
        video_id=video_row_id, language=data.language, provider=data.provider, full_text=data.full_text,
        duration_seconds=data.duration_seconds, status=status,
    )
    session.add(tr)
    await session.flush()
    for s in data.segments:
        session.add(TranscriptSegment(
            transcript_id=tr.id, segment_index=s.segment_index, start_seconds=s.start_seconds,
            end_seconds=s.end_seconds, text=s.text, language=s.language or data.language,
        ))
    await session.flush()
    await delete_video_report(session, video_row_id)  # transcript changed -> stored report is stale
    return tr


async def get_transcript(session: AsyncSession, video_row_id: uuid.UUID) -> tuple[VideoTranscript, list[SegmentIn]] | None:
    tr = (
        await session.execute(
            select(VideoTranscript).where(VideoTranscript.video_id == video_row_id).order_by(VideoTranscript.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if tr is None:
        return None
    rows = (
        await session.execute(
            select(TranscriptSegment).where(TranscriptSegment.transcript_id == tr.id).order_by(TranscriptSegment.segment_index)
        )
    ).scalars()
    return tr, [
        SegmentIn(segment_index=r.segment_index, start_seconds=r.start_seconds, end_seconds=r.end_seconds, text=r.text, language=r.language)
        for r in rows
    ]


# ---------------------------------------------------------------- content features
async def upsert_content_features(session: AsyncSession, video_row_id: uuid.UUID, **fields) -> ContentFeature:
    row = (await session.execute(select(ContentFeature).where(ContentFeature.video_id == video_row_id))).scalar_one_or_none()
    if row is None:
        row = ContentFeature(video_id=video_row_id)
        session.add(row)
    for k, v in fields.items():
        setattr(row, k, v)
    await session.flush()
    return row


async def get_content_features(session: AsyncSession, video_row_ids: list[uuid.UUID]) -> dict[uuid.UUID, ContentFeature]:
    if not video_row_ids:
        return {}
    rows = (await session.execute(select(ContentFeature).where(ContentFeature.video_id.in_(video_row_ids)))).scalars()
    return {r.video_id: r for r in rows}


# ---------------------------------------------------------------- retention points
async def replace_retention_points(session: AsyncSession, video_row_id: uuid.UUID, duration: int | None, points: list) -> None:
    await session.execute(delete(VideoRetentionPoint).where(VideoRetentionPoint.video_id == video_row_id))
    for p in points:
        session.add(VideoRetentionPoint(
            video_id=video_row_id, time_ratio=p.time_ratio,
            absolute_time_seconds=round(p.time_ratio * duration, 3) if duration else None,
            audience_watch_ratio=p.audience_watch_ratio, relative_retention_performance=p.relative_retention_performance,
            started_watching=p.started_watching, stopped_watching=p.stopped_watching,
        ))
    await session.flush()


# ---------------------------------------------------------------- reports
async def get_video_report(session: AsyncSession, video_row_id: uuid.UUID) -> VideoReport | None:
    return (await session.execute(select(VideoReport).where(VideoReport.video_id == video_row_id))).scalar_one_or_none()


async def save_video_report(session: AsyncSession, video_row_id: uuid.UUID, report: dict) -> VideoReport:
    row = await get_video_report(session, video_row_id)
    if row is None:
        row = VideoReport(video_id=video_row_id, structured_report_json=report)
        session.add(row)
    row.structured_report_json = report
    row.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return row


async def delete_video_report(session: AsyncSession, video_row_id: uuid.UUID) -> None:
    await session.execute(delete(VideoReport).where(VideoReport.video_id == video_row_id))


async def get_channel_report(session: AsyncSession, user_id: uuid.UUID, channel_id: str, start: str, end: str) -> ChannelReport | None:
    return (
        await session.execute(
            select(ChannelReport).where(
                ChannelReport.user_id == user_id, ChannelReport.channel_id == channel_id,
                ChannelReport.date_start == start, ChannelReport.date_end == end,
            )
        )
    ).scalar_one_or_none()


async def save_channel_report(session: AsyncSession, user_id: uuid.UUID, channel_id: str, start: str, end: str, report: dict) -> ChannelReport:
    row = await get_channel_report(session, user_id, channel_id, start, end)
    if row is None:
        row = ChannelReport(user_id=user_id, channel_id=channel_id, date_start=start, date_end=end, structured_report_json=report)
        session.add(row)
    row.structured_report_json = report
    row.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return row


# ---------------------------------------------------------------- trends
async def get_trend_query(session: AsyncSession, genre: str, subgenre: str | None, language: str | None, region: str | None, window: str, query: str) -> TrendSearchCache | None:
    rows = (
        await session.execute(
            select(TrendSearchCache).where(
                TrendSearchCache.genre == genre, TrendSearchCache.subgenre == subgenre, TrendSearchCache.language == language,
                TrendSearchCache.region == region, TrendSearchCache.time_window == window, TrendSearchCache.query == query,
            ).order_by(TrendSearchCache.created_at.desc()).limit(1)
        )
    ).scalars()
    for row in rows:
        if _utc(row.expires_at) > datetime.now(timezone.utc):
            return row
    return None


async def put_trend_query(session: AsyncSession, genre, subgenre, language, region, window, query, video_ids: list[str], ttl_hours: int) -> TrendSearchCache:
    row = TrendSearchCache(
        genre=genre, subgenre=subgenre, language=language, region=region, time_window=window, query=query,
        video_ids=video_ids, expires_at=datetime.now(timezone.utc) + timedelta(hours=ttl_hours),
    )
    session.add(row)
    await session.flush()
    return row


async def replace_trend_topics(session: AsyncSession, genre, subgenre, language, region, window, topics: list[dict]) -> None:
    await session.execute(delete(TrendTopic).where(
        TrendTopic.genre == genre, TrendTopic.subgenre == subgenre, TrendTopic.language == language,
        TrendTopic.region == region, TrendTopic.time_window == window,
    ))
    for t in topics:
        session.add(TrendTopic(
            genre=genre, subgenre=subgenre, language=language, region=region, time_window=window,
            topic_name=t["topic"], sample_size=t["sample_size"], median_views=t["median_views"], average_views=t["average_views"],
            engagement_rate=t["engagement_rate"], momentum_score=t["momentum_score"], momentum_version=t["momentum_version"],
            common_formats=t["common_formats"], common_title_patterns=t["common_title_patterns"],
        ))
    await session.flush()


async def save_genre_benchmark(session: AsyncSession, genre, subgenre, language, region, window, sample_size: int, stats: dict) -> None:
    await session.execute(delete(GenreBenchmark).where(
        GenreBenchmark.genre == genre, GenreBenchmark.subgenre == subgenre, GenreBenchmark.language == language,
        GenreBenchmark.region == region, GenreBenchmark.time_window == window,
    ))
    session.add(GenreBenchmark(genre=genre, subgenre=subgenre, language=language, region=region, time_window=window, sample_size=sample_size, stats=stats))
    await session.flush()
