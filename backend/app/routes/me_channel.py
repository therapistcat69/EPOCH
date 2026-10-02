from fastapi import APIRouter, Depends, Query

from app.deps import CreatorContext, creator_context
from app.repositories import video_repository
from app.schemas.channel import OwnedChannel
from app.schemas.video import OwnedVideo, OwnedVideosPage

router = APIRouter(prefix="/api/channel/me", tags=["creator channel"])

VIDEO_SORTS = {
    "newest": lambda v: (v.published_at is None, -(v.published_at.timestamp() if v.published_at else 0)),
    "oldest": lambda v: (v.published_at is None, v.published_at.timestamp() if v.published_at else 0),
    "views": lambda v: -(v.view_count or 0),
    "longest": lambda v: -(v.duration_seconds or 0),
    "shortest": lambda v: v.duration_seconds or 0,
}


def to_owned_video(v) -> OwnedVideo:
    return OwnedVideo(
        video_id=v.youtube_video_id, title=v.title, thumbnail_url=v.thumbnail_url, published_at=v.published_at,
        duration_seconds=v.duration_seconds, category_name=v.category_name, privacy_status=v.privacy_status,
        view_count=v.view_count, like_count=v.like_count, comment_count=v.comment_count,
    )


@router.get("", response_model=OwnedChannel)
async def my_channel(ctx: CreatorContext = Depends(creator_context)):
    c = ctx.channel
    return OwnedChannel(
        channel_id=c.youtube_channel_id, title=c.title, description=c.description, custom_url=c.custom_url,
        thumbnail_url=c.thumbnail_url, published_at=c.published_at, subscriber_count=c.subscriber_count,
        total_views=c.total_views, video_count=c.video_count, uploads_playlist_id=c.uploads_playlist_id,
        last_synced_at=c.last_synced_at,
    )


@router.get("/videos", response_model=OwnedVideosPage)
async def my_videos(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = None,
    sort: str = Query("newest", pattern="^(newest|oldest|views|longest|shortest)$"),
    ctx: CreatorContext = Depends(creator_context),
):
    rows = await video_repository.list_channel_videos(ctx.session, ctx.channel.youtube_channel_id, search)
    rows.sort(key=VIDEO_SORTS[sort])
    start = (page - 1) * limit
    return OwnedVideosPage(items=[to_owned_video(v) for v in rows[start : start + limit]], total=len(rows), page=page, limit=limit)
