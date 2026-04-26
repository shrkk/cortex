"""Quiz API endpoints (Phase 4).

Routes:
  POST /quiz                    — generate a new quiz for a course
  GET  /quiz/{quiz_id}/results  — get score and concepts to review
  POST /quiz/{quiz_id}/answer   — grade an answer, advance to next question
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.quiz import AnswerRequest, AnswerResponse, QuizCreate, QuizResponse

router = APIRouter()


def _strip_reference_answers(questions: list[dict]) -> list[dict]:
    """Remove reference_answer from all question dicts before returning to client.

    MUST be called in: POST /quiz response, GET /quiz/{id}/results,
    POST /quiz/{id}/answer (next_question field). Never expose reference_answer.
    """
    return [
        {k: v for k, v in q.items() if k != "reference_answer"}
        for q in (questions or [])
    ]


@router.post("", response_model=QuizResponse, status_code=201)
async def create_quiz(body: QuizCreate):
    """Generate a quiz scoped to a course.

    Concept selection priority (D-18):
    1. Concepts with active struggle_signals first
    2. Concepts with most source coverage
    3. Random fill to num_questions

    Returns quiz with questions stripped of reference_answer.
    Wave 2 (04-04-PLAN.md) implements this.
    """
    raise HTTPException(status_code=501, detail="Not implemented — Wave 2")


@router.get("/{quiz_id}/results")
async def quiz_results(quiz_id: int):
    """Return score breakdown and concepts to review for a completed quiz.

    Same response shape as terminal POST /quiz/{id}/answer response (D-14).
    Strips reference_answer from all questions.
    Wave 2 (04-04-PLAN.md) implements this.
    """
    raise HTTPException(status_code=501, detail="Not implemented — Wave 2")


@router.post("/{quiz_id}/answer")
async def answer_question(quiz_id: int, body: AnswerRequest):
    """Grade a student's answer and advance to next question.

    MCQ: deterministic comparison against options[correct_index].
    short_answer/application: Claude tool_use grading (D-19).
    Mutates quiz.questions in-place; flag_modified required (D-12).
    On last answer: returns is_complete=True + score inline (D-13).
    Wave 2 (04-04-PLAN.md) implements this.
    """
    raise HTTPException(status_code=501, detail="Not implemented — Wave 2")
