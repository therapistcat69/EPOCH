import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OAuthAccount, User, UserSession


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def upsert_user(
    session: AsyncSession, google_sub: str, name: str | None, email: str | None, image: str | None
) -> User:
    user = (await session.execute(select(User).where(User.google_sub == google_sub))).scalar_one_or_none()
    if user is None:
        user = User(google_sub=google_sub)
        session.add(user)
    user.name, user.profile_image = name, image
    if email:
        user.email = email
    await session.flush()
    return user


async def get_user(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)


async def get_oauth_account(session: AsyncSession, user_id: uuid.UUID) -> OAuthAccount | None:
    return (
        await session.execute(
            select(OAuthAccount).where(OAuthAccount.user_id == user_id, OAuthAccount.provider == "google")
        )
    ).scalar_one_or_none()


async def upsert_oauth_account(
    session: AsyncSession,
    user_id: uuid.UUID,
    access_token_encrypted: str,
    refresh_token_encrypted: str | None,
    expires_at: datetime,
    scope: str | None,
) -> OAuthAccount:
    acct = await get_oauth_account(session, user_id)
    if acct is None:
        acct = OAuthAccount(user_id=user_id, provider="google", access_token_encrypted=access_token_encrypted)
        session.add(acct)
    acct.access_token_encrypted = access_token_encrypted
    # Google only returns a refresh token on consent; never overwrite a stored one with nothing.
    if refresh_token_encrypted:
        acct.refresh_token_encrypted = refresh_token_encrypted
    acct.expires_at = expires_at
    acct.scope = scope
    await session.flush()
    return acct


async def create_session(session: AsyncSession, user_id: uuid.UUID, ttl_days: int) -> UserSession:
    row = UserSession(
        id=secrets.token_urlsafe(48),
        user_id=user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=ttl_days),
    )
    session.add(row)
    await session.flush()
    return row


async def get_valid_session(session: AsyncSession, session_id: str) -> UserSession | None:
    row = await session.get(UserSession, session_id)
    if row is None:
        return None
    if _utc(row.expires_at) < datetime.now(timezone.utc):
        await session.delete(row)
        await session.flush()
        return None
    return row


async def delete_session(session: AsyncSession, session_id: str) -> None:
    await session.execute(delete(UserSession).where(UserSession.id == session_id))
