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
    except Exception as exc:
        print(f"Seed failed — is the database running? Error: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
