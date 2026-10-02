from datetime import datetime

from pydantic import BaseModel


class ChannelRef(BaseModel):
    id: str | None = None
    title: str | None = None


class VideoStatistics(BaseModel):
    views: int | None = None
    likes: int | None = None
    comments: int | None = None


class NormalizedVideo(BaseModel):
    video_id: str
    url: str
    title: str
    description: str | None = None
    channel: ChannelRef
    published_at: datetime | None = None
    duration_seconds: int = 0
    duration_formatted: str = "00:00"
    category_id: str | None = None
    category_name: str | None = None
    statistics: VideoStatistics
    thumbnail_url: str | None = None
    tags: list[str] = []
    language: str | None = None
    caption_available: bool = False
    source: str = "youtube_data_api"


class NormalizedChannel(BaseModel):
    channel_id: str
    title: str
    description: str | None = None
    custom_url: str | None = None
    published_at: datetime | None = None
    subscriber_count: int | None = None
    total_views: int | None = None
    video_count: int | None = None
    thumbnail_url: str | None = None
    uploads_playlist_id: str | None = None
    source: str = "youtube_data_api"


class ChannelVideosPage(BaseModel):
    items: list[NormalizedVideo]
    next_page_token: str | None = None
