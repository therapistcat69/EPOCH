import uuid

from fastapi import APIRouter, Body, Depends

from app.deps import CreatorContext, creator_context
from app.errors import AppError
from app.repositories import analytics_repository as repo
from app.schemas.reporting import ProcessedReport, ReportingJobInfo, ReportInfo, ReportTypeInfo
from app.services.youtube_reporting_service import DEFAULT_REPORT_TYPE, ReportingService

router = APIRouter(prefix="/api/reporting", tags=["reporting"])


def _svc(ctx: CreatorContext) -> ReportingService:
    return ReportingService(ctx.session, ctx.user.id, ctx.access_token)


def _job_info(j) -> ReportingJobInfo:
    return ReportingJobInfo(id=j.id, youtube_job_id=j.youtube_job_id, report_type=j.report_type,
                            status=j.status, last_report_at=j.last_report_at)


@router.get("/report-types", response_model=list[ReportTypeInfo])
async def report_types(ctx: CreatorContext = Depends(creator_context)):
    return await _svc(ctx).list_report_types()


@router.get("/jobs", response_model=list[ReportingJobInfo])
async def jobs(ctx: CreatorContext = Depends(creator_context)):
    return [_job_info(j) for j in await repo.list_reporting_jobs(ctx.session, ctx.user.id)]


@router.post("/jobs", response_model=ReportingJobInfo)
async def create_job(report_type: str = Body(DEFAULT_REPORT_TYPE, embed=True), ctx: CreatorContext = Depends(creator_context)):
    """Idempotent: returns the existing job for this report type if there is one."""
    return _job_info(await _svc(ctx).ensure_job(report_type))


@router.get("/jobs/{job_id}", response_model=ReportingJobInfo)
async def get_job(job_id: uuid.UUID, ctx: CreatorContext = Depends(creator_context)):
    job = await _own_job(ctx, job_id)
    await _svc(ctx).get_remote_job(job.youtube_job_id)  # surfaces YouTube-side errors
    return _job_info(job)


@router.get("/jobs/{job_id}/reports", response_model=list[ReportInfo])
async def job_reports(job_id: uuid.UUID, ctx: CreatorContext = Depends(creator_context)):
    """Refresh the list of generated reports from YouTube (no downloads). New jobs can take ~48h to produce data."""
    job = await _own_job(ctx, job_id)
    reports = await _svc(ctx).sync_reports(job)
    return [ReportInfo(id=r.id, youtube_report_id=r.youtube_report_id, start_time=r.start_time,
                       end_time=r.end_time, processed_at=r.processed_at, row_count=r.row_count) for r in reports]


@router.post("/reports/{report_id}/process", response_model=ProcessedReport)
async def process_report(report_id: uuid.UUID, ctx: CreatorContext = Depends(creator_context)):
    report = await repo.get_report(ctx.session, report_id)
    if report is None:
        raise AppError("REPORT_NOT_FOUND", "That report could not be found.", 404)
    await _own_job(ctx, report.job_id)
    return await _svc(ctx).process_report(report)


async def _own_job(ctx: CreatorContext, job_id: uuid.UUID):
    from app.models import ReportingJob

    job = await ctx.session.get(ReportingJob, job_id)
    if job is None or job.user_id != ctx.user.id:
        raise AppError("JOB_NOT_FOUND", "That reporting job could not be found.", 404)
    return job
