from __future__ import annotations

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.models import Concept, ConceptSource, Source, Flashcard, Course
from app.schemas.concepts import ConceptDetailResponse

router = APIRouter()


@router.get("/{concept_id}", response_model=ConceptDetailResponse)
async def get_concept_detail(
    concept_id: int,
    session: AsyncSession = Depends(get_session),
):
    raise HTTPException(status_code=501, detail="Not implemented — Wave 1b")
