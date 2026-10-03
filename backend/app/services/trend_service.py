"""Trend engine: official YouTube Data API only (search.list for discovery, videos.list for stats).

search.list is quota-expensive (~100 units) so results are cached in `trend_search_cache` (TTL) and never
re-run per page view. Topics come from TF-IDF clustering of titles/descriptions of the discovered videos.
Everything shown is a RetainAI-derived measurement over a public sample - NOT an official YouTube trend score
and NOT the recommendation algorithm.
"""
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.errors import AppError
from app.repositories import intel_repository as repo
from app.services import genres, nlp
from app.services.content_patterns import derive_title_patterns, detect_format, format_distribution
from app.services.youtube_client import YouTubeClient
from app.services.youtube_service import normalize_video

logger = logging.getLogger("retention.trends")

MOMENTUM_VERSION = "v1"
MIN_TOPIC_SIZE = 3
MIN_SAMPLE_FOR_BENCHMARK = 10
CLUSTER_THRESHOLD = 0.14

# video id -> (stored_at, sample): avoids re-calling videos.list on every request within the TTL
_VIDEO_MEMO: dict[str, tuple[float, "VideoSample"]] = {}


@dataclass
class VideoSample:
    video_id: str
    title: str
    description: str
    channel_id: str | None
    channel_title: str | None
    published_at: datetime | None
    views: int | None
    likes: int | None
    comments: int | None
    duration_seconds: int
    thumbnail_url: str | None = None

    @property
    def engagement_rate(self) -> float | None:
        if not self.views:
            return None
        return ((self.likes or 0) + (self.comments or 0)) / self.views

    def age_days(self, now: datetime) -> float:
        return max((now - self.published_at).total_seconds() / 86400, 1.0) if self.published_at else 1.0

    def views_per_day(self, now: datetime) -> float | None:
        return None if self.views is None else self.views / self.age_days(now)


class ExternalTrendProvider(Protocol):
    """Optional extra signal source (e.g. Google Trends). The app works fully without one."""

    name: str

    async def signals(self, query: str, region: str | None) -> dict | None: ...


class NullTrendProvider:
    name = "none"

    async def signals(self, query: str, region: str | None) -> dict | None:
        return None


def get_external_trend_provider() -> ExternalTrendProvider:
    return NullTrendProvider()


# --------------------------------------------------------------------------- pure analytics
def compute_momentum(
    topic_groups: list[list[VideoSample]], now: datetime, window_days: int
) -> list[dict]:
    """RetainAI Content Momentum Index (formula version v1), relative to the other topics in the sample:

        momentum = normalized_velocity * recency_factor * engagement_factor
        normalized_velocity = median(views per day of the topic's videos) / max over topics
        recency_factor      = 0.5 + 0.5 * share of the topic's videos published in the newest third of the window
        engagement_factor   = 0.5 + 0.5 * median((likes+comments)/views) / max over topics
    Range 0..1. Labels: HIGH >= 0.6, MEDIUM >= 0.3, else LOW.
    """
    stats = []
    for g in topic_groups:
        vpd = [v for v in (s.views_per_day(now) for s in g) if v is not None]
        eng = [e for e in (s.engagement_rate for s in g) if e is not None]
        cutoff = now - timedelta(days=window_days / 3)
        recent = [s for s in g if s.published_at and s.published_at >= cutoff]
        stats.append((nlp.median(vpd) or 0.0, nlp.median(eng) or 0.0, len(recent) / len(g)))
    max_v = max((s[0] for s in stats), default=0.0) or 1.0
    max_e = max((s[1] for s in stats), default=0.0) or 1.0
    out = []
    for (velocity, eng, recent_share) in stats:
        score = (velocity / max_v) * (0.5 + 0.5 * recent_share) * (0.5 + 0.5 * (eng / max_e))
        out.append({"momentum_score": round(score, 4), "label": "HIGH" if score >= 0.6 else "MEDIUM" if score >= 0.3 else "LOW",
                    "recent_share": round(recent_share, 3)})
    return out


def recent_growth(group: list[VideoSample], now: datetime, window_days: int) -> float | None:
    """Median views/day of videos in the newest third of the window vs older ones (age-normalized sample statistic)."""
    cutoff = now - timedelta(days=window_days / 3)
    new = [s.views_per_day(now) for s in group if s.published_at and s.published_at >= cutoff and s.views is not None]
    old = [s.views_per_day(now) for s in group if s.published_at and s.published_at < cutoff and s.views is not None]
    if len(new) < 2 or len(old) < 2:
        return None
    m_old = nlp.median(old)
    return None if not m_old else round(nlp.median(new) / m_old - 1, 4)


