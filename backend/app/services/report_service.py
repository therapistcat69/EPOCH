import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import repository as repo
from app.errors import AppError
from app.models import VideoAnalysis
from app.schemas.features import PENDING_FEATURES, FeaturePayload, FeatureStatus
from app.schemas.report import AnalysisReport, AnalysisSummary, MLStatus
from app.schemas.youtube import NormalizedChannel, NormalizedVideo
from app.services import channel_service, youtube_service
from app.services.youtube_client import YouTubeClient
from app.utils.youtube import extract_video_id


def build_feature_payload(video: NormalizedVideo) -> tuple[FeaturePayload, dict[str, FeatureStatus]]:
    """Real API-derived fields only. Research features stay None; never fabricated."""
    payload = FeaturePayload(
        video_id=video.video_id,
        title=video.title,
        duration_seconds=video.duration_seconds,
        category_id=video.category_id,
        view_count=video.statistics.views,
        like_count=video.statistics.likes,
        comment_count=video.statistics.comments,
        language=video.language,
        transcript_available=video.caption_available,
    )
    readiness: dict[str, FeatureStatus] = {}
    for name in FeaturePayload.model_fields:
        if name == "schema_version":
            continue
        if name in PENDING_FEATURES:
            readiness[name] = "pending_pipeline"
        elif name == "language":
            readiness[name] = "available" if payload.language else "pending_pipeline"
        else:
            readiness[name] = "available"
    return payload, readiness


def _report_from_row(row: VideoAnalysis, cached: bool, include_raw: bool = False) -> AnalysisReport:
    data = row.normalized_data or {}
    video = NormalizedVideo.model_validate(data["video"])
    channel = NormalizedChannel.model_validate(data["channel"]) if data.get("channel") else None
    features, readiness = build_feature_payload(video)
    return AnalysisReport(
        analysis_id=row.id,
        status=row.status,
        cached=cached,
        created_at=row.created_at,
        video=video,
        channel=channel,
        features=FeaturePayload.model_validate(row.feature_payload) if row.feature_payload else features,
        feature_readiness=readiness,
        ml_status=MLStatus(),
        raw_api_response=row.raw_api_response if include_raw else None,
    )


async def analyze(
    session: AsyncSession, client: YouTubeClient, youtube_url: str, refresh: bool = False
) -> AnalysisReport:
    video_id = extract_video_id(youtube_url)

    if not refresh:
        cached = await repo.get_recent_analysis(session, video_id, get_settings().cache_ttl_hours)
        if cached:
            return _report_from_row(cached, cached=True)

    video, raw_video = await youtube_service.get_video(client, video_id)

    channel: NormalizedChannel | None = None
    raw_channel: dict | None = None
    if video.channel.id:
        try:
            channel, raw_channel = await channel_service.get_channel(client, video.channel.id)
        except AppError as exc:
            # Video data is the core product; degrade gracefully if channel lookup fails,
            # except for quota/key problems, which affect everything.
            if exc.code not in {"CHANNEL_NOT_FOUND", "UPSTREAM_ERROR"}:
                raise

    features, _ = build_feature_payload(video)

    video_row = await repo.upsert_video(session, video)
    if channel:
        await repo.upsert_channel(session, channel)
    row = await repo.create_analysis(
        session,
        video_row.id,
        raw={"video": raw_video, "channel": raw_channel},
        normalized={
            "video": video.model_dump(mode="json"),
            "channel": channel.model_dump(mode="json") if channel else None,
        },
        features=features.model_dump(mode="json"),
    )
    await session.commit()
    return _report_from_row(row, cached=False)


async def get_report(session: AsyncSession, analysis_id: uuid.UUID, include_raw: bool = False) -> AnalysisReport:
    row = await repo.get_analysis(session, analysis_id)
    if row is None:
        raise AppError("ANALYSIS_NOT_FOUND", "That analysis could not be found.", 404)
    return _report_from_row(row, cached=True, include_raw=include_raw)


async def recent(session: AsyncSession, limit: int = 8) -> list[AnalysisSummary]:
    out: list[AnalysisSummary] = []
    for row in await repo.list_recent_analyses(session, limit):
        v = (row.normalized_data or {}).get("video", {})
        out.append(
            AnalysisSummary(
                analysis_id=row.id,
                video_id=v.get("video_id", ""),
                title=v.get("title", ""),
                channel_title=(v.get("channel") or {}).get("title"),
                thumbnail_url=v.get("thumbnail_url"),
                created_at=row.created_at,
            )
        )
    return out
