"""Creator-mode YouTube Data API helpers (OAuth token, includes private/unlisted uploads)."""
from app.errors import AppError
from app.schemas.youtube import NormalizedChannel, NormalizedVideo
from app.services.channel_service import normalize_channel
from app.services.youtube_client import YouTubeClient
from app.services.youtube_service import normalize_video, resolve_category_names

OwnedVideoTuple = tuple[NormalizedVideo, str | None, int]


async def get_my_channel(client: YouTubeClient) -> NormalizedChannel:
    raw = await client.my_channel()
    items = raw.get("items", [])
    if not items:
        raise AppError(
            "NO_CHANNEL",
            "We connected your Google account, but no YouTube channel was found for this account.",
            404,
        )
    return normalize_channel(items[0])


async def fetch_uploads(client: YouTubeClient, uploads_playlist_id: str, max_videos: int) -> list[OwnedVideoTuple]:
    """Paginate the uploads playlist, then batch videos.list (50 ids per call) for details.

    Videos that disappear between the two calls (deleted/unavailable) are skipped gracefully.
    """
    ids: list[str] = []
    token: str | None = None
    while len(ids) < max_videos:
        page = await client.playlist_items(uploads_playlist_id, 50, token)
        ids += [i["contentDetails"]["videoId"] for i in page.get("items", []) if i.get("contentDetails")]
        token = page.get("nextPageToken")
        if not token:
            break
    ids = ids[:max_videos]

    out: list[OwnedVideoTuple] = []
    items_by_id: dict[str, dict] = {}
    for i in range(0, len(ids), 50):
        raw = await client.videos(ids[i : i + 50], part="snippet,contentDetails,statistics,status")
        items_by_id.update({it["id"]: it for it in raw.get("items", [])})

    cat_ids = {it["snippet"]["categoryId"] for it in items_by_id.values() if it.get("snippet", {}).get("categoryId")}
    names = await resolve_category_names(client, cat_ids)
    for position, vid in enumerate(ids):  # position 0 = newest upload
        item = items_by_id.get(vid)
        if item is None:
            continue
        out.append((normalize_video(item, names), item.get("status", {}).get("privacyStatus"), position))
    return out
