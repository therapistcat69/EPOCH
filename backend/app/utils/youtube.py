import re
from urllib.parse import parse_qs, urlparse

from app.errors import AppError

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_YT_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}
_SHORT_HOST = "youtu.be"


class InvalidYouTubeURL(AppError):
    def __init__(self, message: str):
        super().__init__("INVALID_URL", message, 400)


def is_valid_video_id(value: str) -> bool:
    return bool(_VIDEO_ID_RE.match(value or ""))


def extract_video_id(url: str) -> str:
    """Return the 11-char video ID from a supported YouTube URL.

    Raises InvalidYouTubeURL with a user-presentable reason otherwise.
    """
    if not url or not url.strip():
        raise InvalidYouTubeURL("Please paste a YouTube video link.")
    raw = url.strip()
    if "://" not in raw:
        raw = "https://" + raw
    try:
        parsed = urlparse(raw)
    except ValueError:
        raise InvalidYouTubeURL("That doesn't look like a valid URL.")

    host = (parsed.hostname or "").lower()
    if not host or "." not in host:
        raise InvalidYouTubeURL("That doesn't look like a valid URL.")
    if host != _SHORT_HOST and host not in _YT_HOSTS:
        raise InvalidYouTubeURL("Only YouTube links are supported.")

    parts = [p for p in parsed.path.split("/") if p]
    candidate: str | None = None
    if host == _SHORT_HOST:
        candidate = parts[0] if parts else None
    elif parts and parts[0] == "watch":
        candidate = (parse_qs(parsed.query).get("v") or [None])[0]
    elif parts and parts[0] == "embed":
        candidate = parts[1] if len(parts) > 1 else None
    elif parts and parts[0] in {"shorts", "live", "playlist", "channel", "c", "user"} or (
        parts and parts[0].startswith("@")
    ):
        raise InvalidYouTubeURL(
            "This kind of YouTube link isn't supported yet. Use a standard video link "
            "(youtube.com/watch?v=…, youtu.be/…, or youtube.com/embed/…)."
        )
    else:
        raise InvalidYouTubeURL("No video ID found in that link.")

    if not candidate:
        raise InvalidYouTubeURL("No video ID found in that link.")
    if not _VIDEO_ID_RE.match(candidate):
        raise InvalidYouTubeURL("The video ID in that link is malformed.")
    return candidate


def is_valid_youtube_url(url: str) -> bool:
    try:
        extract_video_id(url)
        return True
    except InvalidYouTubeURL:
        return False


def canonical_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"
