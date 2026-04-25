import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine

try:
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    @pytest_asyncio.fixture
    async def client():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac

except ModuleNotFoundError:
    # app.main not yet created (added in plan 01-04); migration tests run without it
    pass


@pytest_asyncio.fixture
async def db_engine():
    """Per-test async engine for migration/seed tests.

    Function-scoped to avoid "Future attached to a different loop" errors:
    pytest-asyncio 0.24 creates a new event loop per test, so a module-scoped
    engine created on test-1's loop cannot be reused by test-2's loop.
    """
    from app.core.config import settings

    engine = create_async_engine(settings.database_url)
    yield engine
    await engine.dispose()
