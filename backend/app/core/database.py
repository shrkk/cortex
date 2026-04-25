from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,  # postgresql+asyncpg://...
    pool_size=10,
    max_overflow=5,
    pool_pre_ping=True,
)

# expire_on_commit=False is REQUIRED — prevents DetachedInstanceError when background
# tasks access ORM object attributes after session.commit()
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncSession:
    """FastAPI dependency — yields an async session, cleans up on exit."""
    async with AsyncSessionLocal() as session:
        yield session
