"""Channel / video reports, transcripts, content patterns, benchmark (creator login required)."""
from datetime import date

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from app.deps import CreatorContext, creator_context
from app.repositories import intel_repository as repo
from app.schemas.ml import MLInput, MLPredictRequest
from app.schemas.transcript import TranscriptUpload
from app.errors import AppError
from app.services import ml_registry, benchmark_service, channel_report_service, ml_explain_service, transcript_service as ts, video_report_service
from app.services.ml_service import PredictionService, build_ml_input, get_prediction_service
from app.services.youtube_analytics_service import AnalyticsService
from app.services.feature_service import analyze_and_store
from app.services.groq_service import GroqService, get_groq_service
from app.services.youtube_analytics_service import validate_range
from app.services.youtube_client import YouTubeClient

router = APIRouter(tags=["intelligence"])


@router.get("/api/channel/report")
async def channel_report(
    start_date: date | None = None, end_date: date | None = None, refresh: bool = False,
    ctx: CreatorContext = Depends(creator_context), groq: GroqService = Depends(get_groq_service),
):
    start, end = validate_range(start_date, end_date, default_days=90)
    return await channel_report_service.build_report(ctx, start, end, groq, refresh)


@router.get("/api/content-patterns")
async def content_patterns(
    start_date: date | None = None, end_date: date | None = None,
    ctx: CreatorContext = Depends(creator_context),
):
    start, end = validate_range(start_date, end_date, default_days=90)
    data = await channel_report_service.load_dataset(ctx, start, end)
    return {"date_range": {"start": str(start), "end": str(end)}, **channel_report_service.build_patterns(data),
            "performance_patterns": channel_report_service._observations(data)}


@router.get("/api/video/{video_id}/report")
async def video_report(
    video_id: str, refresh: bool = False,
    ctx: CreatorContext = Depends(creator_context), groq: GroqService = Depends(get_groq_service),
):
    return await video_report_service.build_report(ctx, video_id, groq, refresh)


@router.get("/api/video/{video_id}/transcript")
async def get_transcript(video_id: str, ctx: CreatorContext = Depends(creator_context)):
    video = await video_report_service.owned_video(ctx, video_id)
    return await video_report_service.get_transcript_state(ctx, video)


@router.post("/api/video/{video_id}/transcript/upload")
async def upload_transcript(video_id: str, body: TranscriptUpload, ctx: CreatorContext = Depends(creator_context)):
    """Accepts pasted/uploaded TXT, SRT or VTT text and normalizes it into the internal transcript schema."""
    video = await video_report_service.owned_video(ctx, video_id)
    data = ts.UploadedTranscriptProvider().parse(body.format, body.content, body.language, video.duration_seconds)
    await repo.save_transcript(ctx.session, video.id, data)
    await analyze_and_store(ctx.session, video, data.segments, data.language)
    await ctx.session.commit()
    return await video_report_service.get_transcript_state(ctx, video, try_captions=False)


@router.post("/api/video/{video_id}/transcript/transcribe")
async def transcribe(
    video_id: str, file: UploadFile = File(...), language: str | None = Form(None),
    ctx: CreatorContext = Depends(creator_context), groq: GroqService = Depends(get_groq_service),
):
    """User-supplied audio -> Groq Whisper (verbose_json, segment timestamps). Language auto-detected when omitted."""
    video = await video_report_service.owned_video(ctx, video_id)
    audio = await file.read()
    data = await ts.GroqWhisperProvider(groq).transcribe(audio, file.filename or "audio", language or None)
    await repo.save_transcript(ctx.session, video.id, data)
    await analyze_and_store(ctx.session, video, data.segments, data.language)
    await ctx.session.commit()
    return await video_report_service.get_transcript_state(ctx, video, try_captions=False)


@router.get("/api/video/{video_id}/ml-input", response_model=MLInput)
async def ml_input(video_id: str, ctx: CreatorContext = Depends(creator_context), groq: GroqService = Depends(get_groq_service)):
    """The future model's input contract, filled with real data only (for the ML team's adapter)."""
    return build_ml_input(await video_report_service.build_report(ctx, video_id, groq))


@router.get("/api/video/{video_id}/prediction")
async def video_prediction(
    video_id: str, include_ai: bool = False, ctx: CreatorContext = Depends(creator_context),
    service: PredictionService = Depends(get_prediction_service), groq: GroqService = Depends(get_groq_service),
):
    """ML-predicted retention for one of the creator's videos next to the ACTUAL YouTube retention (when available).
    Predicted and observed data are returned separately and must be displayed separately."""
    video = await video_report_service.owned_video(ctx, video_id)
    transcript = await video_report_service.get_transcript_state(ctx, video)
    if not transcript["available"]:
        return {"available": False, "reason": "NO_TRANSCRIPT", "message": transcript["message"], "options": transcript["options"]}
    segments = [dict(segment_id=s["segment_index"], start=s["start_seconds"], end=s["end_seconds"], text=s["text"]) for s in transcript["segments"]]
    request = MLPredictRequest(video_id=video_id, video=dict(title=video.title, description=video.description or "", duration_seconds=video.duration_seconds),
                               transcript=dict(segments=segments))
    prediction = await service.predict(request)
    await ml_registry.record_prediction(ctx.session, video.id, segments, prediction)  # PredictionHistory (feedback loop)

    actual: dict = {"available": False, "points": [], "note": "Actual YouTube retention is not available for this video yet."}
    try:
        svc = AnalyticsService(ctx.session, ctx.user.id, ctx.channel.youtube_channel_id, ctx.access_token)
        start, end = validate_range(video.published_at.date() if video.published_at else None, None)
        pts, _, _ = await svc.retention(video_id, start, end)
        if pts:
            actual = {"available": True, "note": "Observed YouTube audienceWatchRatio x 100 (can exceed 100 with re-watches).",
                      "points": [dict(time_ratio=p.time_ratio, value=(p.audience_watch_ratio or 0) * 100) for p in pts]}
    except Exception:  # noqa: BLE001 - observed data is optional here
        pass
    out = {"available": True, "prediction": prediction, "actual": actual}
    if actual["available"]:  # prediction vs actual -> error + labelled real example
        try:
            out["feedback"] = await ml_registry.record_feedback(ctx.session, video.id, actual["points"])
        except AppError:
            pass
    if include_ai:
        out["groq"] = await ml_explain_service.explain(groq, prediction, segments, video.title)
    return out


@router.get("/api/channel/benchmark")
async def benchmark(
    genre: str, subgenre: str | None = None, language: str | None = None, region: str | None = None,
    time_window: str = "30d", start_date: date | None = None, end_date: date | None = None, refresh: bool = False,
    ctx: CreatorContext = Depends(creator_context),
):
    return await benchmark_service.build_benchmark(
        ctx, YouTubeClient(), genre, subgenre, language, region, time_window, start_date, end_date, refresh
    )
