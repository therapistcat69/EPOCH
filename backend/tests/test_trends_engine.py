from datetime import datetime, timedelta, timezone

import httpx
import respx

from app.services import nlp
from app.services.content_patterns import derive_title_patterns, detect_format, format_distribution, structural_features
from app.services.trend_service import VideoSample, build_topics, compute_momentum, recent_growth
from app.services import trend_service
from app.services.benchmark_service import compare_distribution, compare_rows

BASE = "https://www.googleapis.com/youtube/v3"
NOW = datetime.now(timezone.utc)


def V(i, title, views, days_old, likes=10, comments=2, desc="", dur=480):
    return VideoSample(f"vid{i:08d}", title, desc, f"ch{i % 3}", f"Channel {i % 3}", NOW - timedelta(days=days_old), views, likes, comments, dur)


AI = [V(1, "Claude Code vs Cursor AI coding agent comparison", 90000, 2), V(2, "How I built an app with Claude Code coding agent", 120000, 3),
      V(3, "Cursor AI coding agent complete guide", 60000, 5), V(4, "AI coding agent Claude Code tutorial", 30000, 25),
      V(5, "Best AI coding agent Cursor vs Codex", 20000, 28)]
COOK = [V(10, "Easy pasta recipe at home", 4000, 20), V(11, "Pasta recipe for beginners", 3000, 22), V(12, "Quick pasta recipe dinner", 5000, 26)]


def test_tokenize_handles_stopwords_digits_and_hindi():
    assert nlp.tokenize("The 5 best AI tools of 2026") == ["best", "ai", "tools"]
    assert "एआई" in nlp.tokenize("आज हम एआई की बात करेंगे")


def test_clustering_separates_topics():
    toks = [nlp.tokenize(s.title) for s in AI + COOK]
    idf = nlp.build_idf(toks)
    groups = nlp.cluster([nlp.vectorize(t, idf) for t in toks], 0.22)
    sets = sorted(sorted(g) for g in groups)
    assert [0, 1, 2, 3, 4] in sets and [5, 6, 7] in sets


def test_topics_stats_and_names():
    topics = build_topics(AI + COOK, NOW, 30)
    assert len(topics) == 2
    ai = next(t for t in topics if t["sample_size"] == 5)
    assert ai["median_views"] == 60000 and "coding" in ai["topic"].lower() or "agent" in ai["topic"].lower()
    assert ai["common_formats"][0]["format"] in {"Comparison", "Tutorial", "Case Study", "Live Build"}
    assert ai["momentum_version"] == "v1" and 0 <= ai["momentum_score"] <= 1


def test_momentum_is_relative_transparent_and_ordered():
    m = compute_momentum([AI, COOK], NOW, 30)
    assert m[0]["momentum_score"] > m[1]["momentum_score"]
    assert m[0]["label"] in {"HIGH", "MEDIUM"} and m[1]["label"] == "LOW"
    assert all(0 <= x["momentum_score"] <= 1 for x in m)
    # recomputation is deterministic
    assert compute_momentum([AI, COOK], NOW, 30) == m


def test_recent_growth_needs_enough_samples():
    assert recent_growth(AI, NOW, 30) is not None
    assert recent_growth(AI[:2], NOW, 30) is None  # insufficient: null, not invented


def test_format_and_title_patterns_are_data_derived():
    assert detect_format("Claude vs GPT") == "Comparison" and detect_format("How to learn Python") == "Tutorial"
    assert detect_format("random words") is None
    assert "X vs Y" in structural_features("A vs B") and "Starts with a number" in structural_features("5 tools")
    pats = derive_title_patterns([s.title for s in AI], min_count=2)
    assert any("X vs Y" in p["pattern"] for p in pats)
    dist = format_distribution([(s.title, None) for s in AI])
    assert abs(sum(d["share"] for d in dist) - 1) < 0.01


def test_benchmark_compare_rows_neutral_and_honest():
    rows = compare_rows({"average_video_length_seconds": 522, "median_views_recent_uploads": 20000, "average_view_percentage": 48.0,
                         "average_intro_seconds": 29, "uploads_per_month": 6},
                        {"median_duration_seconds": 466, "median_views": 41000})
    by = {r["metric"]: r for r in rows}
    assert by["Video length"]["difference"] == 56 and "longer" in by["Video length"]["statement"]
    assert "Consider testing" in by["Video length"]["suggested_experiment"]
    assert by["Average view percentage"]["genre"] is None and "unavailable" in by["Average view percentage"]["statement"]
    assert by["Average intro (hook latency)"]["difference"] is None  # no public genre data
    assert not any("wrong" in (r["statement"] or "").lower() or "winner" in (r["statement"] or "").lower() for r in rows)


