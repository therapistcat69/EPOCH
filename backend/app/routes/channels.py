from fastapi import APIRouter, Depends, Query

from app.schemas.youtube import ChannelVideosPage, NormalizedChannel
from app.services import channel_service
from app.services.youtube_client import YouTubeClient, get_youtube_client

router = APIRouter()


@router.get("/api/youtube/channel/{channel_id}", response_model=NormalizedChannel)
async def get_channel(channel_id: str, client: YouTubeClient = Depends(get_youtube_client)):
    channel, _ = await channel_service.get_channel(client, channel_id)
    return channel


@router.get("/api/youtube/channel/{channel_id}/videos", response_model=ChannelVideosPage)
async def get_channel_videos(
    channel_id: str,
    limit: int = Query(channel_service.DEFAULT_LIMIT, ge=1, le=channel_service.MAX_LIMIT),
    pageToken: str | None = Query(None),
    client: YouTubeClient = Depends(get_youtube_client),
):
    return await channel_service.list_channel_videos(client, channel_id, limit, pageToken)
