from app.errors import AppError
from app.schemas.youtube import ChannelVideosPage, NormalizedChannel
from app.services.youtube_client import YouTubeClient
from app.services.youtube_service import normalize_video, resolve_category_names
from app.utils.formatting import best_thumbnail, parse_datetime, to_int

MAX_LIMIT = 50
DEFAULT_LIMIT = 12


def normalize_channel(item: dict) -> NormalizedChannel:
    snippet = item.get("snippet", {})
    stats = item.get("statistics", {})
    uploads = item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
    return NormalizedChannel(
        channel_id=item["id"],
        title=snippet.get("title", ""),
        description=snippet.get("description"),
        custom_url=snippet.get("customUrl"),
        published_at=parse_datetime(snippet.get("publishedAt")),
        # subscriberCount is omitted when the channel hides it
        subscriber_count=None if stats.get("hiddenSubscriberCount") else to_int(stats.get("subscriberCount")),
        total_views=to_int(stats.get("viewCount")),
        video_count=to_int(stats.get("videoCount")),
        thumbnail_url=best_thumbnail(snippet.get("thumbnails")),
        uploads_playlist_id=uploads,
    )


async def get_channel(client: YouTubeClient, channel_id: str) -> tuple[NormalizedChannel, dict]:
    """Accepts a UC… channel ID or an @handle."""
    if channel_id.startswith("@"):
        raw = await client.channel_by_handle(channel_id)
    else:
        raw = await client.channels([channel_id])
    items = raw.get("items", [])
    if not items:
        raise AppError("CHANNEL_NOT_FOUND", "The requested YouTube channel could not be found.", 404)
    return normalize_channel(items[0]), raw


async def list_channel_videos(
    client: YouTubeClient, channel_id: str, limit: int = DEFAULT_LIMIT, page_token: str | None = None
) -> ChannelVideosPage:
    limit = max(1, min(limit, MAX_LIMIT))
    channel, _ = await get_channel(client, channel_id)
    if not channel.uploads_playlist_id:
        return ChannelVideosPage(items=[], next_page_token=None)

    page = await client.playlist_items(channel.uploads_playlist_id, limit, page_token)
    ids = [i["contentDetails"]["videoId"] for i in page.get("items", []) if i.get("contentDetails")]
    if not ids:
        return ChannelVideosPage(items=[], next_page_token=page.get("nextPageToken"))

    # One batched call for durations/stats instead of one per video.
    videos_raw = await client.videos(ids)
    items = videos_raw.get("items", [])
    cat_ids = {i["snippet"]["categoryId"] for i in items if i.get("snippet", {}).get("categoryId")}
    names = await resolve_category_names(client, cat_ids)
    by_id = {i["id"]: normalize_video(i, names) for i in items}
    ordered = [by_id[v] for v in ids if v in by_id]  # preserve uploads order (newest first)
    return ChannelVideosPage(items=ordered, next_page_token=page.get("nextPageToken"))
