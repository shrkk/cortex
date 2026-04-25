"""
Minimal Phase 1 seed script.

Loads:
  - user_id=1 (the single hardcoded user — no auth in v1)
  - 2 named courses so the notch course-matching pre-flight has data to return

Full demo-quality seed data (20+ concept nodes, struggle signal variance)
belongs to Phase 7. This script is intentionally minimal.

Usage:
    cd backend
    python scripts/seed_demo.py

Idempotent: safe to run multiple times if user_id=1 already exists
(INSERT ... ON CONFLICT DO NOTHING).
"""
import asyncio
import sys
from pathlib import Path

# Ensure backend/ is on sys.path so `from app...` imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import select, func

from app.models.models import User, Course
from app.core.config import settings


engine = create_async_engine(settings.database_url)
# expire_on_commit=False — prevents DetachedInstanceError if we access ORM
# attributes after commit (consistent with database.py pattern)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def backfill_course_embeddings(session) -> None:
    """Embed course titles that have no embedding yet (D-06).

    Called once during seed. Idempotent: skips courses that already have embeddings.
    Requires OPENAI_API_KEY to be set — silently skips if absent.
    """
    from app.core.config import settings as _settings
    if not _settings.openai_api_key:
        print("[seed] OPENAI_API_KEY not set — skipping course embedding backfill")
        return

    from openai import AsyncOpenAI
    from app.models.models import Course
    import sqlalchemy as sa

    client = AsyncOpenAI(api_key=_settings.openai_api_key)

    result = await session.execute(
        sa.select(Course).where(Course.embedding.is_(None))
    )
    courses_to_embed = result.scalars().all()

    if not courses_to_embed:
        print("[seed] All courses already have embeddings")
        return

    titles = [c.title for c in courses_to_embed]
    print(f"[seed] Backfilling embeddings for {len(titles)} courses: {titles}")

    try:
        embed_resp = await client.embeddings.create(
            model="text-embedding-3-small",
            input=titles,
        )
    except Exception as exc:
        print(f"[seed] Course embedding backfill failed (OpenAI error): {exc}")
        print("[seed] Courses seeded without embeddings — /courses/match will return null until embeddings are set")
        return

    for course, embed_data in zip(courses_to_embed, embed_resp.data):
        course.embedding = embed_data.embedding

    await session.commit()
    print(f"[seed] Backfilled {len(titles)} course embeddings")


async def seed() -> None:
    try:
        async with AsyncSessionLocal() as session:
            # user_id=1 is hardcoded throughout the codebase (no auth, single-user v1)
            # ON CONFLICT DO NOTHING makes this idempotent
            await session.execute(
                pg_insert(User)
                .values(id=1)
                .on_conflict_do_nothing(index_elements=["id"])
            )
            await session.flush()

            # Check if courses already seeded (idempotency)
            result = await session.execute(
                select(func.count()).select_from(Course).where(Course.user_id == 1)
            )
            existing_count = result.scalar()

            if existing_count == 0:
                courses = [
                    Course(
                        user_id=1,
                        title="CS 229 Machine Learning",
                        description="Stanford ML course — backprop, regularization, probability",
                    ),
                    Course(
                        user_id=1,
                        title="CS 231N Computer Vision",
                        description="Stanford CV course — CNNs, object detection, segmentation",
                    ),
                ]
                session.add_all(courses)
                await session.commit()
                print(f"Seeded user_id=1 with {len(courses)} courses.")
            else:
                await session.commit()
                print(f"Seed already applied — user_id=1 has {existing_count} courses. Skipping.")

        # Backfill course embeddings using a fresh session (D-06)
        # This must run after courses are committed so it sees the rows
        async with AsyncSessionLocal() as embed_session:
            await backfill_course_embeddings(embed_session)

    except Exception as exc:
        print(f"Seed failed — is the database running? Error: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
