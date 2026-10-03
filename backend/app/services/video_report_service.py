"""Video Intelligence: combines metadata, YouTube Analytics, observed retention and transcript features.
Observed drop-offs are linked to the transcript text. Nothing here is a prediction."""
import logging
from datetime import date, datetime, timezone

from app.deps import CreatorContext
from app.errors import AppError
from app.models import Video
from app.prompts import build_section_label_prompt, build_video_report_prompt
from app.repositories import intel_repository as repo
from app.repositories import video_repository
from app.schemas.reports import GroqVideoReport, SectionLabels
from app.schemas.transcript import SegmentIn
from app.services import transcript_service as ts
from app.services.feature_service import analyze_and_store
from app.services.groq_service import GroqService
from app.services.transcript_analysis_service import TranscriptAnalysis, segments_at
from app.services.youtube_analytics_service import AnalyticsService, observed_drop_offs, validate_range
from app.services.youtube_client import YouTubeClient
from app.utils.youtube import is_valid_video_id

logger = logging.getLogger("retention.video_report")
SECTION_SECONDS = 30.0


async def owned_video(ctx: CreatorContext, video_id: str) -> Video:
    if not is_valid_video_id(video_id):
        raise AppError("INVALID_URL", "The video ID is malformed.", 400)
    v = await video_repository.get_video_by_yt_id(ctx.session, ctx.channel.youtube_channel_id, video_id)
    if v is None:
        raise AppError("VIDEO_NOT_FOUND", "That video isn't in your synced library. Try syncing first.", 404)
    return v


# ------------------------------------------------------------------ transcript access
async def get_transcript_state(ctx: CreatorContext, video: Video, try_captions: bool = True) -> dict:
    """Returns the stored transcript (trying the authorized caption provider once if enabled) or an
    explicit 'unavailable' state with the upload options. Never raises for a missing transcript."""
    stored = await repo.get_transcript(ctx.session, video.id)
    if stored is None and try_captions:
        data = await ts.YouTubeCaptionProvider(YouTubeClient(access_token=ctx.access_token)).fetch(video.youtube_video_id)
        if data:
            await repo.save_transcript(ctx.session, video.id, data)
            await analyze_and_store(ctx.session, video, data.segments, data.language)
            await ctx.session.commit()
            stored = await repo.get_transcript(ctx.session, video.id)
    if stored is None:
        return {"available": False, "video_id": video.youtube_video_id, "segments": [],
                "message": ts.UNAVAILABLE_MESSAGE, "options": ts.UNAVAILABLE_OPTIONS}
    tr, segs = stored
    return {
        "available": True, "video_id": video.youtube_video_id, "transcript_id": str(tr.id), "provider": tr.provider,
        "language": tr.language, "duration_seconds": tr.duration_seconds, "status": tr.status,
        "timestamps_estimated": tr.status == "ready_estimated_timestamps",
        "segments": [s.model_dump() for s in segs], "created_at": tr.created_at.isoformat() if tr.created_at else None,
    }


# ------------------------------------------------------------------ pure helpers
def link_drop_offs(drops, analysis: TranscriptAnalysis | None) -> list[dict]:
    out = []
    for d in drops:
        item = d.model_dump()
        item["transcript"] = []
        if analysis and d.from_seconds is not None and d.to_seconds is not None:
            item["transcript"] = [{"start": s.start, "end": s.end, "text": s.text} for s in segments_at(analysis.segments, d.from_seconds, d.to_seconds)][:4]
        out.append(item)
    return out


def sections(segs: list[SegmentIn]) -> list[dict]:
    out: list[dict] = []
    cur: list[SegmentIn] = []
    for s in sorted(segs, key=lambda x: x.start_seconds):
        if cur and s.end_seconds - cur[0].start_seconds > SECTION_SECONDS:
            out.append(_section(len(out), cur))
            cur = []
        cur.append(s)
    if cur:
        out.append(_section(len(out), cur))
    return out


def _section(i: int, segs: list[SegmentIn]) -> dict:
    return {"index": i, "start": segs[0].start_seconds, "end": segs[-1].end_seconds, "text": " ".join(x.text for x in segs)[:400]}


