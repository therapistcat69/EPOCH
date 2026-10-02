import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.errors import AppError
from app.repositories import channel_repository as channels
from app.repositories import user_repository as users
from app.schemas.youtube import NormalizedChannel
from app.services import crypto
from app.services.channel_service import normalize_channel
from app.services.youtube_client import YouTubeClient

logger = logging.getLogger("retention.oauth")

# Minimum read-only scopes. No write access, no monetary analytics.
SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]
REFRESH_SKEW = timedelta(seconds=60)


@dataclass
class TokenSet:
    access_token: str
    refresh_token: str | None
    expires_at: datetime
    scope: str | None


def new_state() -> str:
    return secrets.token_urlsafe(32)


def states_match(expected: str | None, received: str | None) -> bool:
    return bool(expected) and bool(received) and secrets.compare_digest(expected, received)


def require_configured() -> None:
    if not get_settings().oauth_configured:
        raise AppError(
            "OAUTH_NOT_CONFIGURED",
            "Google sign-in isn't configured on the server yet (client ID/secret or session secret missing).",
            503,
        )


def build_login_url(state: str) -> str:
    require_configured()
    s = get_settings()
    params = {
        "client_id": s.google_client_id,
        "redirect_uri": s.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",  # we need a refresh token for long-lived analytics access
        "prompt": "consent",  # ensures Google returns the refresh token
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{s.google_auth_url}?{urlencode(params)}"


async def _token_request(data: dict) -> dict:
    s = get_settings()
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(s.google_token_url, data=data)
    except httpx.HTTPError:
        raise AppError("UPSTREAM_ERROR", "Could not reach Google. Please try again.", 502)
    if resp.status_code >= 400:
        try:
            code = resp.json().get("error", "")
        except ValueError:
            code = ""
        logger.warning("Google token endpoint returned %s (%s)", resp.status_code, code)  # never log bodies/tokens
        if code == "invalid_grant":
            raise AppError("REAUTH_REQUIRED", "Your Google connection expired. Please sign in again.", 401)
        raise AppError("OAUTH_CALLBACK_FAILED", "Google sign-in failed. Please try again.", 400)
    return resp.json()


def _token_set(payload: dict, fallback_refresh: str | None = None) -> TokenSet:
    return TokenSet(
        access_token=payload["access_token"],
        refresh_token=payload.get("refresh_token") or fallback_refresh,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=int(payload.get("expires_in", 3600))),
        scope=payload.get("scope"),
    )


async def exchange_code(code: str) -> TokenSet:
    s = get_settings()
    payload = await _token_request(
        {
            "code": code,
            "client_id": s.google_client_id,
            "client_secret": s.google_client_secret,
            "redirect_uri": s.google_redirect_uri,
            "grant_type": "authorization_code",
        }
    )
    return _token_set(payload)


async def refresh_tokens(refresh_token: str) -> TokenSet:
    s = get_settings()
    payload = await _token_request(
        {
            "refresh_token": refresh_token,
            "client_id": s.google_client_id,
            "client_secret": s.google_client_secret,
            "grant_type": "refresh_token",
        }
    )
    return _token_set(payload, fallback_refresh=refresh_token)


def missing_scopes(granted: str | None) -> list[str]:
    have = set((granted or "").split())
    return [sc for sc in SCOPES if sc not in have]


async def complete_login(session: AsyncSession, code: str) -> tuple[uuid.UUID, NormalizedChannel]:
    """Exchange the code, identify the user's channel, persist user/tokens/channel. Returns (user_id, channel)."""
    tokens = await exchange_code(code)
    if missing_scopes(tokens.scope):
        raise AppError(
            "SCOPE_MISSING",
            "Both YouTube permissions are required. Please sign in again and leave both boxes ticked.",
            403,
        )

    raw = await YouTubeClient(access_token=tokens.access_token).my_channel()
    items = raw.get("items", [])
    if not items:
        raise AppError(
            "NO_CHANNEL",
            "We connected your Google account, but no YouTube channel was found for this account.",
            404,
        )
    channel = normalize_channel(items[0])

    # Only the two read-only YouTube scopes are requested, so we identify the user by their
    # channel (no Google profile/email scope needed).
    user = await users.upsert_user(
        session, google_sub=f"yt:{channel.channel_id}", name=channel.title, email=None, image=channel.thumbnail_url
    )
    await users.upsert_oauth_account(
        session,
        user.id,
        access_token_encrypted=crypto.encrypt(tokens.access_token),
        refresh_token_encrypted=crypto.encrypt(tokens.refresh_token) if tokens.refresh_token else None,
        expires_at=tokens.expires_at,
        scope=tokens.scope,
    )
    await channels.upsert_channel(session, user.id, channel)
    await session.flush()
    return user.id, channel


async def get_valid_access_token(session: AsyncSession, user_id: uuid.UUID) -> str:
    """Return a usable access token, refreshing (and persisting) it if expired. Invisible to the frontend."""
    acct = await users.get_oauth_account(session, user_id)
    if acct is None:
        raise AppError("NOT_AUTHENTICATED", "Please sign in with YouTube.", 401)
    expires = acct.expires_at if acct.expires_at is None or acct.expires_at.tzinfo else acct.expires_at.replace(tzinfo=timezone.utc)
    if expires and expires > datetime.now(timezone.utc) + REFRESH_SKEW:
        return crypto.decrypt(acct.access_token_encrypted)

    if not acct.refresh_token_encrypted:
        raise AppError("REAUTH_REQUIRED", "Your Google connection expired. Please sign in again.", 401)
    tokens = await refresh_tokens(crypto.decrypt(acct.refresh_token_encrypted))
    acct.access_token_encrypted = crypto.encrypt(tokens.access_token)
    acct.expires_at = tokens.expires_at
    if tokens.scope:
        acct.scope = tokens.scope
    await session.commit()
    return tokens.access_token
