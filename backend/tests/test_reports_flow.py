import json

import httpx
import pytest
import respx

from app.services import trend_service
from tests.creator_fixtures import ANALYTICS, BASE
from tests.fixtures import VIDEO_ID
from tests.test_creator_flow import mock_creator_apis
from tests.test_oauth import do_login
from tests.test_trends_engine import mock_search_and_videos
from tests.test_transcripts_and_analysis import SRT

GROQ = "https://api.groq.com/openai/v1"


def groq_responder(request: httpx.Request) -> httpx.Response:
    body = request.content.decode()
    if "Label each transcript section" in body:
        payload = {"sections": [{"index": 0, "topic": "Intro and promise", "summary": "Opens by comparing AI tools."},
                                {"index": 1, "topic": "Call to action", "summary": "Asks viewers to subscribe."}]}
    elif "CHANNEL report" in body:
        payload = {"summary": "Channel summary grounded in data.", "strengths": ["s"], "weaknesses": ["w"], "content_patterns": ["p"],
                   "observed_performance_patterns": ["o"], "recommendations": [{"observation": "a", "interpretation": "b", "recommendation": "c"}],
                   "experiments_to_try": ["e"]}
    elif "VIDEO report" in body:
        payload = {"summary": "Video summary.", "strengths": ["s"], "weaknesses": ["w"],
                   "hook_analysis": {"observation": "hook obs"}, "recommendations": [
                       {"type": "cut", "start": 62.0, "end": 68.0, "reason": "CTA early", "evidence": "CTA at 62s", "confidence": 0.7}]}
    else:  # trend summary
        payload = {"summary": "Trend summary.", "observed_opportunities": [], "caveats": ["sample only"]}
    return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(payload)}}]})


async def ready(api):
    mock_creator_apis()
    await do_login(api)
    await api.post("/api/sync")


