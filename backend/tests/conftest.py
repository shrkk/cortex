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


@pytest_asyncio.fixture(scope="module")
async def db_engine():
    """Shared async engine for migration/seed tests.

    Module-scoped so the connection pool is created once per test module and
    always disposed — even when a test assertion raises an exception — because
    pytest guarantees fixture teardown after yield.
    """
    from app.core.config import settings

    engine = create_async_engine(settings.database_url)
    yield engine
    await engine.dispose()
