import uuid

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.database import get_session
from app.deps import current_user, get_session_factory
from app.errors import AppError
from app.models import User
from app.repositories import analytics_repository as repo
from app.schemas.sync import SyncStarted, SyncStatus
from app.services.youtube_sync_service import run_sync

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.post("", response_model=SyncStarted)
async def start_sync(
    background: BackgroundTasks,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
):
    running = await repo.running_sync_job(session, user.id)  # don't stack concurrent syncs
    if running:
        return SyncStarted(sync_id=running.id, status=running.status)
    job = await repo.create_sync_job(session, user.id)
    await session.commit()
    background.add_task(run_sync, factory, job.id, user.id)
    return SyncStarted(sync_id=job.id, status="started")


@router.get("/{sync_id}", response_model=SyncStatus)
async def sync_status(
    sync_id: uuid.UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
):
    job = await repo.get_sync_job(session, sync_id)
    if job is None or job.user_id != user.id:
        raise AppError("SYNC_NOT_FOUND", "That sync job could not be found.", 404)
    return SyncStatus(
        sync_id=job.id, status=job.status, step=job.step, error_code=job.error_code,
        error_message=job.error_message, stats=job.stats, updated_at=job.updated_at,
    )
