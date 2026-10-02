import logging

from app.errors import AppError
from app.schemas.youtube import ChannelRef, NormalizedVideo, VideoStatistics
from app.services.youtube_client import YouTubeClient
from app.utils.formatting import (
    best_thumbnail,
    format_duration,
    parse_datetime,
    parse_iso8601_duration,
    to_int,
)
from app.utils.youtube import canonical_url, is_valid_video_id

logger = logging.getLogger("retention.youtube")

# Standard YouTube category IDs. Used as a fallback so we never *need* the extra API call.
STATIC_CATEGORIES = {
    "1": "Film & Animation", "2": "Autos & Vehicles", "10": "Music", "15": "Pets & Animals",
    "17": "Sports", "18": "Short Movies", "19": "Travel & Events", "20": "Gaming",
    "21": "Videoblogging", "22": "People & Blogs", "23": "Comedy", "24": "Entertainment",
    "25": "News & Politics", "26": "Howto & Style", "27": "Education",
    "28": "Science & Technology", "29": "Nonprofits & Activism", "30": "Movies",
    "31": "Anime/Animation", "32": "Action/Adventure", "33": "Classics", "34": "Comedy",
    "35": "Documentary", "36": "Drama", "37": "Family", "38": "Foreign", "39": "Horror",
    "40": "Sci-Fi/Fantasy", "41": "Thriller", "42": "Shorts", "43": "Shows", "44": "Trailers",
}

# Process-wide cache: each category ID is resolved at most once.
_category_cache: dict[str, str] = {}


async def resolve_category_names(client: YouTubeClient, ids: set[str]) -> dict[str, str]:
    """Return {id: name}. Order: in-memory cache -> static map -> one batched API call."""
    result: dict[str, str] = {}
    missing: list[str] = []
    for cid in ids:
        name = _category_cache.get(cid) or STATIC_CATEGORIES.get(cid)
        if name:
            _category_cache[cid] = name
            result[cid] = name
        else:
            missing.append(cid)
    if missing:
        try:
            data = await client.video_categories(missing)
            for item in data.get("items", []):
                name = item.get("snippet", {}).get("title")
                if name:
                    _category_cache[item["id"]] = name
                    result[item["id"]] = name
        except AppError:
            logger.info("Category lookup failed; leaving %s unnamed", missing)
    return result


def normalize_video(item: dict, category_names: dict[str, str] | None = None) -> NormalizedVideo:
    snippet = item.get("snippet", {})
    content = item.get("contentDetails", {})
    stats = item.get("statistics", {})
    vid = item["id"]
    duration = parse_iso8601_duration(content.get("duration"))
    category_id = snippet.get("categoryId")
    category_name = (category_names or {}).get(category_id) if category_id else None
    if category_id and not category_name:
        category_name = _category_cache.get(category_id) or STATIC_CATEGORIES.get(category_id)
    return NormalizedVideo(
        video_id=vid,
        url=canonical_url(vid),
        title=snippet.get("title", ""),
        description=snippet.get("description"),
        channel=ChannelRef(id=snippet.get("channelId"), title=snippet.get("channelTitle")),
        published_at=parse_datetime(snippet.get("publishedAt")),
        duration_seconds=duration,
        duration_formatted=format_duration(duration),
        category_id=category_id,
        category_name=category_name,
        statistics=VideoStatistics(
            views=to_int(stats.get("viewCount")),
            likes=to_int(stats.get("likeCount")),
            comments=to_int(stats.get("commentCount")),
        ),
        thumbnail_url=best_thumbnail(snippet.get("thumbnails")),
        tags=snippet.get("tags", []) or [],
        language=snippet.get("defaultAudioLanguage") or snippet.get("defaultLanguage"),
        caption_available=str(content.get("caption", "false")).lower() == "true",
    )


async def fetch_video_raw(client: YouTubeClient, video_id: str) -> dict:
    if not is_valid_video_id(video_id):
        raise AppError("INVALID_URL", "The video ID is malformed.", 400)
    data = await client.videos([video_id])
    items = data.get("items", [])
    if not items:
        raise AppError(
            "VIDEO_NOT_FOUND",
            "The requested YouTube video could not be found. It may be private or deleted.",
            404,
        )
    return data


async def get_video(client: YouTubeClient, video_id: str) -> tuple[NormalizedVideo, dict]:
    """Return (normalized, raw_response)."""
    raw = await fetch_video_raw(client, video_id)
    item = raw["items"][0]
    cid = item.get("snippet", {}).get("categoryId")
    names = await resolve_category_names(client, {cid}) if cid else {}
    return normalize_video(item, names), raw
