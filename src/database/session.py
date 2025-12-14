"""
Database session configuration for PostgreSQL with async support.
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from typing import AsyncGenerator
import os
from dotenv import load_dotenv

load_dotenv()

# Database URLs - Neon PostgreSQL
# For Neon, use connection string format: postgresql+asyncpg://user:password@host/dbname?sslmode=require
# Or use pooled connection: postgresql+asyncpg://user:password@host-pooler.region.aws.neon.tech/dbname?sslmode=require

def clean_database_url(url: str) -> str:
    """Clean database URL by removing psql prefix and extra quotes."""
    if not url:
        return url
    # Remove 'psql ' prefix if present
    if url.startswith("psql "):
        url = url[5:]
    # Remove surrounding quotes
    url = url.strip().strip("'").strip('"')
    # Ensure it starts with postgresql:// or postgresql+asyncpg://
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    # Remove sslmode from URL - asyncpg uses ssl parameter instead
    # We'll handle SSL via connect_args
    if "sslmode=" in url:
        url = url.split("sslmode=")[0].rstrip("?&")
    if "channel_binding=" in url:
        url = url.split("channel_binding=")[0].rstrip("?&")
    return url

raw_db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/aileads?sslmode=require")
DATABASE_URL = clean_database_url(raw_db_url)

raw_sync_url = os.getenv("DATABASE_URL_SYNC", "")
if raw_sync_url:
    DATABASE_URL_SYNC = clean_database_url(raw_sync_url)
else:
    # Generate sync URL from async URL (use psycopg3)
    DATABASE_URL_SYNC = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)

# Async engine for async operations (Neon compatible)
# Neon supports connection pooling - use pooled connection string for better performance
# Determine SSL requirement from original URL
requires_ssl = "neon.tech" in raw_db_url or "sslmode=require" in raw_db_url.lower()

async_engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("DEBUG", "False").lower() == "true",
    future=True,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args={
        "ssl": "require" if requires_ssl else None
    } if requires_ssl else {},
)

# Sync engine for Alembic migrations (using psycopg3) - optional, only if needed
# Since we're not using Alembic, make this optional
sync_engine = None
SessionLocal = None

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting database session.
    Yields an async database session.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

