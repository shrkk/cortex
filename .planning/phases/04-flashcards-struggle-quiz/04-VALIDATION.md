---
phase: 4
slug: flashcards-struggle-quiz
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-25
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + pytest-asyncio 0.24.0 |
| **Config file** | `backend/pytest.ini` (`asyncio_mode = auto`, `testpaths = tests`) |
| **Quick run command** | `pytest tests/test_flashcards.py tests/test_signals.py tests/test_quiz_api.py -x` |
| **Full suite command** | `pytest tests/ -x` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_flashcards.py tests/test_signals.py tests/test_quiz_api.py -x`
- **After every plan wave:** Run `pytest tests/ -x`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 01 | 0 | FLASH-01..06 | — | N/A | unit stubs | `pytest tests/test_flashcards.py -x` | ❌ W0 | ⬜ pending |
| 4-01-02 | 01 | 0 | STRUGGLE-01..05 | — | N/A | unit stubs | `pytest tests/test_signals.py -x` | ❌ W0 | ⬜ pending |
| 4-01-03 | 01 | 0 | QUIZ-01..06 | — | Strip reference_answer | unit stubs | `pytest tests/test_quiz_api.py -x` | ❌ W0 | ⬜ pending |
| 4-02-01 | 02 | 1 | FLASH-01, FLASH-02 | — | N/A | unit | `pytest tests/test_flashcards.py::test_flashcard_generation tests/test_flashcards.py::test_card_types -x` | ❌ W0 | ⬜ pending |
| 4-02-02 | 02 | 1 | FLASH-04, FLASH-06 | — | N/A | unit | `pytest tests/test_flashcards.py::test_idempotency tests/test_flashcards.py::test_no_srs_columns -x` | ❌ W0 | ⬜ pending |
| 4-03-01 | 03 | 1 | STRUGGLE-01 | — | N/A | unit | `pytest tests/test_signals.py::test_repeated_confusion -x` | ❌ W0 | ⬜ pending |
| 4-03-02 | 03 | 1 | STRUGGLE-02 | — | N/A | unit | `pytest tests/test_signals.py::test_retention_gap -x` | ❌ W0 | ⬜ pending |
| 4-03-03 | 03 | 1 | STRUGGLE-03 | — | N/A | unit | `pytest tests/test_signals.py::test_gotcha_dense -x` | ❌ W0 | ⬜ pending |
| 4-03-04 | 03 | 1 | STRUGGLE-04, STRUGGLE-05 | — | N/A | unit | `pytest tests/test_signals.py::test_practice_failure tests/test_signals.py::test_signals_written -x` | ❌ W0 | ⬜ pending |
| 4-04-01 | 04 | 2 | QUIZ-02, QUIZ-03 | DoS: cap num_questions | cap at len(concepts)*2 before LLM call | unit | `pytest tests/test_quiz_api.py::test_create_quiz tests/test_quiz_api.py::test_question_distribution -x` | ❌ W0 | ⬜ pending |
| 4-04-02 | 04 | 2 | QUIZ-04, QUIZ-05 | Info disclosure: reference_answer | _strip_reference_answers() called in all response paths | unit | `pytest tests/test_quiz_api.py::test_free_response_grading tests/test_quiz_api.py::test_quiz_results -x` | ❌ W0 | ⬜ pending |
| 4-04-03 | 04 | 2 | QUIZ-06 | — | flag_modified called before commit | unit | `pytest tests/test_quiz_api.py::test_answer_persisted -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_flashcards.py` — stubs for FLASH-01 through FLASH-06
- [ ] `tests/test_signals.py` — stubs for STRUGGLE-01 through STRUGGLE-05
- [ ] `tests/test_quiz_api.py` — stubs for QUIZ-01 through QUIZ-06
- [ ] `backend/app/pipeline/flashcards.py` — importable module stub (`run_flashcards` defined as `pass`)
- [ ] `backend/app/pipeline/signals.py` — importable module stub (`run_signals` defined as `pass`)
- [ ] `backend/app/api/quiz.py` — router stub (routes defined, returning 501)
- [ ] `backend/app/schemas/quiz.py` — Pydantic schemas for QuizCreate, QuizResponse, AnswerRequest, AnswerResponse

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Flashcard cards display correctly flip front→back | FLASH-05 | Frontend display toggle — Phase 6 scope | N/A (Phase 4 ensures no DB write on flip; no SRS columns) |
| Struggle signal pulsing indicator on graph node | STRUGGLE-06 | Frontend indicator — Phase 6 scope | N/A (Phase 4 writes signals to DB; Phase 6 reads them) |
| End-to-end quiz walkthrough UX | QUIZ-03 | Full quiz flow requires browser | After Phase 6: POST /quiz → POST /quiz/{id}/answer × N → GET /quiz/{id}/results |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
