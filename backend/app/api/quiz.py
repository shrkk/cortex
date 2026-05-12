"""Quiz API endpoints (Phase 4).

Routes:
  POST /quiz                    — generate a new quiz for a course (QUIZ-02, QUIZ-03)
  GET  /quiz/{quiz_id}/results  — get score and concepts to review (QUIZ-05)
  POST /quiz/{quiz_id}/answer   — grade an answer, advance to next question (QUIZ-04, QUIZ-06)

Key design decisions (from CONTEXT.md):
- D-12: quiz.questions mutated in-place; flag_modified required
- D-13: terminal answer includes is_complete=True + score inline
- D-14: GET /quiz/{id}/results returns same shape as terminal answer
- D-15: One LLM call for full quiz (not per-concept)
- D-16: round(N*0.4) MCQ, round(N*0.3) short_answer, remainder application
- D-17: MCQ has options + correct_index; free-response has reference_answer (never returned)
- D-18: Concept priority: struggle_signals > source_count > random
- D-19: Free-response graded by Claude tool_use; reference_answer in system prompt
"""
from __future__ import annotations

import random

import anthropic
import sqlalchemy as sa
import sqlalchemy.orm.attributes as _orm_attrs
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import app.core.config as _config
from app.core.database import AsyncSessionLocal, get_session
from app.models.models import Concept, ConceptSource, Quiz
from app.schemas.quiz import AnswerRequest, AnswerResponse, QuizCreate, QuizResponse

router = APIRouter()


# ---------------------------------------------------------------------------
# Tool schemas (additionalProperties: false — matches EXTRACT-04 convention)
# ---------------------------------------------------------------------------

QUIZ_TOOL = {
    "name": "generate_quiz",
    "description": (
        "Generate quiz questions for a set of course concepts. "
        "Mix MCQ, short_answer, and application types per the requested distribution. "
        "Include reference_answer for short_answer and application questions "
        "(used for grading only — never shown to the student)."
    ),
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["questions"],
        "properties": {
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["type", "question", "concept_id"],
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["mcq", "short_answer", "application"]
                        },
                        "question": {"type": "string"},
                        "concept_id": {
                            "type": "integer",
                            "description": "ID of the concept this question tests"
                        },
                        "options": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "MCQ only: 4 answer options"
                        },
                        "correct_index": {
                            "type": "integer",
                            "description": "MCQ only: 0-based index of correct option"
                        },
                        "reference_answer": {
                            "type": "string",
                            "description": "short_answer/application only: used for grading, never shown"
                        }
                    }
                }
            }
        }
    }
}

GRADE_TOOL = {
    "name": "grade_answer",
    "description": "Grade a student's free-response answer against the reference answer.",
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["correct", "feedback"],
        "properties": {
            "correct": {
                "type": "boolean",
                "description": "True if the student's answer is substantially correct"
            },
            "feedback": {
                "type": "string",
                "description": "1-2 sentences of constructive feedback"
            }
        }
    }
}


# ---------------------------------------------------------------------------
# Helper: strip reference_answer from all question dicts
# ---------------------------------------------------------------------------

def _strip_reference_answers(questions: list[dict]) -> list[dict]:
    """Remove reference_answer from all question dicts before returning to client.

    MUST be called in: POST /quiz response, GET /quiz/{id}/results,
    POST /quiz/{id}/answer (next_question field). Never expose reference_answer.
    """
    return [
        {k: v for k, v in q.items() if k != "reference_answer"}
        for q in (questions or [])
    ]


# ---------------------------------------------------------------------------
# Helper: D-16 question type distribution
# ---------------------------------------------------------------------------

def _question_distribution(num_questions: int) -> tuple[int, int, int]:
    """Return (mcq_count, short_answer_count, application_count) per D-16 formula.

    Formula: round(N*0.4) MCQ, round(N*0.3) short_answer, remainder application.
    Example: N=7 → (3, 2, 2).
    """
    mcq = round(num_questions * 0.4)
    short = round(num_questions * 0.3)
    application = num_questions - mcq - short
    return mcq, short, max(0, application)


# ---------------------------------------------------------------------------
# Helper: D-19 free-response grading
# ---------------------------------------------------------------------------

async def _grade_free_response(
    question: str,
    student_answer: str,
    reference_answer: str,
    client: anthropic.AsyncAnthropic,
) -> dict:
    """Grade a student's free-response answer via Claude tool_use (D-19).

    reference_answer injected into system prompt — not shown to student.
    Returns {"correct": bool, "feedback": "1-2 sentence string"}.
    """
    message = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=(
            f"You are grading a student's response to a quiz question. "
            f"Reference answer: {reference_answer}"
        ),
        tools=[GRADE_TOOL],
        tool_choice={"type": "tool", "name": "grade_answer"},
        messages=[{
            "role": "user",
            "content": f"Question: {question}\n\nStudent answer: {student_answer}"
        }]
    )
    tool_block = next(b for b in message.content if b.type == "tool_use")
    return tool_block.input  # {"correct": bool, "feedback": str} — already Python dict


