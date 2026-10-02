from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Video
from app.schemas.youtube import NormalizedVideo


async def upsert_owned_videos(
    session: AsyncSession,
    videos: list[tuple[NormalizedVideo, str | None, int]],
) -> int:
    """Idempotent bulk upsert. Items are (video, privacy_status, upload_position)."""
    ids = [v.video_id for v, _, _ in videos]
    existing: dict[str, Video] = {}
    for i in range(0, len(ids), 500):  # chunk to stay under SQLite/Postgres parameter limits
        rows = (await session.execute(select(Video).where(Video.youtube_video_id.in_(ids[i : i + 500])))).scalars()
        existing.update({r.youtube_video_id: r for r in rows})
    for v, privacy, position in videos:
        row = existing.get(v.video_id)
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
        row.privacy_status = privacy
        row.upload_position = position
    await session.flush()
    return len(videos)


async def list_channel_videos(session: AsyncSession, channel_id: str, search: str | None = None) -> list[Video]:
    stmt = select(Video).where(Video.channel_id == channel_id)
    if search:
        like = f"%{search.lower()}%"
        stmt = stmt.where(or_(func.lower(Video.title).like(like), func.lower(Video.description).like(like)))
    stmt = stmt.order_by(Video.published_at.desc())
    return list((await session.execute(stmt)).scalars())


async def get_video_by_yt_id(session: AsyncSession, channel_id: str, youtube_video_id: str) -> Video | None:
    return (
        await session.execute(
            select(Video).where(Video.channel_id == channel_id, Video.youtube_video_id == youtube_video_id)
        )
    ).scalar_one_or_none()
