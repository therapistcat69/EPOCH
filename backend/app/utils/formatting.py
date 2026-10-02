import re
from datetime import datetime
from typing import Any

_DURATION_RE = re.compile(
    r"^P(?:(?P<d>\d+)D)?(?:T(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>\d+)S)?)?$"
)


def parse_iso8601_duration(value: str | None) -> int:
    """'PT9M2S' -> 542. Returns 0 for missing/unparseable values (e.g. live streams 'P0D')."""
    if not value:
        return 0
    m = _DURATION_RE.match(value)
    if not m:
        return 0
    g = {k: int(v) if v else 0 for k, v in m.groupdict().items()}
    return g["d"] * 86400 + g["h"] * 3600 + g["m"] * 60 + g["s"]


def format_duration(seconds: int) -> str:
    h, rem = divmod(max(seconds, 0), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def to_int(value: Any) -> int | None:
    """YouTube returns counts as strings and omits hidden ones (e.g. likes hidden)."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def best_thumbnail(thumbnails: dict | None) -> str | None:
    for key in ("maxres", "standard", "high", "medium", "default"):
        if thumbnails and key in thumbnails:
            return thumbnails[key].get("url")
    return None
