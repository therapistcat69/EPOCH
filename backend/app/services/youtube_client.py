import logging
from typing import Any

import httpx

from app.config import get_settings
from app.errors import AppError

logger = logging.getLogger("retention.youtube")

_QUOTA_REASONS = {"quotaExceeded", "dailyLimitExceeded", "userRateLimitExceeded"}
_KEY_REASONS = {"keyInvalid", "keyExpired", "API_KEY_INVALID"}


def _map_google_error(status: int, body: dict | None, context: str = "data") -> AppError:
    """Translate a Google API error into a structured AppError.

    context: "data" (YouTube Data API), "analytics" or "reporting" (OAuth-only APIs).
    """
    err = (body or {}).get("error", {}) if isinstance(body, dict) else {}
    if not isinstance(err, dict):
        err = {}
    reasons = {e.get("reason") for e in err.get("errors", []) if isinstance(e, dict)}
    message = str(err.get("message", "")).lower()

    if reasons & _QUOTA_REASONS:
        return AppError(
            "QUOTA_EXCEEDED",
            "The YouTube API daily quota has been used up. Please try again later.",
            403,
        )
    if status == 429 or "ratelimitexceeded" in {r.lower() for r in reasons if r}:
        return AppError("RATE_LIMITED", "Too many requests to YouTube. Please slow down and retry.", 429)
    if status == 401:
        return AppError(
            "TOKEN_INVALID",
            "Your Google session is no longer valid. Please reconnect your YouTube account.",
            401,
        )
    if reasons & _KEY_REASONS or "api key not valid" in message or "api_key_invalid" in message:
        return AppError(
            "API_KEY_INVALID",
            "The server's YouTube API key is invalid. Check the backend configuration.",
            403,
        )
    detail_reasons = {d.get("reason") for d in err.get("details", []) if isinstance(d, dict)}
    if "API_KEY_SERVICE_BLOCKED" in detail_reasons:
        return AppError(
            "API_KEY_RESTRICTED",
            "The server's API key is restricted and doesn't allow the YouTube Data API v3.",
            403,
        )
    if "accessNotConfigured" in reasons or "has not been used in project" in message:
        names = {"analytics": "YouTube Analytics API", "reporting": "YouTube Reporting API"}
        return AppError(
            "API_NOT_ENABLED",
            f"The {names.get(context, 'YouTube Data API v3')} is not enabled for the server's Google Cloud project.",
            403,
        )
    if status == 403:
        if context == "analytics":
            return AppError(
                "ANALYTICS_PERMISSION",
                "YouTube Analytics refused access. Reconnect your account and approve the analytics permission.",
                403,
            )
        if context == "reporting":
            return AppError(
                "REPORTING_PERMISSION",
                "YouTube Reporting refused access. Reconnect your account and approve the analytics permission.",
                403,
            )
        return AppError(
            "FORBIDDEN",
            "YouTube refused the request (API not enabled, key restricted, or access denied).",
            403,
        )
    if status == 404:
        return AppError("NOT_FOUND", "The requested YouTube resource was not found.", 404)
    if status == 400:
        if "date" in message:
            return AppError("INVALID_DATE_RANGE", "That date range isn't valid for YouTube Analytics.", 400)
        if context == "analytics":
            return AppError(
                "ANALYTICS_UNAVAILABLE",
                "YouTube Analytics doesn't provide this report for the selected video or date range.",
                400,
            )
        return AppError("UPSTREAM_BAD_REQUEST", "YouTube rejected the request as invalid.", 400)
    return AppError("UPSTREAM_ERROR", "YouTube is temporarily unavailable. Please try again.", 502)


async def google_request(
    method: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    json: dict | None = None,
    access_token: str | None = None,
    api_key: str | None = None,
    context: str = "data",
    raw: bool = False,
) -> Any:
    """Single HTTP path for every Google API call. Never logs URLs, keys or tokens."""
    params = dict(params or {})
    headers: dict[str, str] = {}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    elif api_key:
        params["key"] = api_key
    else:
        raise AppError("API_KEY_MISSING", "The server is not configured with a YouTube API key.", 503)
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.request(method, url, params=params, json=json, headers=headers)
    except httpx.HTTPError:
        logger.warning("Network error calling Google (%s)", context)
        raise AppError("UPSTREAM_ERROR", "Could not reach YouTube. Please try again.", 502)

    if resp.status_code >= 400:
        try:
            body = resp.json()
        except ValueError:
            body = None
        logger.warning("Google %s API returned %s", context, resp.status_code)
        raise _map_google_error(resp.status_code, body, context)
    return resp if raw else resp.json()


class YouTubeClient:
    """Async wrapper over the YouTube Data API v3.

    Public mode: API key (server-side only). Creator mode: pass an OAuth access token.
    """

    def __init__(
        self, api_key: str | None = None, base_url: str | None = None, access_token: str | None = None
    ):
        settings = get_settings()
        self._key = api_key if api_key is not None else settings.youtube_api_key
        self._base = (base_url or settings.youtube_api_base).rstrip("/")
        self._token = access_token

    async def _get(self, resource: str, params: dict[str, Any]) -> dict:
        return await google_request(
            "GET",
            f"{self._base}/{resource}",
            params=params,
            access_token=self._token,
            api_key=self._key,
            context="data",
        )

    async def videos(self, ids: list[str], part: str = "snippet,contentDetails,statistics") -> dict:
        return await self._get("videos", {"part": part, "id": ",".join(ids), "maxResults": len(ids)})

    async def channels(self, ids: list[str]) -> dict:
        return await self._get(
            "channels",
            {"part": "snippet,statistics,contentDetails", "id": ",".join(ids)},
        )

    async def my_channel(self) -> dict:
        """channels.list?mine=true (requires an OAuth access token)."""
        return await self._get(
            "channels",
            {"part": "snippet,statistics,contentDetails", "mine": "true"},
        )

    async def channel_by_handle(self, handle: str) -> dict:
        return await self._get(
            "channels",
            {"part": "snippet,statistics,contentDetails", "forHandle": handle},
        )

    async def playlist_items(self, playlist_id: str, limit: int, page_token: str | None) -> dict:
        params: dict[str, Any] = {"part": "contentDetails", "playlistId": playlist_id, "maxResults": limit}
        if page_token:
            params["pageToken"] = page_token
        return await self._get("playlistItems", params)

    async def video_categories(self, ids: list[str], region: str = "US") -> dict:
        return await self._get(
            "videoCategories",
            {"part": "snippet", "id": ",".join(ids), "regionCode": region},
        )


def get_youtube_client() -> YouTubeClient:
    return YouTubeClient()