# ---------------------------------------------------------------------------
# Helper: generate quiz questions via single LLM call (D-15)
# ---------------------------------------------------------------------------

async def _generate_quiz_questions(
    concepts: list,
    num_questions: int,
    client: anthropic.AsyncAnthropic,
) -> list[dict]:
    """Single Claude tool_use call to generate all quiz questions (D-15).

    Builds context from selected concepts (title, definition, gotchas).
    Returns list of question dicts including reference_answer (for grading).
    """
    mcq_count, short_count, app_count = _question_distribution(num_questions)

    context = "\n\n".join(
        f"Concept ID {c.id}: {c.title}\n"
        f"Definition: {c.definition or '(none)'}\n"
        f"Gotchas: {'; '.join(c.gotchas or []) or '(none)'}"
        for c in concepts
    )

    message = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        tools=[QUIZ_TOOL],
        tool_choice={"type": "tool", "name": "generate_quiz"},
        messages=[{
            "role": "user",
            "content": (
                f"Generate a quiz with exactly {num_questions} questions "
                f"({mcq_count} MCQ, {short_count} short_answer, {app_count} application) "
                f"from the following course concepts. Weight questions toward concepts with "
                f"more gotchas.\n\n{context}"
            )
        }]
    )

    if message.stop_reason != "tool_use":
        return []  # Fallback — should not happen with tool_choice forcing

    tool_block = next(b for b in message.content if b.type == "tool_use")
    return tool_block.input.get("questions", [])


# ---------------------------------------------------------------------------
# POST /quiz — generate a new quiz for a course
# ---------------------------------------------------------------------------

@router.get("")
async def list_quizzes(session: AsyncSession = Depends(get_session)):
    """Return all quizzes ordered newest first, with question count."""
    result = await session.execute(
        sa.select(Quiz).order_by(Quiz.created_at.desc())
    )
    quizzes = result.scalars().all()
    return [
        {
            "id": q.id,
            "course_id": q.course_id,
            "created_at": q.created_at,
            "question_count": len(q.questions) if q.questions else 0,
        }
        for q in quizzes
    ]


@router.post("", response_model=QuizResponse, status_code=201)
async def create_quiz(body: QuizCreate):
    """Generate a quiz scoped to a course.

    Concept selection priority (D-18):
    1. Concepts with active struggle_signals first
    2. Concepts with most source coverage (len(concept_sources))
    3. Random fill

    num_questions capped at len(concepts) * 2 (D-15 special case).
    reference_answer stripped from response (security invariant).
    """
    if not _config.settings.anthropic_api_key:
        raise HTTPException(503, "Quiz generation requires ANTHROPIC_API_KEY")

    # Load all concepts for this course with concept_sources for priority sort
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            sa.select(Concept)
            .where(Concept.course_id == body.course_id)
            .options(selectinload(Concept.concept_sources))
        )
        concepts = result.scalars().all()

    if not concepts:
        raise HTTPException(404, "No concepts found for this course")

    # D-18: Sort concepts by priority (struggle signals > source coverage > random)
    def _concept_priority(c: Concept):
        has_signals = bool(c.struggle_signals)
        source_count = len(c.concept_sources)
        return (not has_signals, -source_count, random.random())

    concepts_sorted = sorted(concepts, key=_concept_priority)

    # Cap num_questions at len(concepts) * 2 (concepts can appear in multiple question types)
    max_questions = len(concepts) * 2
    num_q = min(body.num_questions, max_questions)

    # Select enough concepts to cover num_questions (at most one concept per question)
    selected_concepts = concepts_sorted[:num_q]

    # Single LLM call for all questions (D-15)
    client = anthropic.AsyncAnthropic(api_key=_config.settings.anthropic_api_key)
    questions = await _generate_quiz_questions(selected_concepts, num_q, client)

    # Assign question_id (0-based index) and initial state (D-12 / critical implementation detail)
    for idx, q in enumerate(questions):
        q["question_id"] = idx
        q["answered"] = False
        q["answer"] = None
        q["grading"] = None

    # Persist quiz with questions including reference_answer
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            insert(Quiz).values(
                course_id=body.course_id,
                questions=questions,  # stored with reference_answer
            ).returning(Quiz.id)
        )
        quiz_id = result.scalar_one()
        await session.commit()

    # Strip reference_answer before returning to client
    return QuizResponse(
        id=quiz_id,
        course_id=body.course_id,
        questions=_strip_reference_answers(questions),
    )


# ---------------------------------------------------------------------------
# GET /quiz/{quiz_id} — fetch quiz by ID for quiz page initial load (UI-08)
# ---------------------------------------------------------------------------

