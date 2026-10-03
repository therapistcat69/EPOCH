"""Genres, Trend Radar and system usage. Public YouTube data via the server's API key; no login needed."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.errors import AppError
from app.prompts import build_trend_report_prompt
from app.schemas.reports import GroqTrendReport
from app.services import genres, usage
from app.services.groq_service import GroqService, get_groq_service
from app.services.trend_service import TrendService
from app.services.youtube_client import YouTubeClient, get_youtube_client

router = APIRouter(tags=["trends"])

_AI_CACHE: dict[tuple, dict] = {}


async def _ai(groq: GroqService, key: tuple, result: dict, refresh: bool) -> dict:
    if not groq.configured:
        return {"available": False, "reason": "GROQ_NOT_CONFIGURED", "message": "AI summary unavailable: GROQ_API_KEY is not set on the server."}
    if key in _AI_CACHE and not refresh:
        return _AI_CACHE[key]
    evidence = {
        "selection": {k: result[k] for k in ("genre", "subgenre", "language", "region", "time_window")},
        "sample_size": result["sample_size"], "momentum_version": result["momentum_version"],
        "topics": [{k: t[k] for k in ("topic", "sample_size", "median_views", "recent_growth", "momentum_label", "common_formats", "common_title_patterns")}
                   for t in result["topics"][:6]],
        "genre_stats": {k: result["genre_stats"][k] for k in ("median_duration_seconds", "median_views", "format_distribution")},
    }
    system, user = build_trend_report_prompt(evidence)
    try:
        out = {"available": True, "report": (await groq.chat_json(system, user, GroqTrendReport)).model_dump()}
        _AI_CACHE[key] = out
        return out
    except AppError as exc:
        return {"available": False, "reason": exc.code, "message": exc.message}


@router.get("/api/genres")
async def list_genres():
    return genres.catalogue()


async def _trends(session, client, groq, genre, subgenre, language, region, time_window, refresh, include_ai):
    result = await TrendService(session, client).discover(genre, subgenre, language, region, time_window, refresh)
    if include_ai:
        key = (result["genre"], result["subgenre"], language, region, time_window)
        result["ai_summary"] = await _ai(groq, key, result, refresh)
    return result


@router.get("/api/genres/{genre}/trends")
async def genre_trends(
    genre: str, subgenre: str | None = None, language: str | None = None, region: str | None = None,
    time_window: str = "30d", refresh: bool = False, include_ai: bool = False,
    session: AsyncSession = Depends(get_session), client: YouTubeClient = Depends(get_youtube_client),
    groq: GroqService = Depends(get_groq_service),
):
    return await _trends(session, client, groq, genre, subgenre, language, region, time_window, refresh, include_ai)


@router.get("/api/trends")
async def trends(
    genre: str, subgenre: str | None = None, language: str | None = None, region: str | None = None,
    time_window: str = "30d", refresh: bool = False, include_ai: bool = False,
    session: AsyncSession = Depends(get_session), client: YouTubeClient = Depends(get_youtube_client),
    groq: GroqService = Depends(get_groq_service),
):
    return await _trends(session, client, groq, genre, subgenre, language, region, time_window, refresh, include_ai)


@router.get("/api/trends/{topic}")
async def trend_topic(
    topic: str, genre: str, subgenre: str | None = None, language: str | None = None, region: str | None = None,
    time_window: str = "30d", session: AsyncSession = Depends(get_session),
    client: YouTubeClient = Depends(get_youtube_client),
):
    """One topic's detail from the (cached) sample for the selection."""
    result = await TrendService(session, client).discover(genre, subgenre, language, region, time_window, False)
    match = next((t for t in result["topics"] if t["topic"].lower() == topic.lower()), None)
    if match is None:
        raise AppError("TOPIC_NOT_FOUND", "That topic isn't in the current sample for this selection.", 404)
    return {"selection": {k: result[k] for k in ("genre", "subgenre", "language", "region", "time_window")},
            "sample_size": result["sample_size"], "topic": match, "momentum_note": result["momentum_note"]}


@router.get("/api/system/api-usage")
async def api_usage():
    return usage.snapshot()
