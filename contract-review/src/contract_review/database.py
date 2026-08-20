"""Database engine and session factory.

Two connection modes:
- Async (asyncpg) for the FastAPI app runtime
- Sync (psycopg) for Alembic migrations and sync fallback

DATABASE_URL examples:
  postgresql+asyncpg://contract:contract@localhost:5432/contract_review  (async)
  postgresql+psycopg://contract:contract@localhost:5432/contract_review   (sync)
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from contract_review.db import Base


def get_database_url(*, async_mode: bool = True) -> str:
    """Resolve the database URL from env, converting between sync/async schemes."""
    raw = os.getenv("DATABASE_URL", "")
    if not raw:
        raise RuntimeError("DATABASE_URL is not set; cannot connect to PostgreSQL")
    if async_mode:
        if raw.startswith("postgresql://"):
            return raw.replace("postgresql://", "postgresql+asyncpg://", 1)
        if raw.startswith("postgresql+psycopg://"):
            return raw.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)
        return raw
    else:
        if raw.startswith("postgresql+asyncpg://"):
            return raw.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
        if raw.startswith("postgresql://"):
            return raw.replace("postgresql://", "postgresql+psycopg://", 1)
        return raw


def is_postgres_enabled() -> bool:
    """Check if PostgreSQL backend should be used instead of in-memory."""
    return os.getenv("STORAGE_BACKEND", "memory").lower() == "postgres" and bool(os.getenv("DATABASE_URL"))


# ── Async (app runtime) ──────────────────────────────────────

_async_engine = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_async_engine():
    global _async_engine
    if _async_engine is None:
        _async_engine = create_async_engine(
            get_database_url(async_mode=True),
            echo=False,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
    return _async_engine


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            get_async_engine(), class_=AsyncSession, expire_on_commit=False
        )
    return _async_session_factory


# ── Sync (Alembic / fallback) ────────────────────────────────

_sync_engine = None
_sync_session_factory: sessionmaker[Session] | None = None


def get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(
            get_database_url(async_mode=False),
            echo=False,
            pool_pre_ping=True,
        )
    return _sync_engine


def get_sync_session_factory() -> sessionmaker[Session]:
    global _sync_session_factory
    if _sync_session_factory is None:
        _sync_session_factory = sessionmaker(get_sync_engine(), expire_on_commit=False)
    return _sync_session_factory


async def init_db():
    """Create tables if they don't exist (dev convenience; production uses Alembic)."""
    engine = get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
