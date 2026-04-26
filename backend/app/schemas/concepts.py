from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SourceCitation(BaseModel):
    source_id: int
    title: str | None = None
    source_type: str        # "pdf" | "url" | "image" | "text" | "chat_log"


class ConceptDetailResponse(BaseModel):
    id: int
    course_id: int
    title: str
    summary: str | None = None          # maps to Concept.definition — renamed at endpoint construction
    key_points: list[str] = []
    gotchas: list[str] = []
    examples: list[str] = []
    student_questions: list[str] = []   # aggregated from ConceptSource.student_questions (chat_log only)
    source_citations: list[SourceCitation] = []
    flashcard_count: int = 0
    struggle_signals: dict | None = None
    depth: int | None = None
    # NOTE: no model_config from_attributes — explicit construction in endpoint handles rename


class FlashcardResponse(BaseModel):
    id: int
    concept_id: int
    front: str
    back: str
    card_type: str   # "definition" | "application" | "gotcha" | "compare"
    created_at: datetime

    model_config = {"from_attributes": True}