@router.get("/{quiz_id}", response_model=QuizResponse)
async def get_quiz(quiz_id: int, session: AsyncSession = Depends(get_session)):
    """Return a quiz with questions (reference_answer stripped) by quiz ID.

    Security: reference_answer is stripped via _strip_reference_answers before returning (T-06-01-02).
    """
    result = await session.execute(
        sa.select(Quiz).where(Quiz.id == quiz_id)
    )
    quiz = result.scalar_one_or_none()
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return QuizResponse(
        id=quiz.id,
        course_id=quiz.course_id,
        questions=_strip_reference_answers(quiz.questions or []),
    )


# ---------------------------------------------------------------------------
# GET /quiz/{quiz_id}/results — score and concepts to review
# ---------------------------------------------------------------------------

@router.get("/{quiz_id}/results")
async def quiz_results(quiz_id: int):
    """Return score breakdown and concepts to review for a completed quiz (QUIZ-05).

    Same response shape as terminal POST /quiz/{id}/answer response (D-14).
    Strips reference_answer from all questions.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            sa.select(Quiz).where(Quiz.id == quiz_id)
        )
        quiz = result.scalar_one_or_none()

    if not quiz:
        raise HTTPException(404, "Quiz not found")

    questions = quiz.questions or []
    answered_questions = [q for q in questions if q.get("answered")]

    correct_count = sum(
        1 for q in answered_questions
        if (q.get("grading") or {}).get("correct")
    )
    total = len(questions)
    score = round(correct_count / total, 2) if total else 0.0

    concepts_to_review = list({
        q["concept_id"] for q in questions
        if q.get("answered") and not (q.get("grading") or {}).get("correct")
    })

    return {
        "is_complete": all(q.get("answered") for q in questions),
        "score": score,
        "correct_count": correct_count,
        "total": total,
        "concepts_to_review": concepts_to_review,
        "questions": _strip_reference_answers(questions),  # strip reference_answer
    }


# ---------------------------------------------------------------------------
# POST /quiz/{quiz_id}/answer — grade an answer, return next question or results
# ---------------------------------------------------------------------------

@router.post("/{quiz_id}/answer")
async def answer_question(quiz_id: int, body: AnswerRequest):
    """Grade a student's answer and advance to next question (QUIZ-04, QUIZ-06).

    MCQ: deterministic comparison against options[correct_index].
    short_answer/application: Claude tool_use grading (D-19).
    Mutates quiz.questions in-place; flag_modified required before commit (D-12).

    Returns:
    - {grading, next_question} while questions remain
    - {grading, next_question: null, is_complete: true, score, correct_count, total, concepts_to_review}
      when last question is answered (D-13)
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            sa.select(Quiz).where(Quiz.id == quiz_id)
        )
        quiz = result.scalar_one_or_none()
        if not quiz:
            raise HTTPException(404, "Quiz not found")

        questions = quiz.questions or []
        target_q = next(
            (q for q in questions if q.get("question_id") == body.question_id),
            None,
        )
        if target_q is None:
            raise HTTPException(404, f"Question {body.question_id} not found in quiz {quiz_id}")

        if target_q.get("answered"):
            raise HTTPException(409, f"Question {body.question_id} already answered")

        # Grade the answer
        if target_q["type"] == "mcq":
            option_text = target_q["options"][target_q["correct_index"]]
            correct = body.answer.strip().lower() == option_text.strip().lower()
            grading: dict = {
                "correct": correct,
                "feedback": "Correct!" if correct else f"The correct answer is: {option_text}",
            }
        else:
            # Free-response: Claude grading (D-19)
            if not _config.settings.anthropic_api_key:
                raise HTTPException(503, "Answer grading requires ANTHROPIC_API_KEY")
            client = anthropic.AsyncAnthropic(api_key=_config.settings.anthropic_api_key)
            grading = await _grade_free_response(
                question=target_q["question"],
                student_answer=body.answer,
                reference_answer=target_q.get("reference_answer", ""),
                client=client,
            )

        # Mutate question in-place (D-12)
        target_q["answered"] = True
        target_q["answer"] = body.answer
        target_q["grading"] = grading

        # CRITICAL: flag_modified tells SQLAlchemy this JSON column is dirty
        _orm_attrs.flag_modified(quiz, "questions")
        await session.commit()

        # Determine next question and completion state
        next_q = next((q for q in questions if not q.get("answered")), None)
        all_answered = next_q is None

        response: dict = {
            "grading": grading,
            "next_question": _strip_reference_answers([next_q])[0] if next_q else None,
        }

        if all_answered:
            # D-13: inline results on last answer — client does not need separate GET call
            correct_count = sum(
                1 for q in questions
                if (q.get("grading") or {}).get("correct")
            )
            total = len(questions)
            concepts_to_review = list({
                q["concept_id"] for q in questions
                if not (q.get("grading") or {}).get("correct")
            })
            response.update({
                "is_complete": True,
                "score": round(correct_count / total, 2) if total else 0.0,
                "correct_count": correct_count,
                "total": total,
                "concepts_to_review": concepts_to_review,
            })

    return response
