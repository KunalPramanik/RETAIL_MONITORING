"""Database Session Management Module

Provides async engine and session factory with connection pooling and lifecycle hooks.
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
import os

from src.config import settings
from src.db.models import Base

# Async Engine with NullPool for SQLite to prevent lingering connection pool issues on reload/shutdown
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    poolclass=NullPool,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for yielding async database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def _sync_upgrade_sqlite_schema(sync_conn):
    """Ensure newly added columns exist in SQLite tables across migrations without data loss."""
    from sqlalchemy import text
    try:
        res = sync_conn.execute(text("PRAGMA table_info(camera)"))
        cam_cols = [row[1] for row in res.fetchall()]
        if "sub_stream_path" not in cam_cols:
            sync_conn.execute(text("ALTER TABLE camera ADD COLUMN sub_stream_path VARCHAR(255)"))
        if "pipeline_mode" not in cam_cols:
            sync_conn.execute(text("ALTER TABLE camera ADD COLUMN pipeline_mode VARCHAR(64) DEFAULT 'STANDARD_DETECTION'"))
        if "roi_polygon" not in cam_cols:
            sync_conn.execute(text("ALTER TABLE camera ADD COLUMN roi_polygon JSON"))
        if "ignored_classes" not in cam_cols:
            sync_conn.execute(text("ALTER TABLE camera ADD COLUMN ignored_classes JSON"))
        
        res = sync_conn.execute(text("PRAGMA table_info(camera_heartbeat)"))
        hb_cols = [row[1] for row in res.fetchall()]
        if "dropped_frames" not in hb_cols:
            sync_conn.execute(text("ALTER TABLE camera_heartbeat ADD COLUMN dropped_frames INTEGER DEFAULT 0"))

        res = sync_conn.execute(text("PRAGMA table_info(material)"))
        mat_cols = [row[1] for row in res.fetchall()]
        if mat_cols and "counting_tier" not in mat_cols:
            sync_conn.execute(text("ALTER TABLE material ADD COLUMN counting_tier VARCHAR(32) DEFAULT 'SINGLE_UNIT'"))
    except Exception:
        pass


async def init_db():
    """Create all database tables on application startup and auto-migrate added columns."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_sync_upgrade_sqlite_schema)


async def close_db():
    """Dispose all engine connections upon application shutdown."""
    await async_engine.dispose()


