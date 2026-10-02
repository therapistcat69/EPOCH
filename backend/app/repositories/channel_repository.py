import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import YouTubeChannel
from app.schemas.youtube import NormalizedChannel


async def upsert_channel(session: AsyncSession, user_id: uuid.UUID, c: NormalizedChannel) -> YouTubeChannel:
    row = (
        await session.execute(select(YouTubeChannel).where(YouTubeChannel.youtube_channel_id == c.channel_id))
    ).scalar_one_or_none()
    if row is None:
        row = YouTubeChannel(youtube_channel_id=c.channel_id, user_id=user_id)
        session.add(row)
    row.user_id = user_id
    row.title = c.title
    row.description = c.description
    row.custom_url = c.custom_url
    row.thumbnail_url = c.thumbnail_url
    row.published_at = c.published_at
    row.subscriber_count = c.subscriber_count
    row.total_views = c.total_views
    row.video_count = c.video_count
    row.uploads_playlist_id = c.uploads_playlist_id
    await session.flush()
    return row


async def get_user_channel(session: AsyncSession, user_id: uuid.UUID) -> YouTubeChannel | None:
    return (
        await session.execute(select(YouTubeChannel).where(YouTubeChannel.user_id == user_id).limit(1))
    ).scalar_one_or_none()


async def mark_synced(session: AsyncSession, channel: YouTubeChannel) -> None:
    channel.last_synced_at = datetime.now(timezone.utc)
    await session.flush()
