import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.config import get_settings
from app.db.database import Base, get_session
from app.deps import get_session_factory
from app.main import create_app
from app.services.youtube_client import YouTubeClient, get_youtube_client


@pytest.fixture(autouse=True)
def oauth_env(monkeypatch):
    """Deterministic fake OAuth config for every test (never the developer's real .env values)."""
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/youtube/callback")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret-0123456789")
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:3000")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def yt_client() -> YouTubeClient:
    return YouTubeClient(api_key="test-key")


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest_asyncio.fixture
async def app(session_factory, yt_client) -> FastAPI:
    application = create_app()

    async def _session():
        async with session_factory() as s:
            yield s

    application.dependency_overrides[get_session] = _session
    application.dependency_overrides[get_session_factory] = lambda: session_factory
    application.dependency_overrides[get_youtube_client] = lambda: yt_client
    return application


@pytest_asyncio.fixture
async def api(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
