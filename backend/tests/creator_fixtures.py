"""Mock Google responses for creator-mode tests."""
import httpx

from tests.fixtures import CHANNEL_ID, CHANNELS_RESPONSE, VIDEO_ID, VIDEOS_RESPONSE

BASE = "https://www.googleapis.com/youtube/v3"
ANALYTICS = "https://youtubeanalytics.googleapis.com/v2/reports"
REPORTING = "https://youtubereporting.googleapis.com/v1"
TOKEN_URL = "https://oauth2.googleapis.com/token"

SCOPES = "https://www.googleapis.com/auth/youtube.readonly https://www.googleapis.com/auth/yt-analytics.readonly"

TOKEN_RESPONSE = {
    "access_token": "ACCESS-1",
    "refresh_token": "REFRESH-1",
    "expires_in": 3600,
    "scope": SCOPES,
    "token_type": "Bearer",
}

# Owner view includes the status part (privacy)
OWNER_VIDEOS = {
    "items": [{**VIDEOS_RESPONSE["items"][0], "status": {"privacyStatus": "private"}}]
}
UPLOADS = {"items": [{"contentDetails": {"videoId": VIDEO_ID}}]}


def hdr(*names):
    return [{"name": n} for n in names]


def analytics_responder(request: httpx.Request) -> httpx.Response:
    p = request.url.params
    dims, metrics = p.get("dimensions"), p["metrics"].split(",")
    if dims == "elapsedVideoTimeRatio":
        cols = ["elapsedVideoTimeRatio", *metrics]
        rows = [
            [0.01, 1.0, 1.0, 5, 0] if "startedWatching" in metrics else [0.01, 1.0, 1.0],
            [0.50, 0.6, 1.17, 1, 3] if "startedWatching" in metrics else [0.50, 0.6, 1.17],
            [0.99, 0.2, 0.9, 0, 6] if "startedWatching" in metrics else [0.99, 0.2, 0.9],
        ]
    elif dims == "day":
        cols, rows = ["day", *metrics], [["2026-09-01", 10, 25.5, 2, 1], ["2026-09-02", 20, 30.0, 3, 0]]
    elif dims == "video":
        cols = ["video", *metrics]
        rows = [[VIDEO_ID, 1000, 500.5, 120.5, 45.5, 50, 5, 7]]
    elif dims:  # country / deviceType / insightTrafficSourceType
        cols, rows = [dims, *metrics], [["US" if dims == "country" else "MOBILE", 800, 400.0, 100.0, 40.0][: len(metrics) + 1]]
    else:  # overview or single-video totals
        vals = {"views": 1000, "engagedViews": 900, "estimatedMinutesWatched": 500.5, "averageViewDuration": 120.5,
                "averageViewPercentage": 45.5, "likes": 50, "comments": 5, "shares": 3,
                "subscribersGained": 10, "subscribersLost": 2}
        cols, rows = metrics, [[vals[m] for m in metrics]]
    return httpx.Response(200, json={"columnHeaders": hdr(*cols), "rows": rows})