def build_topics(samples: list[VideoSample], now: datetime, window_days: int) -> list[dict]:
    # titles carry the topic signal; descriptions are mostly boilerplate, so they only get a small weight
    token_lists = [nlp.tokenize(f"{s.title} {s.title} {s.title} {nlp.strip_urls(s.description)[:120]}") for s in samples]
    idf = nlp.build_idf(token_lists)
    vecs = [nlp.vectorize(t, idf) for t in token_lists]
    groups_idx = [g for g in nlp.cluster(vecs, CLUSTER_THRESHOLD) if len(g) >= MIN_TOPIC_SIZE]
    groups = [[samples[i] for i in g] for g in groups_idx]
    momentum = compute_momentum(groups, now, window_days)
    topics = []
    for g_idx, group, m in zip(groups_idx, groups, momentum):
        views = [s.views for s in group if s.views is not None]
        eng = [e for e in (s.engagement_rate for s in group) if e is not None]
        formats = format_distribution([(s.title, s.description) for s in group])
        name_terms = nlp.top_terms([token_lists[i] for i in g_idx], k=3)
        top = sorted(group, key=lambda s: s.views or 0, reverse=True)
        chans: dict[str, int] = {}
        for s in group:
            if s.channel_title:
                chans[s.channel_title] = chans.get(s.channel_title, 0) + 1
        topics.append({
            "topic": " ".join(name_terms).title() or "Misc", "sample_size": len(group),
            "median_views": nlp.median(views), "average_views": nlp.mean(views),
            "engagement_rate": nlp.median(eng), "recent_growth": recent_growth(group, now, window_days),
            "momentum_score": m["momentum_score"], "momentum_label": m["label"], "momentum_version": MOMENTUM_VERSION,
            "common_formats": [f for f in formats if f["format"] != "Other / unclassified"][:3],
            "common_title_patterns": derive_title_patterns([s.title for s in group], min_count=2, top=3),
            "example_videos": [{"video_id": s.video_id, "title": s.title, "views": s.views, "channel": s.channel_title} for s in top[:3]],
            "top_channels": sorted(chans, key=chans.get, reverse=True)[:3],
        })
    return sorted(topics, key=lambda t: t["momentum_score"], reverse=True)


def genre_stats(samples: list[VideoSample], topics: list[dict]) -> dict:
    titles = [s.title for s in samples]
    total_topic = sum(t["sample_size"] for t in topics) or 1
    return {
        "sample_size": len(samples),
        "unique_channels": len({s.channel_id for s in samples if s.channel_id}),
        "median_duration_seconds": nlp.median([s.duration_seconds for s in samples if s.duration_seconds]),
        "median_views": nlp.median([s.views for s in samples if s.views is not None]),
        "average_views": nlp.mean([s.views for s in samples if s.views is not None]),
        "median_engagement_rate": nlp.median([e for e in (s.engagement_rate for s in samples) if e is not None]),
        "format_distribution": format_distribution([(s.title, s.description) for s in samples]),
        "title_patterns": derive_title_patterns(titles, min_count=2, top=8),
        "topic_distribution": [{"topic": t["topic"], "share": round(t["sample_size"] / total_topic, 3)} for t in topics],
        # public data cannot provide these; shown as "Data unavailable" rather than invented
        "average_view_percentage": None,
        "average_intro_seconds": None,
    }


def opportunities(topics: list[dict]) -> list[dict]:
    """Deterministic, evidence-first opportunity statements (no model involved)."""
    out = []
    for t in topics[:3]:
        if t["momentum_label"] == "LOW":
            continue
        fmt = t["common_formats"][0]["format"] if t["common_formats"] else None
        ev = [f"{t['sample_size']} videos analyzed", f"median views {int(t['median_views'] or 0):,}"]
        if t["recent_growth"] is not None:
            ev.append(f"newer uploads' views/day {t['recent_growth']:+.0%} vs older uploads in the sample")
        if fmt:
            ev.append(f"most common format: {fmt}")
        out.append({
            "title": f"{fmt + ' videos on ' if fmt else ''}{t['topic']}",
            "statement": f"Observed public YouTube content in the selected sample shows strong representation of {t['topic']}"
                         f"{' ' + fmt.lower() + ' content' if fmt else ''}.",
            "evidence": ev,
        })
    return out


