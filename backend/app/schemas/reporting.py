import uuid
from datetime import datetime

from pydantic import BaseModel


class ReportTypeInfo(BaseModel):
    id: str
    name: str | None = None
    deprecate_time: str | None = None


class ReportingJobInfo(BaseModel):
    id: uuid.UUID | None = None
    youtube_job_id: str
    report_type: str
    status: str = "active"
    last_report_at: datetime | None = None


class ReportInfo(BaseModel):
    id: uuid.UUID
    youtube_report_id: str
    start_time: datetime | None = None
    end_time: datetime | None = None
    processed_at: datetime | None = None
    row_count: int | None = None


class ProcessedReport(BaseModel):
    report_id: uuid.UUID
    row_count: int
    columns: list[str]
    processed_at: datetime
