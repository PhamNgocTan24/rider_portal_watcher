"""
Shared pytest fixtures for API tests.

Strategy:
- Run Alembic migrations once per session before any test.
- Use NullPool so asyncpg never reuses connections across loops.
- Each test gets its own DB session (function scope).
- Tests use unique IDs to avoid row collisions.
"""
from __future__ import annotations

import os

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.database import get_db
from app.main import app

TEST_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://rideportal:rideportal@postgres:5432/rideportal",
)


@pytest.fixture(scope="session", autouse=True)
def run_migrations():
    """Run alembic upgrade head once before all tests."""
    cfg = Config("/app/alembic.ini")
    command.upgrade(cfg, "head")


def _make_session_factory():
    engine = create_async_engine(TEST_DB_URL, poolclass=NullPool, echo=False)
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False), engine


@pytest_asyncio.fixture()
async def db_session(run_migrations):
    """Each test gets its own async session with a fresh engine (NullPool)."""
    factory, engine = _make_session_factory()
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture()
async def client(db_session: AsyncSession):
    """FastAPI async test client with DB dependency overridden."""

    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