# --------------------------------------------------------------------------- service
class TrendService:
    def __init__(self, session: AsyncSession, client: YouTubeClient):
        self.session, self.client = session, client
        self.settings = get_settings()

    async def _video_ids(self, genre, sub, language, region, window, queries, window_days, refresh) -> tuple[list[str], int]:
        ids: list[str] = []
        searches = 0
        for q in queries[: self.settings.trend_queries_per_request]:
            hit = None if refresh else await repo.get_trend_query(self.session, genre, sub, language, region, window, q)
            if hit:
                ids += list(hit.video_ids)
                continue
            published_after = (datetime.now(timezone.utc) - timedelta(days=window_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
            params = {"q": q, "publishedAfter": published_after, "order": "viewCount"}
            if region:
                params["regionCode"] = region
            if language:
                params["relevanceLanguage"] = language
            res = await self.client.search(params)
            searches += 1
            found = [i["id"]["videoId"] for i in res.get("items", []) if i.get("id", {}).get("videoId")]
            await repo.put_trend_query(self.session, genre, sub, language, region, window, q, found, self.settings.trend_cache_hours)
            ids += found
        await self.session.commit()
        return list(dict.fromkeys(ids))[:100], searches

    async def _samples(self, ids: list[str]) -> list[VideoSample]:
        ttl = self.settings.trend_cache_hours * 3600
        now_ts = time.time()
        need = [i for i in ids if i not in _VIDEO_MEMO or now_ts - _VIDEO_MEMO[i][0] > ttl]
        for k in range(0, len(need), 50):  # batched videos.list: ~1 unit per call
            raw = await self.client.videos(need[k : k + 50])
            for item in raw.get("items", []):
                v = normalize_video(item)
                _VIDEO_MEMO[v.video_id] = (now_ts, VideoSample(
                    v.video_id, v.title, v.description or "", v.channel.id, v.channel.title, v.published_at,
                    v.statistics.views, v.statistics.likes, v.statistics.comments, v.duration_seconds, v.thumbnail_url,
                ))
        return [_VIDEO_MEMO[i][1] for i in ids if i in _VIDEO_MEMO]

    async def discover(self, genre: str, subgenre: str | None, language: str | None, region: str | None,
                       window: str = "30d", refresh: bool = False) -> dict:
        try:
            g, sub, queries = genres.resolve(genre, subgenre)
        except KeyError:
            raise AppError("UNKNOWN_GENRE", f"Unknown genre '{genre}'. See /api/genres.", 404)
        if window not in genres.TIME_WINDOWS:
            raise AppError("INVALID_TIME_WINDOW", f"time_window must be one of {', '.join(genres.TIME_WINDOWS)}.", 400)
        window_days = genres.TIME_WINDOWS[window]

        ids, searches = await self._video_ids(g, sub, language, region, window, queries, window_days, refresh)
        samples = await self._samples(ids)
        now = datetime.now(timezone.utc)
        samples = [s for s in samples if s.published_at and (now - s.published_at).days <= window_days + 1]
        if len(samples) < MIN_TOPIC_SIZE:
            raise AppError("NO_TREND_RESULTS", "Not enough recent public videos were found for that selection. Try a wider time range or another subgenre.", 404)

        topics = build_topics(samples, now, window_days)
        stats = genre_stats(samples, topics)
        await repo.replace_trend_topics(self.session, g, sub, language, region, window, topics)
        await repo.save_genre_benchmark(self.session, g, sub, language, region, window, len(samples), stats)
        await self.session.commit()
        return {
            "genre": g, "subgenre": sub, "language": language, "region": region, "time_window": window,
            "generated_at": now.isoformat(), "sample_size": len(samples), "queries": queries[: self.settings.trend_queries_per_request],
            "search_calls_made": searches, "served_from_cache": searches == 0,
            "momentum_version": MOMENTUM_VERSION,
            "momentum_note": "RetainAI Content Momentum Index: a transparent, sample-relative measure (not a YouTube trend score).",
            "topics": topics, "genre_stats": stats, "opportunities": opportunities(topics),
            "external_signals": None,  # ExternalTrendProvider (e.g. Google Trends) is optional and not configured
        }
