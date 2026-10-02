from datetime import datetime

from pydantic import BaseModel


class OwnedChannel(BaseModel):
    channel_id: str
    title: str
    description: str | None = None
    custom_url: str | None = None
    thumbnail_url: str | None = None
    published_at: datetime | None = None
    subscriber_count: int | None = None
    total_views: int | None = None
    video_count: int | None = None
    uploads_playlist_id: str | None = None
    last_synced_at: datetime | None = None
