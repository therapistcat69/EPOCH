import httpx
import pytest
import respx

from app.schemas.analytics import Metrics
from app.schemas.retention import RetentionPoint
from app.services import youtube_analytics_service as an
from app.services.youtube_data_service import fetch_uploads
from app.services.youtube_client import YouTubeClient
from tests.creator_fixtures import (
    ANALYTICS,
    BASE,
    OWNER_VIDEOS,
    REPORTING,
    UPLOADS,
    analytics_responder,
)
from tests.fixtures import CHANNEL_ID, VIDEO_ID
from tests.test_oauth import do_login, mock_google


# ---------------- pure normalization -------------------------------------------
def test_parse_rows_and_overview_normalization():
    resp = {"columnHeaders": [{"name": "views"}, {"name": "subscribersGained"}, {"name": "subscribersLost"},
                              {"name": "averageViewPercentage"}], "rows": [[100, 10, 3, 42.5]]}
    m = an.to_metrics(an.parse_rows(resp)[0])
    assert (m.views, m.subscribers_gained, m.subscribers_lost, m.net_subscribers) == (100, 10, 3, 7)
    assert m.average_view_percentage == 42.5
    assert m.shares is None  # never invented


def test_empty_rows_give_empty_metrics():
    assert an.to_metrics(None) == Metrics()
    assert an.parse_rows({"columnHeaders": [{"name": "views"}]}) == []


def test_video_metric_and_timeseries_normalization():
    rows = an.parse_rows({"columnHeaders": [{"name": "day"}, {"name": "views"}, {"name": "estimatedMinutesWatched"},
                                            {"name": "subscribersGained"}, {"name": "subscribersLost"}],
                          "rows": [["2026-09-01", 5, 2.5, 4, 1]]})
    p = an.to_timeseries(rows)[0]
    assert (p.date, p.views, p.watch_time_minutes, p.net_subscribers) == ("2026-09-01", 5, 2.5, 3)


def test_retention_normalization_is_raw_and_sorted():
    rows = [{"elapsedVideoTimeRatio": 0.5, "audienceWatchRatio": 0.6, "relativeRetentionPerformance": 1.17},
            {"elapsedVideoTimeRatio": 0.01, "audienceWatchRatio": 1.0, "relativeRetentionPerformance": 1.0}]
    pts = an.to_retention(rows)
    assert [p.time_ratio for p in pts] == [0.01, 0.5]
    assert pts[1].audience_watch_ratio == 0.6 and pts[1].started_watching is None


def test_observed_drop_offs_are_ranked_declines():
    pts = [RetentionPoint(time_ratio=r, audience_watch_ratio=a) for r, a in
           [(0.0, 1.0), (0.25, 0.9), (0.5, 0.5), (0.75, 0.5), (1.0, 0.45)]]
    drops = an.observed_drop_offs(pts, 100, top=2)
    assert [(d.from_ratio, d.to_ratio) for d in drops] == [(0.25, 0.5), (0.0, 0.25)]
    assert drops[0].drop == pytest.approx(0.4) and drops[0].from_seconds == 25


def test_insights_are_descriptive_only():
    ins = an.compute_insights([Metrics(average_view_percentage=40, views=10), Metrics(average_view_percentage=60, views=30),
                               Metrics(average_view_percentage=50, views=20)])
    assert ins.videos_analyzed == 3 and ins.median_view_percentage == 50 and ins.average_views_per_video == 20


def test_date_range_validation():
    from datetime import date

    from app.errors import AppError

    s, e = an.validate_range(None, None)
    assert (e - s).days == 27  # default 28 days
    with pytest.raises(AppError) as exc:
        an.validate_range(date(2026, 2, 1), date(2026, 1, 1))
    assert exc.value.code == "INVALID_DATE_RANGE"
    with pytest.raises(AppError):
        an.validate_range(date(2000, 1, 1), date(2026, 1, 1))


# ---------------- YouTube Data (creator) ---------------------------------------
@respx.mock
async def test_uploads_playlist_pagination_and_privacy():
    pl = respx.get(f"{BASE}/playlistItems").mock(side_effect=[
        httpx.Response(200, json={"items": [{"contentDetails": {"videoId": VIDEO_ID}}], "nextPageToken": "P2"}),
        httpx.Response(200, json={"items": [{"contentDetails": {"videoId": "gone0000000"}}]}),
    ])
    respx.get(f"{BASE}/videos").mock(return_value=httpx.Response(200, json=OWNER_VIDEOS))  # 2nd id is "deleted"
    out = await fetch_uploads(YouTubeClient(access_token="tok"), "UU123", 100)
    assert pl.call_count == 2 and pl.calls[1].request.url.params["pageToken"] == "P2"
    assert len(out) == 1  # deleted/unavailable video skipped
    video, privacy, position = out[0]
    assert (video.video_id, privacy, position) == (VIDEO_ID, "private", 0)


