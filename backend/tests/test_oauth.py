from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import httpx
import respx
from sqlalchemy import select

from app.models import OAuthAccount, User
from app.services import oauth_service
from tests.creator_fixtures import BASE, SCOPES, TOKEN_RESPONSE, TOKEN_URL
from tests.fixtures import CHANNELS_RESPONSE


async def start_login(api) -> str:
    r = await api.get("/api/auth/youtube/login")
    assert r.status_code == 302
    return parse_qs(urlparse(r.headers["location"]).query)["state"][0]


def mock_google(token=TOKEN_RESPONSE, channels=CHANNELS_RESPONSE):
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=token))
    return respx.get(f"{BASE}/channels").mock(return_value=httpx.Response(200, json=channels))


async def do_login(api):
    state = await start_login(api)
    r = await api.get(f"/api/auth/youtube/callback?code=abc&state={state}")
    assert r.status_code == 302, r.text
    return r


def test_login_url_scopes_and_params():
    url = oauth_service.build_login_url("STATE123")
    q = parse_qs(urlparse(url).query)
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert q["scope"] == [" ".join(oauth_service.SCOPES)]
    assert set(q["scope"][0].split()) == set(SCOPES.split())  # exactly the two read-only scopes
    assert "monetary" not in url and "auth/youtube " not in q["scope"][0] + " "
    assert q["state"] == ["STATE123"] and q["access_type"] == ["offline"] and q["response_type"] == ["code"]
    assert q["redirect_uri"] == ["http://localhost:8000/api/auth/youtube/callback"]
    assert "test-client-secret" not in url


def test_state_validation():
    s = oauth_service.new_state()
    assert oauth_service.states_match(s, s)
    assert not oauth_service.states_match(s, "other")
    assert not oauth_service.states_match(None, s) and not oauth_service.states_match(s, None)
    assert oauth_service.new_state() != oauth_service.new_state()


async def test_login_redirects_with_state_cookie(api):
    r = await api.get("/api/auth/youtube/login")
    assert r.status_code == 302 and "accounts.google.com" in r.headers["location"]
    cookie = r.headers["set-cookie"].lower()
    assert "oauth_state=" in cookie and "httponly" in cookie and "samesite=lax" in cookie


async def test_login_not_configured_redirects_with_error(api, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    from app.config import get_settings

    get_settings.cache_clear()
    r = await api.get("/api/auth/youtube/login")
    assert r.status_code == 302 and r.headers["location"].endswith("/login?error=OAUTH_NOT_CONFIGURED")


@respx.mock
async def test_callback_success_creates_session_and_stores_encrypted_tokens(api, session_factory):
    mock_google()
    r = await do_login(api)
    assert r.headers["location"] == "http://localhost:3000/dashboard"
    cookies = r.headers.get_list("set-cookie")
    session_cookie = next(c for c in cookies if c.startswith("retainai_session="))
    assert "httponly" in session_cookie.lower() and "samesite=lax" in session_cookie.lower()
    assert "ACCESS-1" not in session_cookie and "REFRESH-1" not in session_cookie  # opaque id only

    async with session_factory() as s:
        acct = (await s.execute(select(OAuthAccount))).scalar_one()
        assert "ACCESS-1" not in acct.access_token_encrypted and "REFRESH-1" not in acct.refresh_token_encrypted
        assert (await s.execute(select(User))).scalar_one().name == "Example Channel"

    me = await api.get("/api/auth/me")
    body = me.json()
    assert body["authenticated"] is True and body["channel"]["id"] == "UCuAXFkgsw1L7xaCfnd5JJOw"
    assert "token" not in me.text.lower()

    # logout destroys the session
    assert (await api.post("/api/auth/logout")).json() == {"ok": True}
    assert (await api.get("/api/auth/me")).json()["authenticated"] is False


@respx.mock
async def test_callback_uses_mine_true(api):
    route = mock_google()
    await do_login(api)
    assert route.calls[0].request.url.params["mine"] == "true"
    assert route.calls[0].request.headers["authorization"] == "Bearer ACCESS-1"


async def test_callback_invalid_state(api):
    await start_login(api)
    r = await api.get("/api/auth/youtube/callback?code=abc&state=forged")
    assert r.status_code == 302 and r.headers["location"].endswith("/login?error=INVALID_STATE")
    assert "retainai_session" not in r.headers.get("set-cookie", "")


async def test_callback_without_state_cookie(api):
    r = await api.get("/api/auth/youtube/callback?code=abc&state=whatever")
    assert r.headers["location"].endswith("error=INVALID_STATE")


async def test_callback_user_denied(api):
    r = await api.get("/api/auth/youtube/callback?error=access_denied")
    assert r.headers["location"].endswith("/login?error=OAUTH_DENIED")


@respx.mock
async def test_callback_no_channel(api):
    mock_google(channels={"items": []})
    state = await start_login(api)
    r = await api.get(f"/api/auth/youtube/callback?code=abc&state={state}")
    assert r.headers["location"].endswith("/login?error=NO_CHANNEL")


@respx.mock
async def test_callback_missing_scope(api):
    mock_google(token={**TOKEN_RESPONSE, "scope": "https://www.googleapis.com/auth/youtube.readonly"})
    state = await start_login(api)
    r = await api.get(f"/api/auth/youtube/callback?code=abc&state={state}")
    assert r.headers["location"].endswith("/login?error=SCOPE_MISSING")


@respx.mock
async def test_token_refresh_when_expired(api, session_factory):
    mock_google()
    await do_login(api)
    async with session_factory() as s:
        acct = (await s.execute(select(OAuthAccount))).scalar_one()
        acct.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        user_id = acct.user_id
        await s.commit()

    refresh = respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "ACCESS-2", "expires_in": 3600, "scope": SCOPES})
    )
    async with session_factory() as s:
        token = await oauth_service.get_valid_access_token(s, user_id)
    assert token == "ACCESS-2"
    last = refresh.calls[-1].request.content  # same route object as the login exchange; check the latest call
    assert b"grant_type=refresh_token" in last
    assert b"REFRESH-1" in last  # decrypted stored refresh token was used
    async with session_factory() as s:
        acct = (await s.execute(select(OAuthAccount))).scalar_one()
        assert acct.expires_at.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)
        assert acct.refresh_token_encrypted  # kept


@respx.mock
async def test_unexpired_token_is_not_refreshed(api, session_factory):
    mock_google()
    await do_login(api)
    async with session_factory() as s:
        user_id = (await s.execute(select(OAuthAccount))).scalar_one().user_id
        before = len(respx.calls)
        assert await oauth_service.get_valid_access_token(s, user_id) == "ACCESS-1"
    assert len(respx.calls) == before


@respx.mock
async def test_refresh_failure_requires_reauth(api, session_factory):
    mock_google()
    await do_login(api)
    async with session_factory() as s:
        acct = (await s.execute(select(OAuthAccount))).scalar_one()
        acct.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        user_id = acct.user_id
        await s.commit()
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(400, json={"error": "invalid_grant"}))
    r = await api.get("/api/channel/me")
    assert r.status_code == 401 and r.json()["error"]["code"] == "REAUTH_REQUIRED"