def deterministic_experiments(analysis: TranscriptAnalysis | None, drops: list[dict]) -> list[dict]:
    """Evidence-based suggestions that need no model. Observation -> interpretation -> recommendation."""
    out: list[dict] = []
    if analysis:
        h, p = analysis.hook_latency_seconds, analysis.promise_gap_seconds
        if h is not None and h > 20:
            out.append({"observation": f"The first hook-like segment starts at {h:.0f}s.",
                        "interpretation": "A longer opening before the first hook means viewers wait longer before a reason to stay.",
                        "recommendation": "Consider testing an opening where the first concrete payoff appears earlier."})
        if p is not None and p > 30:
            out.append({"observation": f"Words from the title first cluster in the transcript at {p:.0f}s.",
                        "interpretation": "The title's promise starts to be addressed after a long lead-in (a content-structure feature, not a measured cause of drop-off).",
                        "recommendation": "Consider testing an earlier statement of what the video delivers."})
        if analysis.repeated_ideas:
            r = analysis.repeated_ideas[0]
            out.append({"observation": f"{len(analysis.repeated_ideas)} segment(s) closely repeat earlier wording, e.g. {r.start:.0f}-{r.end:.0f}s (similarity {r.similarity}).",
                        "interpretation": "Repeated explanations lower information density in those spans.",
                        "recommendation": "Consider compressing or cutting the repeated explanation in an edit and comparing the result."})
        early_cta = next((c for c in analysis.ctas if c.start < 60 and c.type in ("subscribe", "like", "comment")), None)
        if early_cta:
            out.append({"observation": f"A {early_cta.type} call-to-action appears at {early_cta.start:.0f}s.",
                        "interpretation": "Asking before delivering value can interrupt the opening.",
                        "recommendation": "Consider testing the CTA after the first payoff."})
    for d in drops[:1]:
        text = (d["transcript"][0]["text"][:120] + "…") if d.get("transcript") else None
        if d.get("from_seconds") is not None:
            out.append({"observation": f"The largest observed decline in audience watching is {d['from_seconds']:.0f}-{d['to_seconds']:.0f}s "
                                       f"(−{d['drop'] * 100:.1f} points)." + (f" The transcript there says: “{text}”" if text else ""),
                        "interpretation": "Content at this point coincides with the biggest audience change; the data doesn't show why.",
                        "recommendation": "Consider testing a tighter or re-ordered version of this section."})
    return out


# ------------------------------------------------------------------ Groq steps (optional)
async def label_sections(groq: GroqService, title: str, secs: list[dict]) -> dict[int, dict]:
    if not groq.configured or not secs:
        return {}
    try:
        system, user = build_section_label_prompt(title, [{"index": s["index"], "start": s["start"], "end": s["end"], "text": s["text"]} for s in secs[:40]])
        res = await groq.chat_json(system, user, SectionLabels, max_tokens=2000)
        return {s.index: {"topic": s.topic, "summary": s.summary} for s in res.sections}
    except AppError as exc:
        logger.info("Section labelling skipped: %s", exc.code)
        return {}


async def groq_section(groq: GroqService, evidence: dict) -> dict:
    if not groq.configured:
        return {"available": False, "reason": "GROQ_NOT_CONFIGURED", "message": "AI review unavailable: GROQ_API_KEY is not set on the server."}
    system, user = build_video_report_prompt(evidence)
    try:
        return {"available": True, "report": (await groq.chat_json(system, user, GroqVideoReport)).model_dump()}
    except AppError as exc:
        return {"available": False, "reason": exc.code, "message": exc.message}