# ---------------- end-to-end creator API (mocked Google) ------------------------
def mock_creator_apis():
    mock_google()
    respx.get(f"{BASE}/playlistItems").mock(return_value=httpx.Response(200, json=UPLOADS))
    respx.get(f"{BASE}/videos").mock(return_value=httpx.Response(200, json=OWNER_VIDEOS))
    route = respx.get(ANALYTICS).mock(side_effect=analytics_responder)
    respx.get(f"{REPORTING}/jobs").mock(return_value=httpx.Response(200, json={"jobs": []}))
    respx.post(f"{REPORTING}/jobs").mock(return_value=httpx.Response(200, json={"id": "J1", "reportTypeId": "channel_basic_a3"}))
    respx.get(f"{REPORTING}/jobs/J1/reports").mock(return_value=httpx.Response(200, json={"reports": [{
        "id": "R1", "startTime": "2026-09-01T00:00:00Z", "endTime": "2026-09-02T00:00:00Z",
        "createTime": "2026-09-03T00:00:00Z", "downloadUrl": "https://youtubereporting.googleapis.com/v1/media/R1"}]}))
    return route


@respx.mock
async def test_sync_is_idempotent_and_populates_library(api):
    mock_creator_apis()
    await do_login(api)
    for _ in range(2):  # run twice: must update, not duplicate
        r = await api.post("/api/sync")
        assert r.status_code == 200 and r.json()["status"] == "started"
        status = (await api.get(f"/api/sync/{r.json()['sync_id']}")).json()
        assert status["status"] == "completed", status
        assert status["stats"] == {"videos": 1, "analytics": "ok", "reporting": "ok"}
    lib = (await api.get("/api/channel/me/videos")).json()
    assert lib["total"] == 1 and lib["items"][0]["privacy_status"] == "private"
    ch = (await api.get("/api/channel/me")).json()
    assert ch["uploads_playlist_id"] == "UUuAXFkgsw1L7xaCfnd5JJOw" and ch["last_synced_at"]
    assert len((await api.get("/api/reporting/jobs")).json()) == 1


@respx.mock
async def test_overview_timeseries_caching_and_fallback(api):
    route = mock_creator_apis()
    await do_login(api)
    q = "?start_date=2026-09-01&end_date=2026-09-28"
    o = (await api.get(f"/api/analytics/overview{q}")).json()
    assert o["metrics"]["views"] == 1000 and o["metrics"]["net_subscribers"] == 8 and o["cached"] is False
    assert route.calls[0].request.url.params["ids"] == "channel==MINE"
    assert route.calls[0].request.headers["authorization"] == "Bearer ACCESS-1"
    n = route.call_count
    assert (await api.get(f"/api/analytics/overview{q}")).json()["cached"] is True
    assert route.call_count == n  # served from the DB cache
    assert (await api.get(f"/api/analytics/overview{q}&refresh=true")).json()["cached"] is False

    ts = (await api.get(f"/api/analytics/timeseries{q}")).json()
    assert [p["date"] for p in ts["points"]] == ["2026-09-01", "2026-09-02"] and ts["points"][0]["net_subscribers"] == 1

    bad = await api.get("/api/analytics/overview?start_date=2026-09-10&end_date=2026-09-01")
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "INVALID_DATE_RANGE"


@respx.mock
async def test_engaged_views_fallback_when_unsupported(api):
    mock_google()
    calls = []

    def responder(request):
        calls.append(request.url.params["metrics"])
        if "engagedViews" in request.url.params["metrics"]:
            return httpx.Response(400, json={"error": {"message": "Unknown metric", "errors": [{"reason": "badRequest"}]}})
        return analytics_responder(request)

    respx.get(ANALYTICS).mock(side_effect=responder)
    await do_login(api)
    o = (await api.get("/api/analytics/overview?start_date=2026-09-01&end_date=2026-09-28")).json()
    assert o["metrics"]["views"] == 1000 and o["metrics"]["engaged_views"] is None
    assert len(calls) == 2


@respx.mock
async def test_video_table_one_batched_request_sort_search(api):
    route = mock_creator_apis()
    await do_login(api)
    await api.post("/api/sync")
    before = route.call_count
    r = (await api.get("/api/analytics/videos?start_date=2026-09-01&end_date=2026-09-28&sort=highest_avp")).json()
    assert route.call_count == before + 1  # one batched report, not one request per video
    assert route.calls[-1].request.url.params["dimensions"] == "video"
    row = r["items"][0]
    assert row["video"]["video_id"] == VIDEO_ID and row["metrics"]["average_view_percentage"] == 45.5
    assert r["insights"]["videos_analyzed"] == 1 and r["total"] == 1
    none = (await api.get("/api/analytics/videos?search=zzzz")).json()
    assert none["total"] == 0 and none["items"] == []
    assert (await api.get("/api/analytics/videos?sort=bogus")).status_code == 422


