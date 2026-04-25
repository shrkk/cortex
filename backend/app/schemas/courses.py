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

    model_config = {"from_attributes": True}


class CourseMatchResponse(BaseModel):
    course_id: int
    title: str
    confidence: float
