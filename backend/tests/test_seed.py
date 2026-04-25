import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings


async def test_seed_creates_user_and_courses():
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as conn:
        user_result = await conn.execute(
            text("SELECT id FROM users WHERE id = 1")
        )
        user_row = user_result.fetchone()

        course_result = await conn.execute(
            text("SELECT COUNT(*) FROM courses WHERE user_id = 1")
        )
        course_count = course_result.scalar()
    await engine.dispose()

    assert user_row is not None, "user_id=1 not found in users table"
    assert course_count >= 1, f"Expected at least 1 course for user_id=1, got {course_count}"
