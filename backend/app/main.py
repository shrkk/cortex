from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import update

from app.core.database import AsyncSessionLocal
from app.models.models import Source
from app.api.router import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: reset any sources stuck in status='processing' from a prior crash.
    This guards against silent task loss when uvicorn restarts mid-pipeline.
    Shutdown: nothing needed in Phase 1.
    """
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(Source)
            .where(Source.status == "processing")
            .values(status="pending")
        )
        await session.commit()
    yield
    # Shutdown hook would go here — nothing needed for Phase 1


app = FastAPI(
    title="Cortex API",
    description="Knowledge graph backend for student learning",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS: allow_origins=["*"] is required for local dev.
# Swift URLSession sends no Origin header — if we list specific origins, requests with
# no Origin header are blocked. allow_credentials=False is mandatory when using ["*"].
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # MUST be False when allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
