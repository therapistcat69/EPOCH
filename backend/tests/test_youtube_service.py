import httpx
import pytest
import respx

from app.errors import AppError
from app.services import channel_service, youtube_service
from tests.fixtures import (
    CHANNEL_ID,
    CHANNELS_RESPONSE,
    PLAYLIST_RESPONSE,
    QUOTA_ERROR,
    VIDEO_ID,
    VIDEOS_RESPONSE,
)

BASE = "https://www.googleapis.com/youtube/v3"


@respx.mock
async def test_get_video_mocked(yt_client):
    route = respx.get(f"{BASE}/videos").mock(return_value=httpx.Response(200, json=VIDEOS_RESPONSE))
    video, raw = await youtube_service.get_video(yt_client, VIDEO_ID)
    assert video.title == "Example Video" and video.category_name == "Science & Technology"
    assert raw == VIDEOS_RESPONSE
    assert route.call_count == 1  # category came from the static map: no extra call
    assert route.calls[0].request.url.params["key"] == "test-key"


@respx.mock
async def test_video_not_found(yt_client):
    respx.get(f"{BASE}/videos").mock(return_value=httpx.Response(200, json={"items": []}))
    with pytest.raises(AppError) as exc:
        await youtube_service.get_video(yt_client, VIDEO_ID)
    assert exc.value.code == "VIDEO_NOT_FOUND" and exc.value.status_code == 404


@respx.mock
@pytest.mark.parametrize(
    "status,body,code,http",
    [
        (403, QUOTA_ERROR, "QUOTA_EXCEEDED", 403),
        (429, {"error": {"errors": [{"reason": "rateLimitExceeded"}]}}, "RATE_LIMITED", 429),
        (400, {"error": {"message": "API key not valid. Please pass a valid API key."}}, "API_KEY_INVALID", 403),
        (403, {"error": {"errors": [{"reason": "forbidden"}]}}, "FORBIDDEN", 403),
        (403, {"error": {"errors": [{"reason": "accessNotConfigured"}]}}, "API_NOT_ENABLED", 403),
        (
            403,
            {"error": {"errors": [{"reason": "forbidden"}], "details": [{"reason": "API_KEY_SERVICE_BLOCKED"}]}},
            "API_KEY_RESTRICTED",
            403,
        ),
        (500, {}, "UPSTREAM_ERROR", 502),
    ],
)
async def test_google_error_mapping(yt_client, status, body, code, http):
    respx.get(f"{BASE}/videos").mock(return_value=httpx.Response(status, json=body))
    with pytest.raises(AppError) as exc:
        await youtube_service.get_video(yt_client, VIDEO_ID)
    assert exc.value.code == code and exc.value.status_code == http
    assert "test-key" not in exc.value.message


async def test_missing_api_key():
    from app.services.youtube_client import YouTubeClient

    with pytest.raises(AppError) as exc:
        await YouTubeClient(api_key="").videos([VIDEO_ID])
    assert exc.value.code == "API_KEY_MISSING"


@respx.mock
async def test_unknown_category_fetched_once(yt_client):
    youtube_service._category_cache.clear()
    route = respx.get(f"{BASE}/videoCategories").mock(
        return_value=httpx.Response(200, json={"items": [{"id": "999", "snippet": {"title": "Custom"}}]})
    )
    assert await youtube_service.resolve_category_names(yt_client, {"999"}) == {"999": "Custom"}
    assert await youtube_service.resolve_category_names(yt_client, {"999"}) == {"999": "Custom"}
    assert route.call_count == 1


@respx.mock
async def test_channel_videos_pagination(yt_client):
    respx.get(f"{BASE}/channels").mock(return_value=httpx.Response(200, json=CHANNELS_RESPONSE))
    pl = respx.get(f"{BASE}/playlistItems").mock(return_value=httpx.Response(200, json=PLAYLIST_RESPONSE))
    respx.get(f"{BASE}/videos").mock(return_value=httpx.Response(200, json=VIDEOS_RESPONSE))
    page = await channel_service.list_channel_videos(yt_client, CHANNEL_ID, limit=5, page_token="TOK")
    assert page.next_page_token == "NEXT" and len(page.items) == 1
    params = pl.calls[0].request.url.params
    assert params["maxResults"] == "5" and params["pageToken"] == "TOK"
