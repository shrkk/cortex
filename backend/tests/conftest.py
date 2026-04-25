import pytest
import pytest_asyncio

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

except ImportError:
    # app.main not yet created (added in plan 01-04); migration tests run without it
    pass
