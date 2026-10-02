import httpx
import respx

from tests.fixtures import CHANNELS_RESPONSE, QUOTA_ERROR, VIDEO_ID, VIDEOS_RESPONSE

BASE = "https://www.googleapis.com/youtube/v3"
URL = f"https://youtu.be/{VIDEO_ID}"


async def test_health(api):
    r = await api.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


async def test_analyze_invalid_url(api):
    r = await api.post("/api/analyze", json={"youtube_url": "https://vimeo.com/1"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_URL"


async def test_analyze_bad_body(api):
    r = await api.post("/api/analyze", json={})
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_REQUEST"


@respx.mock
async def test_analyze_happy_path_and_cache(api):
    vroute = respx.get(f"{BASE}/videos").mock(return_value=httpx.Response(200, json=VIDEOS_RESPONSE))
    respx.get(f"{BASE}/channels").mock(return_value=httpx.Response(200, json=CHANNELS_RESPONSE))

    r = await api.post("/api/analyze", json={"youtube_url": URL})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed" and body["cached"] is False
    assert body["video"]["title"] == "Example Video"
    assert body["video"]["category_name"] == "Science & Technology"
    assert body["channel"]["subscriber_count"] == 12345
    assert body["features"]["view_count"] == 100000
    assert body["features"]["document_entropy"] is None
    assert body["ml_status"]["available"] is False
    assert "retention" not in " ".join(body["features"].keys())

    # Second call is served from the DB cache: no new YouTube request
    r2 = await api.post("/api/analyze", json={"youtube_url": URL})
    assert r2.json()["cached"] is True and r2.json()["analysis_id"] == body["analysis_id"]
    assert vroute.call_count == 1

    # refresh bypasses the cache
    r3 = await api.post("/api/analyze?refresh=true", json={"youtube_url": URL})
    assert r3.json()["cached"] is False and vroute.call_count == 2

    # stored report can be re-read, with raw data on request
    got = await api.get(f"/api/analyses/{body['analysis_id']}?include_raw=true")
    assert got.status_code == 200 and got.json()["raw_api_response"]["video"]["items"]
    recent = await api.get("/api/analyses")
    assert len(recent.json()) == 1


@respx.mock
async def test_analyze_video_not_found(api):
    respx.get(f"{BASE}/videos").mock(return_value=httpx.Response(200, json={"items": []}))
    r = await api.post("/api/analyze", json={"youtube_url": URL})
    assert r.status_code == 404 and r.json()["error"]["code"] == "VIDEO_NOT_FOUND"


@respx.mock
async def test_analyze_quota_error(api):
    respx.get(f"{BASE}/videos").mock(return_value=httpx.Response(403, json=QUOTA_ERROR))
    r = await api.post("/api/analyze", json={"youtube_url": URL})
    assert r.status_code == 403 and r.json()["error"]["code"] == "QUOTA_EXCEEDED"


async def test_unknown_analysis(api):
    r = await api.get("/api/analyses/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404 and r.json()["error"]["code"] == "ANALYSIS_NOT_FOUND"


async def test_ml_predict_not_implemented(api):
    payload = {
        "video_id": VIDEO_ID,
        "features": {"video_id": VIDEO_ID, "title": "t", "duration_seconds": 1},
    }
    r = await api.post("/api/ml/predict", json=payload)
    assert r.status_code == 501 and r.json()["error"]["code"] == "ML_NOT_IMPLEMENTED"


async def test_creator_routes_require_login(api):
    for path in ["/api/channel/me", "/api/analytics/overview", "/api/analytics/videos", "/api/reporting/jobs"]:
        r = await api.get(path)
        assert r.status_code == 401 and r.json()["error"]["code"] == "NOT_AUTHENTICATED", path
    r = await api.post("/api/sync")
    assert r.status_code == 401
    me = await api.get("/api/auth/me")
    assert me.status_code == 200 and me.json() == {"authenticated": False, "user": None, "channel": None}