@respx.mock
async def test_video_detail_and_retention(api):
    route = mock_creator_apis()
    await do_login(api)
    await api.post("/api/sync")
    d = (await api.get(f"/api/analytics/video/{VIDEO_ID}?start_date=2026-09-01&end_date=2026-09-28")).json()
    assert d["metrics"]["subscribers_lost"] == 2 and d["video"]["title"] == "Example Video"

    ret = (await api.get(f"/api/analytics/video/{VIDEO_ID}/retention")).json()
    assert [p["time_ratio"] for p in ret["points"]] == [0.01, 0.5, 0.99]
    assert ret["points"][1]["audience_watch_ratio"] == 0.6 and ret["points"][1]["relative_retention_performance"] == 1.17
    assert ret["has_started_stopped"] is True and ret["observed_drop_offs"][0]["drop"] == pytest.approx(0.4)
    last = route.calls[-1].request.url.params
    assert last["filters"] == f"video=={VIDEO_ID}" and last["dimensions"] == "elapsedVideoTimeRatio"  # single video ID

    assert (await api.get("/api/analytics/video/AAAAAAAAAAA/retention")).json()["error"]["code"] == "VIDEO_NOT_FOUND"
    assert (await api.get("/api/analytics/video/bad/retention")).status_code == 400


@respx.mock
async def test_retention_unavailable_gives_friendly_error(api):
    mock_creator_apis()
    respx.get(ANALYTICS).mock(return_value=httpx.Response(200, json={"columnHeaders": [{"name": "elapsedVideoTimeRatio"}]}))
    await do_login(api)
    await api.post("/api/sync")
    r = await api.get(f"/api/analytics/video/{VIDEO_ID}/retention")
    assert r.status_code == 404 and r.json()["error"]["code"] == "ANALYTICS_UNAVAILABLE"


@respx.mock
async def test_breakdowns_and_analytics_permission_error(api):
    mock_creator_apis()
    await do_login(api)
    for path, key in [("traffic-sources", "MOBILE"), ("geography", "US"), ("devices", "MOBILE")]:
        r = (await api.get(f"/api/analytics/{path}?start_date=2026-09-01&end_date=2026-09-28")).json()
        assert r["rows"][0]["key"] == key and r["rows"][0]["views"] == 800, path
    respx.get(ANALYTICS).mock(return_value=httpx.Response(403, json={"error": {"errors": [{"reason": "forbidden"}]}}))
    r = await api.get("/api/analytics/overview?start_date=2026-08-01&end_date=2026-08-02")
    assert r.status_code == 403 and r.json()["error"]["code"] == "ANALYTICS_PERMISSION"


@respx.mock
async def test_ml_features_contract(api):
    mock_creator_apis()
    await do_login(api)
    await api.post("/api/sync")
    f = (await api.get(f"/api/analytics/video/{VIDEO_ID}/ml-features")).json()
    assert f["feature_schema_version"] == "1.0" and f["average_view_percentage"] == pytest.approx(0.455)
    assert f["retention"]["time_ratio"] == [0.01, 0.5, 0.99]
    assert f["content_features"] == {} and f["audio_features"] == {}  # unavailable: empty, never faked
    assert "token" not in str(f).lower()


# ---------------- Reporting API ---------------------------------------------------
@respx.mock
async def test_reporting_job_creation_listing_and_processing(api):
    mock_creator_apis()
    respx.get(f"{REPORTING}/reportTypes").mock(return_value=httpx.Response(200, json={"reportTypes": [
        {"id": "channel_basic_a3", "name": "User activity"}]}))
    csv = httpx.Response(200, text="date,views\n2026-09-01,5\n2026-09-02,6\n")
    respx.get("https://youtubereporting.googleapis.com/v1/media/R1").mock(return_value=csv)
    await do_login(api)

    types = (await api.get("/api/reporting/report-types")).json()
    assert types[0]["id"] == "channel_basic_a3"

    job = (await api.post("/api/reporting/jobs", json={})).json()  # default channel_basic_a3
    assert job["youtube_job_id"] == "J1" and job["report_type"] == "channel_basic_a3"
    again = (await api.post("/api/reporting/jobs", json={})).json()
    assert again["id"] == job["id"]  # idempotent: no second job

    reports = (await api.get(f"/api/reporting/jobs/{job['id']}/reports")).json()
    assert len(reports) == 1 and reports[0]["youtube_report_id"] == "R1" and reports[0]["processed_at"] is None

    done = (await api.post(f"/api/reporting/reports/{reports[0]['id']}/process")).json()
    assert done["row_count"] == 2 and done["columns"] == ["date", "views"]


@respx.mock
async def test_reporting_permission_error(api):
    mock_creator_apis()
    respx.get(f"{REPORTING}/jobs").mock(return_value=httpx.Response(403, json={"error": {"errors": [{"reason": "forbidden"}]}}))
    await do_login(api)
    r = await api.post("/api/reporting/jobs", json={})
    assert r.status_code == 403 and r.json()["error"]["code"] == "REPORTING_PERMISSION"
