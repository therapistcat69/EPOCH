"""Google OAuth 2.0 (server-side authorization-code flow). Tokens never leave the server."""
import logging
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.database import get_session
from app.deps import SESSION_COOKIE, current_user
from app.errors import AppError
from app.models import User
from app.repositories import channel_repository, user_repository
from app.schemas.auth import AuthChannel, AuthUser, MeResponse
from app.services import oauth_service

logger = logging.getLogger("retention.auth")
router = APIRouter(prefix="/api/auth", tags=["auth"])

STATE_COOKIE = "oauth_state"


def _to_login(error: str) -> RedirectResponse:
    resp = RedirectResponse(f"{get_settings().frontend_url}/login?{urlencode({'error': error})}", status_code=302)
    resp.delete_cookie(STATE_COOKIE, path="/api/auth")
    return resp


@router.get("/youtube/login")
async def login():
    try:
        state = oauth_service.new_state()
        url = oauth_service.build_login_url(state)
    except AppError as exc:
        return _to_login(exc.code)
    resp = RedirectResponse(url, status_code=302)
    resp.set_cookie(
        STATE_COOKIE, state, max_age=600, httponly=True, samesite="lax",
        secure=get_settings().cookie_secure, path="/api/auth",
    )
    return resp


@router.get("/youtube/callback")
async def callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    if error:  # e.g. access_denied when the user cancels consent
        return _to_login("OAUTH_DENIED" if error == "access_denied" else "OAUTH_CALLBACK_FAILED")
    if not oauth_service.states_match(request.cookies.get(STATE_COOKIE), state):
        return _to_login("INVALID_STATE")
    if not code:
        return _to_login("OAUTH_CALLBACK_FAILED")
    try:
        user_id, _ = await oauth_service.complete_login(session, code)
        sess = await user_repository.create_session(session, user_id, get_settings().session_ttl_days)
        await session.commit()
    except AppError as exc:
        await session.rollback()
        return _to_login(exc.code)
    except Exception:  # noqa: BLE001
        logger.exception("OAuth callback failed")
        await session.rollback()
        return _to_login("OAUTH_CALLBACK_FAILED")

    s = get_settings()
    resp = RedirectResponse(f"{s.frontend_url}/dashboard", status_code=302)
    resp.delete_cookie(STATE_COOKIE, path="/api/auth")
    resp.set_cookie(
        SESSION_COOKIE, sess.id, max_age=s.session_ttl_days * 86400, httponly=True,
        samesite="lax", secure=s.cookie_secure, path="/",
    )
    return resp


@router.get("/me", response_model=MeResponse)
async def me(request: Request, session: AsyncSession = Depends(get_session)):
    try:
        user: User = await current_user(request, session)
    except AppError:
        return MeResponse(authenticated=False)
    channel = await channel_repository.get_user_channel(session, user.id)
    return MeResponse(
        authenticated=True,
        user=AuthUser(name=user.name, email=user.email, image=user.profile_image),
        channel=AuthChannel(id=channel.youtube_channel_id, title=channel.title, thumbnail_url=channel.thumbnail_url)
        if channel
        else None,
    )


@router.post("/logout")
async def logout(request: Request, session: AsyncSession = Depends(get_session)):
    """Ends the app session only; the Google grant is not revoked."""
    sid = request.cookies.get(SESSION_COOKIE)
    if sid:
        await user_repository.delete_session(session, sid)
        await session.commit()
    from fastapi.responses import JSONResponse

    resp = JSONResponse({"ok": True})
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp
