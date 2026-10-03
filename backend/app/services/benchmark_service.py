"""Channel-vs-genre benchmarking. Neutral measurements and experiment suggestions: no winner score,
no claim that a difference is wrong or causal. Metrics unavailable from public data are reported as such."""
from datetime import date, datetime, timedelta, timezone

from app.deps import CreatorContext
from app.services import nlp
from app.services.channel_report_service import ChannelVideo, load_dataset, upload_frequency_per_month
from app.services.content_patterns import derive_title_patterns, format_distribution, structural_features
from app.services.genres import TIME_WINDOWS
from app.services.trend_service import MIN_SAMPLE_FOR_BENCHMARK, TrendService
from app.services.youtube_analytics_service import validate_range
from app.services.youtube_client import YouTubeClient


def _fmt_sec(sec: float | None) -> str:
    if sec is None:
        return "Data unavailable"
    s = int(round(sec))
    return f"{s // 60}:{s % 60:02d}"


def compare_rows(channel: dict, genre: dict) -> list[dict]:
    """Pure comparison of the two sides. Each row carries both values, the difference and a plain statement."""
    rows: list[dict] = []

    def add(metric: str, unit: str, c, g, statement: str | None = None, experiment: str | None = None):
        diff = (c - g) if c is not None and g is not None else None
        rows.append({"metric": metric, "unit": unit, "channel": c, "genre": g, "difference": diff,
                     "statement": statement if diff is not None else "Data unavailable for one or both sides.",
                     "suggested_experiment": experiment if diff is not None else None})

    c_len, g_len = channel.get("average_video_length_seconds"), genre.get("median_duration_seconds")
    diff = None if c_len is None or g_len is None else c_len - g_len
    add("Video length", "seconds", c_len, g_len,
        f"Your channel's average video length is {_fmt_sec(abs(diff)) if diff is not None else ''} "
        f"{'longer' if (diff or 0) > 0 else 'shorter'} than the genre sample's median ({_fmt_sec(g_len)})." if diff is not None else None,
        "Consider testing a different video length in an upcoming video and comparing average view percentage.")
    c_v, g_v = channel.get("median_views_recent_uploads"), genre.get("median_views")
    add("Median views (recent uploads)", "views", c_v, g_v,
        f"Your recent uploads' median views ({int(c_v or 0):,}) vs the genre sample median ({int(g_v or 0):,}). "
        "The sample is public search results sorted by views, so it leans toward higher-performing videos." if c_v is not None and g_v is not None else None)
    add("Average view percentage", "percent", channel.get("average_view_percentage"), None)  # public data can't supply a genre value
    add("Average intro (hook latency)", "seconds", channel.get("average_intro_seconds"), genre.get("average_intro_seconds"))
    add("Upload frequency", "per month", channel.get("uploads_per_month"), None)
    return rows


def compare_distribution(channel_items: list[dict], genre_items: list[dict], key: str) -> list[dict]:
    names = list(dict.fromkeys([i[key] for i in channel_items] + [i[key] for i in genre_items]))
    c = {i[key]: i["share"] for i in channel_items}
    g = {i[key]: i["share"] for i in genre_items}
    return [{"name": n, "channel_share": c.get(n, 0.0), "genre_share": g.get(n, 0.0)} for n in names][:12]


async def build_benchmark(ctx: CreatorContext, client: YouTubeClient, genre: str, subgenre: str | None, language: str | None,
                          region: str | None, window: str, start: date | None, end: date | None, refresh: bool) -> dict:
    start, end = validate_range(start, end, default_days=90)
    data: list[ChannelVideo] = await load_dataset(ctx, start, end, refresh)
    trend = await TrendService(ctx.session, client).discover(genre, subgenre, language, region, window, refresh)
    gstats = trend["genre_stats"]

    window_days = TIME_WINDOWS[window]
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    def aware(dt: datetime) -> datetime:  # SQLite returns naive datetimes; Postgres returns aware ones
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    recent = [c for c in data if c.row.published_at and aware(c.row.published_at) >= cutoff and c.row.view_count is not None]
    feats = [c.features for c in data if c.features and c.features.hook_latency_seconds is not None]
    pct = [c.metrics.average_view_percentage for c in data if c.metrics and c.metrics.average_view_percentage is not None]
    titles = [c.row.title for c in data]
    channel = {
        "videos_in_library": len(data),
        "average_video_length_seconds": nlp.mean([c.row.duration_seconds for c in data if c.row.duration_seconds]),
        "median_views_recent_uploads": nlp.median([c.row.view_count for c in recent]) if len(recent) >= 3 else None,
        "recent_uploads_count": len(recent),
        "average_view_percentage": nlp.mean(pct),
        "average_intro_seconds": nlp.mean([f.hook_latency_seconds for f in feats]),
        "videos_with_intro_data": len(feats),
        "uploads_per_month": upload_frequency_per_month(data, start, end),
    }
    insufficient = trend["sample_size"] < MIN_SAMPLE_FOR_BENCHMARK
    ch_formats = format_distribution([(c.row.title, c.row.description) for c in data])
    ch_struct = {}
    for t in titles:
        for f in structural_features(t):
            ch_struct[f] = ch_struct.get(f, 0) + 1
    n = max(len(titles), 1)
    ch_patterns = [{"pattern": k, "share": round(v / n, 3)} for k, v in sorted(ch_struct.items(), key=lambda kv: -kv[1])]
    gen_struct = [p for p in gstats["title_patterns"] if not p["pattern"].startswith("Starts with")]
    return {
        "genre": trend["genre"], "subgenre": trend["subgenre"], "language": language, "region": region, "time_window": window,
        "date_range": {"start": str(start), "end": str(end)},
        "status": "insufficient_sample" if insufficient else "ok",
        "message": f"Only {trend['sample_size']} public videos were found (need {MIN_SAMPLE_FOR_BENCHMARK}); treat comparisons with caution."
        if insufficient else None,
        "genre_sample_size": trend["sample_size"], "channel": channel, "genre_stats": gstats,
        "metrics": compare_rows(channel, gstats),
        "formats": compare_distribution(ch_formats, gstats["format_distribution"], "format"),
        "title_patterns": compare_distribution(ch_patterns, [{"pattern": p["pattern"], "share": p["share"]} for p in gen_struct], "pattern"),
        "topics": {"channel": [], "genre": gstats["topic_distribution"]},
        "note": "Genre values come from a sample of recent public YouTube videos found via search (not all of YouTube). "
                "Differences are observations, not judgements.",
    }
