from datetime import datetime

from pydantic import BaseModel


class OwnedVideo(BaseModel):
    video_id: str
    title: str
    thumbnail_url: str | None = None
    published_at: datetime | None = None
    duration_seconds: int | None = None
    category_name: str | None = None
    privacy_status: str | None = None
    view_count: int | None = None
    like_count: int | None = None
    comment_count: int | None = None


class OwnedVideosPage(BaseModel):
    items: list[OwnedVideo]
    total: int
    page: int
    limit: int
