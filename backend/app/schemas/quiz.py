"""Pydantic schemas for quiz endpoints (Phase 4).

QuizCreate: POST /quiz request body.
QuizResponse: POST /quiz and GET /quiz/{id}/results response.
AnswerRequest: POST /quiz/{id}/answer request body.
AnswerResponse: POST /quiz/{id}/answer response.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class QuizCreate(BaseModel):
    course_id: int
    num_questions: int


class QuizResponse(BaseModel):
    id: int
    course_id: int
    questions: list[dict[str, Any]]  # reference_answer stripped before populating

    model_config = {"from_attributes": True}


class AnswerRequest(BaseModel):
    question_id: int
    answer: str


class AnswerResponse(BaseModel):
    grading: dict[str, Any]
    next_question: dict[str, Any] | None = None
    is_complete: bool = False
    score: float | None = None
    correct_count: int | None = None
    total: int | None = None
    concepts_to_review: list[int] | None = None