@respx.mock
async def test_transcript_unavailable_state_then_upload_srt(api):
    await ready(api)
    t = (await api.get(f"/api/video/{VIDEO_ID}/transcript")).json()
    assert t["available"] is False and t["message"] == "Transcript unavailable for this video."
    assert t["options"] == ["upload_transcript", "upload_audio"]

    up = await api.post(f"/api/video/{VIDEO_ID}/transcript/upload", json={"format": "srt", "content": SRT, "language": "en"})
    assert up.status_code == 200
    body = up.json()
    assert body["available"] and body["provider"] == "uploaded" and len(body["segments"]) == 3 and body["timestamps_estimated"] is False
    assert (await api.get(f"/api/video/{VIDEO_ID}/transcript")).json()["segments"][2]["start_seconds"] == 62.25

    bad = await api.post(f"/api/video/{VIDEO_ID}/transcript/upload", json={"format": "vtt", "content": "WEBVTT\n\nnothing"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "TRANSCRIPT_PARSE_FAILED"
    assert (await api.post("/api/video/AAAAAAAAAAA/transcript/upload", json={"format": "txt", "content": "hi"})).json()["error"]["code"] == "VIDEO_NOT_FOUND"


@respx.mock
async def test_groq_whisper_transcription_endpoint(api):
    await ready(api)
    respx.post(f"{GROQ}/audio/transcriptions").mock(return_value=httpx.Response(200, json={
        "language": "en", "duration": 20.0, "text": "hello world",
        "segments": [{"id": 0, "start": 0.0, "end": 8.0, "text": "Hello world welcome."}, {"id": 1, "start": 8.0, "end": 20.0, "text": "Today we test the example video."}]}))
    r = await api.post(f"/api/video/{VIDEO_ID}/transcript/transcribe", files={"file": ("a.mp3", b"fake-audio", "audio/mpeg")})
    assert r.status_code == 200 and r.json()["provider"] == "groq_whisper" and len(r.json()["segments"]) == 2
    assert r.json()["language"] == "en"


@respx.mock
async def test_transcribe_not_configured(api, monkeypatch):
    await ready(api)
    monkeypatch.setenv("GROQ_API_KEY", "")
    from app.config import get_settings

    get_settings.cache_clear()
    r = await api.post(f"/api/video/{VIDEO_ID}/transcript/transcribe", files={"file": ("a.mp3", b"x", "audio/mpeg")})
    assert r.status_code == 503 and r.json()["error"]["code"] == "GROQ_NOT_CONFIGURED"


@respx.mock
async def test_video_report_full_with_groq_and_retention_link(api, session_factory):
    await ready(api)
    respx.post(f"{GROQ}/chat/completions").mock(side_effect=groq_responder)
    await api.post(f"/api/video/{VIDEO_ID}/transcript/upload", json={"format": "srt", "content": SRT, "language": "en"})
    r = await api.get(f"/api/video/{VIDEO_ID}/report")
    assert r.status_code == 200, r.text
    rep = r.json()
    assert rep["video"]["title"] == "Example Video" and rep["analytics"]["metrics"]["views"] == 1000
    # observed retention (raw) + drop-off linked to the transcript text
    assert rep["retention"]["available"] and len(rep["retention"]["points"]) == 3
    drop = rep["retention"]["observed_drop_offs"][0]
    assert drop["drop"] == pytest.approx(0.4) and drop["from_seconds"] is not None
    assert rep["transcript"]["available"] and rep["features"]["segment_count"] == 3
    assert rep["features"]["segments"][2]["is_cta"] is True
    assert rep["hook"]["hook_latency_seconds"] == 0.0  # first cue already contains a hook phrase ("Today ...")
    # the sample transcript never says the title's words ("example video"), so no promise start is found: null, not invented
    assert rep["promise_gap"]["promise_gap_seconds"] is None and "content-structure" in rep["promise_gap"]["note"]
    assert rep["pacing"]["silence_rate"] is None  # needs audio: never invented
    assert rep["groq"]["available"] and rep["groq"]["report"]["recommendations"][0]["type"] == "cut"
    assert rep["features"]["segments"][0]["topic"] == "Intro and promise"  # Groq section label applied
    assert rep["predicted_retention"] == {"available": False, "message": "ML model not connected."}
    assert rep["experiments"] and all({"observation", "interpretation", "recommendation"} <= set(e) for e in rep["experiments"])

    # stored in DB: report, features and raw retention points
    from sqlalchemy import select

    from app.models import ContentFeature, VideoReport, VideoRetentionPoint

    async with session_factory() as s:
        assert (await s.execute(select(VideoReport))).scalars().first() is not None
        cf = (await s.execute(select(ContentFeature))).scalar_one()
        assert cf.feature_schema_version == "1.0" and cf.cta_count >= 2
        pts = (await s.execute(select(VideoRetentionPoint).order_by(VideoRetentionPoint.time_ratio))).scalars().all()
        assert len(pts) == 3 and pts[1].audience_watch_ratio == 0.6 and pts[1].absolute_time_seconds == pytest.approx(0.5 * 542, abs=0.01)

    calls = len([c for c in respx.calls if "chat/completions" in str(c.request.url)])
    again = (await api.get(f"/api/video/{VIDEO_ID}/report")).json()
    assert again["cached"] is True and len([c for c in respx.calls if "chat/completions" in str(c.request.url)]) == calls  # no new Groq call

    # ML handoff: real data only
    ml = (await api.get(f"/api/video/{VIDEO_ID}/ml-input")).json()
    assert ml["feature_schema_version"] == "1.0" and ml["retention"]["time_ratio"] == [0.01, 0.5, 0.99]
    assert ml["audio_features"] == {} and ml["visual_features"] == {} and "hook_latency_seconds" in ml["transcript_features"]


@respx.mock
async def test_video_report_without_transcript_or_groq_does_not_fail(api, monkeypatch):
    await ready(api)
    monkeypatch.setenv("GROQ_API_KEY", "")
    from app.config import get_settings

    get_settings.cache_clear()
    rep = (await api.get(f"/api/video/{VIDEO_ID}/report")).json()
    assert rep["transcript"]["available"] is False and rep["transcript"]["message"] == "Transcript unavailable for this video."
    assert rep["features"] is None and rep["retention"]["available"] is True
    assert rep["groq"]["available"] is False and rep["groq"]["reason"] == "NO_TRANSCRIPT"


@respx.mock
async def test_groq_failure_degrades_gracefully(api):
    await ready(api)
    respx.post(f"{GROQ}/chat/completions").mock(return_value=httpx.Response(429, json={}))
    await api.post(f"/api/video/{VIDEO_ID}/transcript/upload", json={"format": "srt", "content": SRT})
    rep = (await api.get(f"/api/video/{VIDEO_ID}/report")).json()
    assert rep["groq"] == {"available": False, "reason": "GROQ_RATE_LIMITED", "message": "Groq is rate limiting requests. Please retry in a moment."}
    assert rep["features"] is not None  # deterministic analysis still delivered


@respx.mock
async def test_channel_report_aggregation_and_groq(api):
    await ready(api)
    respx.post(f"{GROQ}/chat/completions").mock(side_effect=groq_responder)
    await api.post(f"/api/video/{VIDEO_ID}/transcript/upload", json={"format": "srt", "content": SRT})
    r = (await api.get("/api/channel/report?start_date=2026-09-01&end_date=2026-09-28")).json()
    o = r["overview"]
    assert o["videos_analyzed"] == 1 and o["videos_in_library"] == 1 and o["total_views"] == 1000 and o["net_subscribers"] == 8
    assert o["average_video_length_seconds"] == 542 and o["median_views_per_video"] == 1000
    assert r["content_patterns"]["transcript_insights"]["videos_with_transcripts"] == 1
    assert r["content_patterns"]["formats"] and r["note"].startswith("Observed associations")
    assert r["groq"]["available"] and r["groq"]["report"]["summary"].startswith("Channel summary")
    assert (await api.get("/api/channel/report?start_date=2026-09-01&end_date=2026-09-28")).json()["cached"] is True
    pats = (await api.get("/api/content-patterns?start_date=2026-09-01&end_date=2026-09-28")).json()
    assert pats["formats"] and "performance_patterns" in pats


@respx.mock
async def test_channel_report_requires_login_and_sync(api):
    assert (await api.get("/api/channel/report")).status_code == 401
    mock_creator_apis()
    await do_login(api)  # logged in but never synced -> no videos
    r = await api.get("/api/channel/report?start_date=2026-09-01&end_date=2026-09-28")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NO_VIDEOS"


@respx.mock
async def test_benchmark_endpoint(api):
    trend_service._VIDEO_MEMO.clear()
    await ready(api)
    mock_search_and_videos()
    r = await api.get("/api/channel/benchmark?genre=Technology&subgenre=AI Tools&region=IN&language=en&time_window=30d"
                      "&start_date=2026-07-01&end_date=2026-09-28")
    assert r.status_code == 200, r.text
    b = r.json()
    # 8 public videos < the 10-video minimum: the comparison is still returned but flagged, with a caution message
    assert b["status"] == "insufficient_sample" and b["genre_sample_size"] == 8 and "treat comparisons with caution" in b["message"]
    by = {m["metric"]: m for m in b["metrics"]}
    assert by["Video length"]["channel"] == 542 and by["Video length"]["genre"] == 480
    assert by["Average view percentage"]["genre"] is None and "unavailable" in by["Average view percentage"]["statement"]
    assert "winner" not in json.dumps(b).lower() and "score" not in json.dumps(b["metrics"]).lower()
    assert b["note"].startswith("Genre values come from a sample")


@respx.mock
async def test_trend_ai_summary_optional(api):
    trend_service._VIDEO_MEMO.clear()
    mock_search_and_videos()
    respx.post(f"{GROQ}/chat/completions").mock(side_effect=groq_responder)
    r = (await api.get("/api/genres/Technology/trends?subgenre=AI Tools&region=IN&include_ai=true")).json()
    assert r["ai_summary"]["available"] and r["ai_summary"]["report"]["caveats"] == ["sample only"]
