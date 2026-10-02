import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.schemas.report import AnalysisReport, AnalysisSummary, AnalyzeRequest
from app.schemas.youtube import NormalizedVideo
from app.services import report_service, youtube_service
from app.services.youtube_client import YouTubeClient, get_youtube_client

router = APIRouter()


@router.get("/api/youtube/video/{video_id}", response_model=NormalizedVideo)
async def get_video(video_id: str, client: YouTubeClient = Depends(get_youtube_client)):
    video, _ = await youtube_service.get_video(client, video_id)
    return video


@router.post("/api/analyze", response_model=AnalysisReport)
async def analyze(
    body: AnalyzeRequest,
    refresh: bool = Query(False, description="Bypass the cache and re-fetch from YouTube"),
    session: AsyncSession = Depends(get_session),
    client: YouTubeClient = Depends(get_youtube_client),
):
    return await report_service.analyze(session, client, body.youtube_url, refresh=refresh)


@router.get("/api/analyses", response_model=list[AnalysisSummary])
async def recent_analyses(
    limit: int = Query(8, ge=1, le=30), session: AsyncSession = Depends(get_session)
):
    return await report_service.recent(session, limit)


@router.get("/api/analyses/{analysis_id}", response_model=AnalysisReport)
async def get_analysis(
    analysis_id: uuid.UUID,
    include_raw: bool = Query(False),
    session: AsyncSession = Depends(get_session),
):
    return await report_service.get_report(session, analysis_id, include_raw=include_raw)
