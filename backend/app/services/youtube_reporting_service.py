"""YouTube Reporting API: bulk, asynchronous report generation (NOT an instant mirror of YouTube Studio).

A job is created once per report type; YouTube then generates daily report files that can be
listed and downloaded. Dashboards use the Analytics API for immediate results instead.
"""
import csv
import io
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.errors import AppError
from app.models import ReportingJob, ReportingReport
from app.repositories import analytics_repository as repo
from app.schemas.reporting import ProcessedReport, ReportTypeInfo
from app.services.youtube_client import google_request
from app.utils.formatting import parse_datetime

DEFAULT_REPORT_TYPE = "channel_basic_a3"


class ReportingService:
    def __init__(self, session: AsyncSession, user_id: uuid.UUID, access_token: str):
        self.session, self.user_id, self.token = session, user_id, access_token
        self.base = get_settings().reporting_api_base

    async def _call(self, method: str, path: str, **kw):
        return await google_request(
            method, f"{self.base}/{path}", access_token=self.token, context="reporting", **kw
        )

    async def list_report_types(self) -> list[ReportTypeInfo]:
        data = await self._call("GET", "reportTypes")
        return [
            ReportTypeInfo(id=r["id"], name=r.get("name"), deprecate_time=r.get("deprecateTime"))
            for r in data.get("reportTypes", [])
        ]

    async def list_remote_jobs(self) -> list[dict]:
        return (await self._call("GET", "jobs")).get("jobs", [])

    async def get_remote_job(self, job_id: str) -> dict:
        return await self._call("GET", f"jobs/{job_id}")

    async def ensure_job(self, report_type: str = DEFAULT_REPORT_TYPE) -> ReportingJob:
        """Create the job only if one doesn't already exist (locally or on YouTube)."""
        existing = await repo.get_reporting_job(self.session, self.user_id, report_type)
        if existing:
            return existing
        for job in await self.list_remote_jobs():
            if job.get("reportTypeId") == report_type:
                saved = await repo.save_reporting_job(self.session, self.user_id, job["id"], report_type)
                await self.session.commit()
                return saved
        created = await self._call(
            "POST", "jobs", json={"reportTypeId": report_type, "name": f"retainai-{report_type}"}
        )
        saved = await repo.save_reporting_job(self.session, self.user_id, created["id"], report_type)
        await self.session.commit()
        return saved

    async def sync_reports(self, job: ReportingJob) -> list[ReportingReport]:
        """Record which generated reports exist. Does not download them."""
        data = await self._call("GET", f"jobs/{job.youtube_job_id}/reports")
        for r in data.get("reports", []):
            await repo.upsert_report(
                self.session,
                job,
                r["id"],
                parse_datetime(r.get("startTime")),
                parse_datetime(r.get("endTime")),
                r.get("downloadUrl"),
                parse_datetime(r.get("createTime")),
            )
        await self.session.commit()
        return await repo.list_reports(self.session, job.id)

    async def get_remote_report(self, job: ReportingJob, report_id: str) -> dict:
        return await self._call("GET", f"jobs/{job.youtube_job_id}/reports/{report_id}")

    async def process_report(self, report: ReportingReport) -> ProcessedReport:
        """Download one report on demand and record its shape. File contents are not stored."""
        if not report.download_url:
            raise AppError("REPORT_NOT_READY", "This report has no download URL yet.", 409)
        resp = await google_request(
            "GET", report.download_url, access_token=self.token, context="reporting", raw=True
        )
        rows = list(csv.reader(io.StringIO(resp.text)))
        columns = rows[0] if rows else []
        report.row_count = max(len(rows) - 1, 0)
        report.processed_at = datetime.now(timezone.utc)
        await self.session.commit()
        return ProcessedReport(
            report_id=report.id, row_count=report.row_count, columns=columns, processed_at=report.processed_at
        )
