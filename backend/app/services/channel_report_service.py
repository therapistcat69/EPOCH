"""Channel Intelligence: aggregates the creator's analytics + content features, then (optionally) asks Groq
to explain them. All numbers are computed here, deterministically, from YouTube data."""
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import CreatorContext
from app.errors import AppError
from app.models import ContentFeature, Video
from app.prompts import build_channel_report_prompt
from app.repositories import intel_repository as repo
from app.repositories import video_repository
from app.schemas.analytics import Metrics
from app.schemas.reports import GroqChannelReport
from app.services import nlp
from app.services.content_patterns import derive_title_patterns, detect_format, format_distribution, structural_features
from app.services.feature_service import analyze_and_store
from app.services.groq_service import GroqService
from app.services.youtube_analytics_service import AnalyticsService, validate_range

logger = logging.getLogger("retention.channel_report")
MIN_GROUP = 3  # smallest group we'll draw an observation from
MAX_VIDEOS_FOR_PATTERNS = 300


@dataclass
class ChannelVideo:
    row: Video
    metrics: Metrics | None
    features: ContentFeature | None


def _mean_pct(items: list[ChannelVideo]) -> float | None:
    return nlp.mean([c.metrics.average_view_percentage for c in items if c.metrics and c.metrics.average_view_percentage is not None])


def _median_views(items: list[ChannelVideo]) -> float | None:
    return nlp.median([c.metrics.views for c in items if c.metrics and c.metrics.views is not None])


async def load_dataset(ctx: CreatorContext, start: date, end: date, refresh: bool = False) -> list[ChannelVideo]:
    """DB videos + one batched analytics report + stored content features (computed lazily from stored transcripts)."""
    svc = AnalyticsService(ctx.session, ctx.user.id, ctx.channel.youtube_channel_id, ctx.access_token)
    metrics_by_id, _, _ = await svc.videos(start, end, refresh)
    rows = (await video_repository.list_channel_videos(ctx.session, ctx.channel.youtube_channel_id))[:MAX_VIDEOS_FOR_PATTERNS]
    feats = await repo.get_content_features(ctx.session, [r.id for r in rows])
    out: list[ChannelVideo] = []
    for r in rows:
        f = feats.get(r.id)
        if f is None:  # a transcript exists but features weren't computed yet -> compute (cheap, deterministic)
            stored = await repo.get_transcript(ctx.session, r.id)
            if stored:
                _, f = await analyze_and_store(ctx.session, r, stored[1], stored[0].language)
        out.append(ChannelVideo(r, metrics_by_id.get(r.youtube_video_id), f))
    await ctx.session.commit()
    return out


# ------------------------------------------------------------------ deterministic aggregation
def _group_stats(groups: dict[str, list[ChannelVideo]]) -> list[dict]:
    out = []
    for name, items in groups.items():
        with_data = [c for c in items if c.metrics]
        out.append({
            "group": name, "videos": len(items), "videos_with_analytics": len(with_data),
            "median_views": _median_views(items), "average_view_percentage": _mean_pct(items),
        })
    return sorted(out, key=lambda g: -g["videos"])


def _duration_bucket(sec: int | None) -> str | None:
    if sec is None:
        return None
    m = sec / 60
    return "Under 5 min" if m < 5 else "5-10 min" if m < 10 else "10-20 min" if m < 20 else "20+ min"


