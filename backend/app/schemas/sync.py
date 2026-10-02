import uuid
from datetime import datetime

from pydantic import BaseModel


class SyncStarted(BaseModel):
    sync_id: uuid.UUID
    status: str = "started"


class SyncStatus(BaseModel):
    sync_id: uuid.UUID
    status: str  # started | running | completed | failed
    step: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    stats: dict | None = None
    updated_at: datetime | None = None
