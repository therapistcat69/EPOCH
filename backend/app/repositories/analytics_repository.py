import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AnalyticsCache, ReportingJob, ReportingReport, SyncJob


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def make_cache_key(user_id: uuid.UUID, report_type: str, video_id: str | None, start: date, end: date, extra: str = "") -> str:
    return f"{user_id}|{report_type}|{video_id or '-'}|{start}|{end}|{extra}"


async def get_cached(session: AsyncSession, key: str, max_age_minutes: int) -> AnalyticsCache | None:
    row = (await session.execute(select(AnalyticsCache).where(AnalyticsCache.cache_key == key))).scalar_one_or_none()
    if row is None:
        return None
    if _utc(row.fetched_at) < datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes):
        return None
    return row


async def put_cached(
    session: AsyncSession,
    key: str,
    *,
    user_id: uuid.UUID,
    channel_id: str,
    video_id: str | None,
    report_type: str,
    start: date,
    end: date,
    metrics: dict | list,
) -> None:
    row = (await session.execute(select(AnalyticsCache).where(AnalyticsCache.cache_key == key))).scalar_one_or_none()
    if row is None:
        row = AnalyticsCache(cache_key=key, user_id=user_id, channel_id=channel_id, video_id=video_id,
                             report_type=report_type, start_date=start, end_date=end)
        session.add(row)
    row.metrics = metrics
    row.fetched_at = datetime.now(timezone.utc)
    await session.flush()


# ---- sync jobs -------------------------------------------------------------
async def create_sync_job(session: AsyncSession, user_id: uuid.UUID) -> SyncJob:
    job = SyncJob(user_id=user_id, status="started", step="Starting sync...")
    session.add(job)
    await session.flush()
    return job


async def get_sync_job(session: AsyncSession, sync_id: uuid.UUID) -> SyncJob | None:
    return await session.get(SyncJob, sync_id)


async def running_sync_job(session: AsyncSession, user_id: uuid.UUID) -> SyncJob | None:
    rows = (
        await session.execute(
            select(SyncJob).where(SyncJob.user_id == user_id, SyncJob.status.in_(["started", "running"]))
        )
    ).scalars()
    for job in rows:  # ignore stale jobs (e.g. server restarted mid-sync)
        if _utc(job.updated_at or job.created_at) > datetime.now(timezone.utc) - timedelta(minutes=15):
            return job
    return None


# ---- reporting -------------------------------------------------------------
async def get_reporting_job(session: AsyncSession, user_id: uuid.UUID, report_type: str) -> ReportingJob | None:
    return (
        await session.execute(
            select(ReportingJob).where(ReportingJob.user_id == user_id, ReportingJob.report_type == report_type)
        )
    ).scalar_one_or_none()


async def list_reporting_jobs(session: AsyncSession, user_id: uuid.UUID) -> list[ReportingJob]:
    return list((await session.execute(select(ReportingJob).where(ReportingJob.user_id == user_id))).scalars())


async def save_reporting_job(
    session: AsyncSession, user_id: uuid.UUID, youtube_job_id: str, report_type: str
) -> ReportingJob:
    job = (
        await session.execute(
            select(ReportingJob).where(ReportingJob.user_id == user_id, ReportingJob.youtube_job_id == youtube_job_id)
        )
    ).scalar_one_or_none()
    if job is None:
        job = ReportingJob(user_id=user_id, youtube_job_id=youtube_job_id, report_type=report_type)
        session.add(job)
    await session.flush()
    return job


async def upsert_report(
    session: AsyncSession,
    job: ReportingJob,
    youtube_report_id: str,
    start_time: datetime | None,
    end_time: datetime | None,
    download_url: str | None,
    created_at: datetime | None,
) -> ReportingReport:
    row = (
        await session.execute(
            select(ReportingReport).where(
                ReportingReport.job_id == job.id, ReportingReport.youtube_report_id == youtube_report_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = ReportingReport(job_id=job.id, youtube_report_id=youtube_report_id)
        session.add(row)
    row.start_time, row.end_time, row.download_url = start_time, end_time, download_url
    if created_at and (job.last_report_at is None or _utc(created_at) > _utc(job.last_report_at)):
        job.last_report_at = created_at
    await session.flush()
    return row


async def list_reports(session: AsyncSession, job_id: uuid.UUID) -> list[ReportingReport]:
    return list(
        (
            await session.execute(
                select(ReportingReport)
                .where(ReportingReport.job_id == job_id)
                .order_by(ReportingReport.start_time.desc())
            )
        ).scalars()
    )


async def get_report(session: AsyncSession, report_id: uuid.UUID) -> ReportingReport | None:
    return await session.get(ReportingReport, report_id)
