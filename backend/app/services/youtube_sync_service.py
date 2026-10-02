"""Idempotent creator-data sync, run as a background task. Safe to run repeatedly (upserts only)."""
import logging
import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.errors import AppError
from app.repositories import analytics_repository as jobs
from app.repositories import channel_repository as channels
from app.repositories import video_repository as videos
from app.services import oauth_service
from app.services.youtube_analytics_service import AnalyticsService, validate_range
from app.services.youtube_client import YouTubeClient
from app.services.youtube_data_service import fetch_uploads, get_my_channel
from app.services.youtube_reporting_service import ReportingService

logger = logging.getLogger("retention.sync")


async def _set(session: AsyncSession, job, status: str, step: str, **extra) -> None:
    job.status, job.step = status, step
    for k, v in extra.items():
        setattr(job, k, v)
    await session.commit()


async def run_sync(session_factory: async_sessionmaker[AsyncSession], sync_id: uuid.UUID, user_id: uuid.UUID) -> None:
    settings = get_settings()
    async with session_factory() as session:
        job = await jobs.get_sync_job(session, sync_id)
        if job is None:
            return
        stats: dict = {}
        try:
            await _set(session, job, "running", "Fetching channel...")
            token = await oauth_service.get_valid_access_token(session, user_id)
            client = YouTubeClient(access_token=token)
            channel = await get_my_channel(client)
            channel_row = await channels.upsert_channel(session, user_id, channel)
            await session.commit()

            await _set(session, job, "running", "Fetching videos...")
            owned = []
            if channel.uploads_playlist_id:
                owned = await fetch_uploads(client, channel.uploads_playlist_id, settings.max_sync_videos)
            await _set(session, job, "running", "Updating database...")
            stats["videos"] = await videos.upsert_owned_videos(session, owned)
            await session.commit()

            await _set(session, job, "running", "Fetching analytics...")
            start, end = validate_range(None, date.today())
            svc = AnalyticsService(session, user_id, channel.channel_id, token)
            try:
                await svc.overview(start, end, refresh=True)
                await svc.timeseries(start, end, refresh=True)
                await svc.videos(start, end, refresh=True)
                stats["analytics"] = "ok"
            except AppError as exc:  # analytics problems shouldn't discard the video sync
                stats["analytics"] = f"skipped: {exc.code}"

            await _set(session, job, "running", "Scheduling reporting job...")
            try:
                reporting = ReportingService(session, user_id, token)
                rjob = await reporting.ensure_job()
                await reporting.sync_reports(rjob)
                stats["reporting"] = "ok"
            except AppError as exc:
                stats["reporting"] = f"skipped: {exc.code}"

            await channels.mark_synced(session, channel_row)
            await _set(session, job, "completed", "Done.", stats=stats)
        except AppError as exc:
            await session.rollback()
            job = await jobs.get_sync_job(session, sync_id)
            await _set(session, job, "failed", "Sync failed.", error_code=exc.code, error_message=exc.message, stats=stats)
        except Exception:  # noqa: BLE001
            logger.exception("Unexpected sync failure")
            await session.rollback()
            job = await jobs.get_sync_job(session, sync_id)
            await _set(session, job, "failed", "Sync failed.", error_code="INTERNAL_ERROR",
                       error_message="Something went wrong during sync.", stats=stats)