# ------------------------------------------------------------------ main entry
async def build_report(ctx: CreatorContext, video_id: str, groq: GroqService, refresh: bool = False) -> dict:
    video = await owned_video(ctx, video_id)
    if not refresh:
        stored = await repo.get_video_report(ctx.session, video.id)
        if stored:
            rep = dict(stored.structured_report_json)
            if rep.get("groq", {}).get("available") or not groq.configured:
                rep["cached"] = True
                return rep

    svc = AnalyticsService(ctx.session, ctx.user.id, ctx.channel.youtube_channel_id, ctx.access_token)
    start, end = validate_range(video.published_at.date() if video.published_at else date(2005, 2, 14), None)
    metrics, _, _ = await svc.video_detail(video_id, start, end, refresh)

    # observed retention (raw), stored in video_retention_points
    retention: dict = {"available": False, "points": [], "observed_drop_offs": [], "message": None}
    drops = []
    try:
        points, _, _ = await svc.retention(video_id, start, end, refresh)
        if points:
            await repo.replace_retention_points(ctx.session, video.id, video.duration_seconds, points)
            drops = observed_drop_offs(points, video.duration_seconds)
            retention.update(available=True, points=[p.model_dump() for p in points])
        else:
            retention["message"] = "YouTube has no audience retention data for this video yet."
    except AppError as exc:
        retention["message"] = exc.message

    transcript = await get_transcript_state(ctx, video)
    analysis: TranscriptAnalysis | None = None
    segs: list[SegmentIn] = []
    if transcript["available"]:
        segs = [SegmentIn(**s) for s in transcript["segments"]]
        analysis, _ = await analyze_and_store(ctx.session, video, segs, transcript["language"])
        secs = sections(segs)
        labels = await label_sections(groq, video.title, secs)
        for sec in secs:
            sec.update(labels.get(sec["index"], {}))
            for f in analysis.segments:
                if sec["start"] <= f.start <= sec["end"] and sec["index"] in labels:
                    f.topic, f.summary = labels[sec["index"]]["topic"], labels[sec["index"]]["summary"]
    linked = link_drop_offs(drops, analysis)
    retention["observed_drop_offs"] = linked

    experiments = deterministic_experiments(analysis, linked)
    features = analysis.model_dump(mode="json") if analysis else None
    report = {
        "video": {
            "video_id": video.youtube_video_id, "title": video.title, "description": (video.description or "")[:1000],
            "channel": video.channel_title, "published_at": video.published_at.isoformat() if video.published_at else None,
            "duration_seconds": video.duration_seconds, "views": video.view_count, "likes": video.like_count,
            "comments": video.comment_count, "thumbnail_url": video.thumbnail_url, "privacy_status": video.privacy_status,
        },
        "analytics": {"date_range": {"start": str(start), "end": str(end)}, "metrics": metrics.model_dump()},
        "retention": retention,
        "transcript": {k: v for k, v in transcript.items() if k != "segments"},
        "features": features,
        "hook": None if not analysis else {
            "hook_latency_seconds": analysis.hook_latency_seconds, "first_payoff_seconds": analysis.first_payoff_seconds,
            "first_topic_reveal_seconds": analysis.first_topic_reveal_seconds,
        },
        "promise_gap": None if not analysis else {"promise_gap_seconds": analysis.promise_gap_seconds,
                                                  "note": "A content-structure feature; not claimed to cause audience loss."},
        "pacing": None if not analysis else {
            "average_words_per_minute": analysis.average_words_per_minute, "sentences_per_minute": analysis.sentences_per_minute,
            "mean_segment_seconds": analysis.mean_segment_seconds, "topic_transitions": analysis.topic_transitions,
            "silence_rate": None,  # needs audio analysis: Data unavailable
        },
        "repetition": None if not analysis else {"repeated_ideas": [r.model_dump() for r in analysis.repeated_ideas], "repetition_score": analysis.repetition_score},
        "cta": None if not analysis else {"ctas": [c.model_dump() for c in analysis.ctas]},
        "experiments": experiments,
        "predicted_retention": {"available": False, "message": "ML model not connected."},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cached": False,
    }

    if analysis:
        evidence = {
            "video": {k: report["video"][k] for k in ("title", "duration_seconds", "views", "likes", "comments", "published_at")},
            "analytics": report["analytics"]["metrics"],
            "observed_drop_offs": [{"from_s": d["from_seconds"], "to_s": d["to_seconds"], "drop_points": round(d["drop"] * 100, 1),
                                    "transcript": [t["text"][:160] for t in d["transcript"][:2]]} for d in linked],
            "hook": report["hook"], "promise_gap_seconds": analysis.promise_gap_seconds, "pacing": report["pacing"],
            "repeated_ideas": [r.model_dump() for r in analysis.repeated_ideas][:5],
            "ctas": [c.model_dump() for c in analysis.ctas][:6],
            "sections": [{"start": s["start"], "end": s["end"], "topic": s.get("topic"), "summary": s.get("summary") or s["text"][:160]} for s in secs[:30]],
        }
        report["groq"] = await groq_section(groq, evidence)
    else:
        report["groq"] = {"available": False, "reason": "NO_TRANSCRIPT",
                          "message": "AI review needs a transcript. Upload a transcript or audio to enable it."}

    await repo.save_video_report(ctx.session, video.id, report)
    await ctx.session.commit()
    return report