def test_compare_distribution_merges_names():
    out = compare_distribution([{"format": "Tutorial", "share": 0.6}], [{"format": "Tutorial", "share": 0.3}, {"format": "Review", "share": 0.2}], "format")
    assert {o["name"] for o in out} == {"Tutorial", "Review"}
    assert next(o for o in out if o["name"] == "Review")["channel_share"] == 0.0


# ---------------------------------------------------------------- API + quota caching
def video_item(s: VideoSample):
    return {"id": s.video_id, "snippet": {"publishedAt": s.published_at.strftime("%Y-%m-%dT%H:%M:%SZ"), "channelId": s.channel_id,
            "channelTitle": s.channel_title, "title": s.title, "description": s.description or "desc", "categoryId": "28",
            "thumbnails": {"high": {"url": "https://i.ytimg.com/x.jpg"}}},
            "contentDetails": {"duration": "PT8M"}, "statistics": {"viewCount": str(s.views), "likeCount": str(s.likes), "commentCount": str(s.comments)}}


def mock_search_and_videos():
    samples = AI + COOK
    ids = [s.video_id for s in samples]
    search = respx.get(f"{BASE}/search").mock(return_value=httpx.Response(200, json={"items": [{"id": {"videoId": i}} for i in ids]}))
    videos = respx.get(f"{BASE}/videos").mock(return_value=httpx.Response(200, json={"items": [video_item(s) for s in samples]}))
    return search, videos


@respx.mock
async def test_trends_endpoint_caches_search_results(api):
    trend_service._VIDEO_MEMO.clear()
    search, videos = mock_search_and_videos()
    url = "/api/genres/Technology/trends?subgenre=AI Tools&language=en&region=IN&time_window=30d"
    r1 = (await api.get(url)).json()
    assert r1["sample_size"] == 8 and r1["topics"] and r1["search_calls_made"] == 2 and r1["served_from_cache"] is False
    assert r1["momentum_version"] == "v1" and "not a YouTube trend score" in r1["momentum_note"]
    assert r1["external_signals"] is None and r1["genre_stats"]["average_view_percentage"] is None
    params = search.calls[0].request.url.params
    assert params["regionCode"] == "IN" and params["relevanceLanguage"] == "en" and "publishedAfter" in params and params["type"] == "video"
    first_calls = search.call_count

    r2 = (await api.get(url)).json()  # second request: no new search.list, no new videos.list (memoized)
    assert search.call_count == first_calls and r2["served_from_cache"] is True
    assert videos.call_count == 1
    again = (await api.get(url + "&refresh=true")).json()
    assert again["search_calls_made"] == 2 and search.call_count == first_calls + 2

    usage = (await api.get("/api/system/api-usage")).json()
    assert usage["counters"]["youtube_search_calls"] >= 4 and "not Google Cloud's exact quota" in usage["note"]


@respx.mock
async def test_trend_topic_detail_unknown_genre_and_catalogue(api):
    trend_service._VIDEO_MEMO.clear()
    mock_search_and_videos()
    sel = "genre=Technology&subgenre=AI Tools&region=IN&language=en&time_window=30d"
    top = (await api.get(f"/api/trends?{sel}&include_ai=false")).json()["topics"][0]["topic"]
    d = await api.get(f"/api/trends/{top}?{sel}")
    assert d.status_code == 200 and d.json()["topic"]["example_videos"]
    assert (await api.get("/api/trends/nonexistent-topic?" + sel)).json()["error"]["code"] == "TOPIC_NOT_FOUND"
    assert (await api.get("/api/genres/Underwater/trends")).json()["error"]["code"] == "UNKNOWN_GENRE"
    assert (await api.get("/api/genres/Technology/trends?time_window=5y")).json()["error"]["code"] == "INVALID_TIME_WINDOW"
    cat = (await api.get("/api/genres")).json()
    assert any(g["name"] == "Technology" and "AI Tools" in g["subgenres"] for g in cat["genres"])


@respx.mock
async def test_no_trend_results(api):
    trend_service._VIDEO_MEMO.clear()
    respx.get(f"{BASE}/search").mock(return_value=httpx.Response(200, json={"items": []}))
    r = await api.get("/api/genres/Finance/trends?region=IN&time_window=7d")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NO_TREND_RESULTS"


@respx.mock
async def test_trend_quota_error_is_friendly(api):
    respx.get(f"{BASE}/search").mock(return_value=httpx.Response(403, json={"error": {"errors": [{"reason": "quotaExceeded"}]}}))
    r = await api.get("/api/genres/Gaming/trends?region=IN")
    assert r.status_code == 403 and r.json()["error"]["code"] == "QUOTA_EXCEEDED"
