from datetime import datetime

from pydantic import BaseModel


class CourseCreate(BaseModel):
    title: str
    user_id: int = 1  # hardcoded single-user; default=1 for Swift client compatibility


class CourseResponse(BaseModel):
    id: int
    user_id: int
    title: str
    description: str | None = None
    created_at: datetime
    concept_count: int = 0           # total concepts in this course
    active_struggle_count: int = 0   # concepts with non-empty struggle_signals dict

    model_config = {"from_attributes": True}


class CourseMatchResponse(BaseModel):
    course_id: int
    title: str
    confidence: float


class SourceResponse(BaseModel):
    id: int
    course_id: int
    source_type: str   # "pdf" | "url" | "image" | "text" | "chat_log"
    title: str | None = None
    status: str        # "pending" | "processing" | "done" | "error"
    created_at: datetime

    model_config = {"from_attributes": True}
