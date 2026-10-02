import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Channel, Video, VideoAnalysis
from app.schemas.youtube import NormalizedChannel, NormalizedVideo


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def upsert_video(session: AsyncSession, v: NormalizedVideo) -> Video:
    row = (await session.execute(select(Video).where(Video.youtube_video_id == v.video_id))).scalar_one_or_none()
    if row is None:
        row = Video(youtube_video_id=v.video_id)
        session.add(row)
    row.youtube_url = v.url
    row.title = v.title
    row.description = v.description
    row.channel_id = v.channel.id
    row.channel_title = v.channel.title
    row.published_at = v.published_at
    row.duration_seconds = v.duration_seconds
    row.category_id = v.category_id
    row.category_name = v.category_name
    row.view_count = v.statistics.views
    row.like_count = v.statistics.likes
    row.comment_count = v.statistics.comments
    row.thumbnail_url = v.thumbnail_url
    await session.flush()
    return row


async def upsert_channel(session: AsyncSession, c: NormalizedChannel) -> Channel:
    row = (
        await session.execute(select(Channel).where(Channel.youtube_channel_id == c.channel_id))
    ).scalar_one_or_none()
    if row is None:
        row = Channel(youtube_channel_id=c.channel_id)
        session.add(row)
    row.title = c.title
    row.description = c.description
    row.custom_url = c.custom_url
    row.published_at = c.published_at
    row.subscriber_count = c.subscriber_count
    row.video_count = c.video_count
    row.view_count = c.total_views
    row.thumbnail_url = c.thumbnail_url
    await session.flush()
    return row


async def create_analysis(
    session: AsyncSession,
    video_row_id: uuid.UUID,
    raw: dict,
    normalized: dict,
    features: dict,
) -> VideoAnalysis:
    row = VideoAnalysis(
        video_id=video_row_id,
        status="completed",
        raw_api_response=raw,
        normalized_data=normalized,
        feature_payload=features,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def get_recent_analysis(
    session: AsyncSession, youtube_video_id: str, ttl_hours: int
) -> VideoAnalysis | None:
    stmt = (
        select(VideoAnalysis)
        .join(Video, Video.id == VideoAnalysis.video_id)
        .where(Video.youtube_video_id == youtube_video_id, VideoAnalysis.status == "completed")
        .order_by(VideoAnalysis.created_at.desc())
        .limit(1)
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        return None
    if _as_utc(row.created_at) < datetime.now(timezone.utc) - timedelta(hours=ttl_hours):
        return None
    return row


async def get_analysis(session: AsyncSession, analysis_id: uuid.UUID) -> VideoAnalysis | None:
    return await session.get(VideoAnalysis, analysis_id)


async def list_recent_analyses(session: AsyncSession, limit: int = 8) -> list[VideoAnalysis]:
    stmt = select(VideoAnalysis).order_by(VideoAnalysis.created_at.desc()).limit(limit * 3)
    rows = (await session.execute(stmt)).scalars().all()
    seen: set[uuid.UUID] = set()
    out: list[VideoAnalysis] = []
    for r in rows:  # newest analysis per video
        if r.video_id in seen:
            continue
        seen.add(r.video_id)
        out.append(r)
        if len(out) >= limit:
            break
    return out