def _observations(data: list[ChannelVideo]) -> list[dict]:
    """Association statements only (never causal), each with its sample size."""
    obs: list[dict] = []
    with_m = [c for c in data if c.metrics]
    overall_views = _median_views(with_m)
    overall_pct = _mean_pct(with_m)

    def compare(kind: str, groups: dict[str, list[ChannelVideo]], what: str) -> None:
        eligible = {k: v for k, v in groups.items() if len([c for c in v if c.metrics]) >= MIN_GROUP}
        if len(eligible) < 2:
            return
        by_pct = {k: _mean_pct(v) for k, v in eligible.items() if _mean_pct(v) is not None}
        if len(by_pct) >= 2:
            best = max(by_pct, key=by_pct.get)
            obs.append({"kind": kind, "metric": "average_view_percentage", "group": best, "n": len(eligible[best]),
                        "value": round(by_pct[best], 2), "baseline": round(overall_pct, 2) if overall_pct is not None else None,
                        "statement": f"Videos in {what} “{best}” (n={len(eligible[best])}) were associated with the highest average view percentage "
                                     f"in this range ({by_pct[best]:.1f}% vs {overall_pct:.1f}% across analyzed videos)."})
        by_views = {k: _median_views(v) for k, v in eligible.items() if _median_views(v) is not None}
        if len(by_views) >= 2:
            best = max(by_views, key=by_views.get)
            obs.append({"kind": kind, "metric": "median_views", "group": best, "n": len(eligible[best]),
                        "value": by_views[best], "baseline": overall_views,
                        "statement": f"Videos in {what} “{best}” (n={len(eligible[best])}) were associated with the highest median views "
                                     f"in this range ({int(by_views[best]):,} vs {int(overall_views or 0):,} overall)."})

    fmt: dict[str, list[ChannelVideo]] = {}
    dur: dict[str, list[ChannelVideo]] = {}
    intro: dict[str, list[ChannelVideo]] = {}
    for c in data:
        fmt.setdefault(detect_format(c.row.title, c.row.description) or "Other / unclassified", []).append(c)
        b = _duration_bucket(c.row.duration_seconds)
        if b:
            dur.setdefault(b, []).append(c)
        h = c.features.hook_latency_seconds if c.features else None
        if h is not None:
            intro.setdefault("hook within 15s" if h <= 15 else "hook at 16-30s" if h <= 30 else "hook after 30s", []).append(c)
    compare("format", fmt, "format")
    compare("duration", dur, "length bucket")
    compare("intro", intro, "intro group")
    # title structure: with vs without each structural feature
    for feature in {f for c in data for f in structural_features(c.row.title)}:
        has = [c for c in with_m if feature in structural_features(c.row.title)]
        lacks = [c for c in with_m if feature not in structural_features(c.row.title)]
        if len(has) >= MIN_GROUP and len(lacks) >= MIN_GROUP and _median_views(has) is not None and _median_views(lacks) is not None:
            obs.append({"kind": "title_structure", "metric": "median_views", "group": feature, "n": len(has),
                        "value": _median_views(has), "baseline": _median_views(lacks),
                        "statement": f"Titles with the pattern “{feature}” (n={len(has)}) were associated with median views of "
                                     f"{int(_median_views(has)):,} vs {int(_median_views(lacks)):,} for titles without it (n={len(lacks)})."})
    return obs


def build_patterns(data: list[ChannelVideo]) -> dict:
    titles = [c.row.title for c in data]
    token_lists = [nlp.tokenize(f"{c.row.title} {c.row.title} {(c.row.description or '')[:200]}") for c in data]
    topics: list[dict] = []
    if len(data) >= MIN_GROUP:
        idf = nlp.build_idf(token_lists)
        vecs = [nlp.vectorize(t, idf) for t in token_lists]
        for g in nlp.cluster(vecs, 0.2):
            items = [data[i] for i in g]
            if len(items) >= 2:
                topics.append({"topic": " ".join(nlp.top_terms([token_lists[i] for i in g], 3)).title(), "videos": len(items),
                               "videos_with_analytics": len([c for c in items if c.metrics]),
                               "median_views": _median_views(items), "average_view_percentage": _mean_pct(items)})
    topics.sort(key=lambda t: -t["videos"])
    feats = [c.features for c in data if c.features]
    cta_types: dict[str, int] = {}
    themes: dict[str, int] = {}
    for f in feats:
        for c in (f.cta_timestamps or []):
            cta_types[c["type"]] = cta_types.get(c["type"], 0) + 1
        for term in (f.features_json or {}).get("top_terms", []):
            themes[term] = themes.get(term, 0) + 1
    return {
        "topics": topics[:8],
        "formats": format_distribution([(c.row.title, c.row.description) for c in data]),
        "title_patterns": derive_title_patterns(titles, min_count=2, top=6),
        "keywords": nlp.top_terms(token_lists, k=10),
        "common_video_lengths": _group_stats({k: v for k, v in _bucketize(data).items()}),
        "transcript_insights": {
            "videos_with_transcripts": len(feats),
            "average_words_per_minute": nlp.mean([f.average_words_per_minute for f in feats]),
            "average_intro_hook_seconds": nlp.mean([f.hook_latency_seconds for f in feats]),
            "average_promise_gap_seconds": nlp.mean([f.promise_gap_seconds for f in feats]),
            "average_repetition_score": nlp.mean([f.repetition_score for f in feats]),
            "common_cta_types": sorted(cta_types, key=cta_types.get, reverse=True)[:4],
            "recurring_themes": sorted(themes, key=themes.get, reverse=True)[:8],
        },
    }


