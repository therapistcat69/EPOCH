import logging
import socket
from collections.abc import AsyncIterator

from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

logger = logging.getLogger("retention.db")

SQLITE_FALLBACK_URL = "sqlite+aiosqlite:///./retention_dev.db"


class Base(DeclarativeBase):
    pass


def resolve_database_url(raw: str) -> tuple[str, str]:
    """Return (async_url, backend_label). Falls back to local SQLite when the
    configured value is empty or not a Postgres/SQLite URL, and says so loudly."""
    raw = (raw or "").strip()
    if raw.startswith(("postgres://", "postgresql://")):
        url = raw.replace("postgres://", "postgresql://", 1).replace(
            "postgresql://", "postgresql+asyncpg://", 1
        )
        return url, "postgres"
    if raw.startswith(("postgresql+asyncpg://", "sqlite")):
        return raw, "postgres" if raw.startswith("postgresql") else "sqlite"
    if raw:
        logger.warning(
            "DATABASE_URL is not a Postgres connection string (expected postgresql://...). "
            "Falling back to local SQLite for development."
        )
    else:
        logger.warning("DATABASE_URL is empty. Falling back to local SQLite for development.")
    return SQLITE_FALLBACK_URL, "sqlite-fallback"


def _prefer_ipv4(url: str) -> str | URL:
    """Supabase's pooler publishes IPv6/NAT64 addresses that hang on many networks.
    Resolve to IPv4 up front (credentials are percent-decoded by make_url)."""
    parsed = make_url(url)
    try:
        ipv4 = socket.getaddrinfo(parsed.host, parsed.port or 5432, socket.AF_INET)[0][4][0]
    except (socket.gaierror, TypeError):
        return url
    return parsed.set(host=ipv4)


def build_engine(raw_url: str | None = None) -> tuple[AsyncEngine, str]:
    url, label = resolve_database_url(raw_url if raw_url is not None else get_settings().database_url)
    kwargs: dict = {}
    if label == "postgres":
        url = _prefer_ipv4(url)
        kwargs["connect_args"] = {"timeout": 15}
        # Supabase's pooler (pgbouncer) does not support prepared statements.
        kwargs["connect_args"].update({"statement_cache_size": 0, "prepared_statement_cache_size": 0})
        kwargs["pool_pre_ping"] = True
    return create_async_engine(url, **kwargs), label


engine, db_backend = build_engine()
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    from app import models  # noqa: F401  (register tables)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
