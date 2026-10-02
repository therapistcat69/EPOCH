from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import database
from app.db.database import get_session
from app.errors import AppError
from app.models import User, YouTubeChannel
from app.repositories import channel_repository, user_repository
from app.services import oauth_service

SESSION_COOKIE = "retainai_session"


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Overridable in tests; background tasks open their own session from this."""
    return database.SessionLocal


async def current_user(request: Request, session: AsyncSession = Depends(get_session)) -> User:
    sid = request.cookies.get(SESSION_COOKIE)
    row = await user_repository.get_valid_session(session, sid) if sid else None
    user = await user_repository.get_user(session, row.user_id) if row else None
    if user is None:
        raise AppError("NOT_AUTHENTICATED", "Please sign in with YouTube.", 401)
    return user


@dataclass
class CreatorContext:
    user: User
    channel: YouTubeChannel
    access_token: str
    session: AsyncSession


async def creator_context(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> CreatorContext:
    channel = await channel_repository.get_user_channel(session, user.id)
    if channel is None:
        raise AppError("NO_CHANNEL", "No YouTube channel is linked to this account.", 404)
    token = await oauth_service.get_valid_access_token(session, user.id)  # refreshes automatically
    return CreatorContext(user=user, channel=channel, access_token=token, session=session)