def _bucketize(data: list[ChannelVideo]) -> dict[str, list[ChannelVideo]]:
    out: dict[str, list[ChannelVideo]] = {}
    for c in data:
        b = _duration_bucket(c.row.duration_seconds)
        if b:
            out.setdefault(b, []).append(c)
    return out


def upload_frequency_per_month(data: list[ChannelVideo], start: date, end: date) -> float | None:
    days = max((end - start).days + 1, 1)
    in_range = [c for c in data if c.row.published_at and start <= c.row.published_at.date() <= end]
    return round(len(in_range) / (days / 30.44), 2) if data else None


async def build_report(ctx: CreatorContext, start: date, end: date, groq: GroqService, refresh: bool = False) -> dict:
    start, end = validate_range(start, end)
    key = (str(start), str(end))
    if not refresh:
        stored = await repo.get_channel_report(ctx.session, ctx.user.id, ctx.channel.youtube_channel_id, *key)
        if stored:
            report = dict(stored.structured_report_json)
            if report.get("groq", {}).get("available") or not groq.configured:
                report["cached"] = True
                return report

    svc = AnalyticsService(ctx.session, ctx.user.id, ctx.channel.youtube_channel_id, ctx.access_token)
    overview, _, _ = await svc.overview(start, end, refresh)
    data = await load_dataset(ctx, start, end, refresh)
    if not data:
        raise AppError("NO_VIDEOS", "No synced videos yet. Click “Sync YouTube Data” first.", 404)
    with_m = [c for c in data if c.metrics]
    durations = [c.row.duration_seconds for c in data if c.row.duration_seconds]
    views = [c.metrics.views for c in with_m if c.metrics.views is not None]

    report = {
        "channel": {"id": ctx.channel.youtube_channel_id, "title": ctx.channel.title},
        "date_range": {"start": str(start), "end": str(end)},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overview": {
            "videos_in_library": len(data), "videos_analyzed": len(with_m),
            "total_views": overview.views, "total_watch_time_minutes": overview.watch_time_minutes,
            "average_view_duration_seconds": overview.average_view_duration_seconds,
            "average_view_percentage": overview.average_view_percentage,
            "subscribers_gained": overview.subscribers_gained, "subscribers_lost": overview.subscribers_lost,
            "net_subscribers": overview.net_subscribers,
            "average_video_length_seconds": nlp.mean(durations),
            "average_views_per_video": nlp.mean(views), "median_views_per_video": nlp.median(views),
            "uploads_per_month": upload_frequency_per_month(data, start, end),
        },
        "content_patterns": build_patterns(data),
        "performance_patterns": _observations(data),
        "note": "Observed associations in your own data. They do not establish causation.",
        "cached": False,
    }
    report["groq"] = await _groq_section(groq, report)
    await repo.save_channel_report(ctx.session, ctx.user.id, ctx.channel.youtube_channel_id, *key, report)
    await ctx.session.commit()
    return report


async def _groq_section(groq: GroqService, report: dict) -> dict:
    if not groq.configured:
        return {"available": False, "reason": "GROQ_NOT_CONFIGURED", "message": "AI report unavailable: GROQ_API_KEY is not set on the server."}
    cp = report["content_patterns"]
    evidence = {
        "date_range": report["date_range"], "overview": report["overview"],
        "top_topics": cp["topics"][:5], "formats": cp["formats"][:5], "title_patterns": cp["title_patterns"],
        "length_buckets": cp["common_video_lengths"], "transcript_insights": cp["transcript_insights"],
        "observed_performance_patterns": [o["statement"] for o in report["performance_patterns"]][:10],
    }
    system, user = build_channel_report_prompt(evidence)
    try:
        result = await groq.chat_json(system, user, GroqChannelReport)
        return {"available": True, "report": result.model_dump()}
    except AppError as exc:
        logger.warning("Channel Groq report failed: %s", exc.code)
        return {"available": False, "reason": exc.code, "message": exc.message}
