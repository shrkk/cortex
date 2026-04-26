---
phase: 06-frontend
plan: 04
subsystem: frontend-flashcard-quiz
tags: [flashcard, quiz, css-3d-flip, post-answer, swr, backend-grading]
dependency_graph:
  requires:
    - 06-01 (TypeScript interfaces — QuizQuestion, AnswerResponse, Flashcard)
    - 06-02 (globals.css flashcard CSS 3D classes — .flashcard-container/.flashcard-inner/.flashcard-front/.flashcard-back)
    - 06-03 (NodeTypes.tsx onGenerateQuiz wiring to POST /quiz + router.push to /quiz/{id})
  provides:
    - FlashcardView: CSS 3D rotateY(180deg) flip, 480x280px card, Show Answer / Next buttons
    - QuizView: POST /quiz/{id}/answer per question, correct field names, feedback + final screen
    - QuizPage: GET /quiz/{id} via useSWR, passes quizId to QuizView
  affects:
    - frontend wave 5 (library page — references existing component patterns)
tech_stack:
  added: []
  patterns:
    - CSS 3D flip via .flashcard-container/.flashcard-inner.flipped classes from globals.css
    - apiFetch<AnswerResponse> POST pattern for quiz answer submission
    - useSWR with explicit fetcher function for QuizPage
    - Per-question grading state (not array accumulation)
key_files:
  created:
    - frontend/app/quiz/[id]/page.tsx
  modified:
    - frontend/components/FlashcardView.tsx
    - frontend/components/QuizView.tsx
decisions:
  - "FlashcardView: replaced reveal-in-place (show answer below divider) with CSS 3D rotateY flip using .flashcard-container/.flashcard-inner.flipped CSS classes from globals.css — matches UI-SPEC exactly"
  - "FlashcardView: added onBack prop for embedded mode (ReadingDrawer back navigation)"
  - "QuizView: per-question grading state (grading: AnswerResponse['grading'] | null) vs old boolean array accumulation"
  - "QuizView: handleNext triggered by button click after submit — no auto-advance on is_complete to avoid race with finalResult state"
  - "QuizPage: no AppShell wrapper — worktree does not have AppShell component; plan spec uses plain <main> element which is correct"
metrics:
  duration: ~8 minutes
  completed: "2026-04-26T04:35:00Z"
  tasks_completed: 2
  files_created: 1
  files_modified: 2
---

# Phase 6 Plan 4: FlashcardView CSS 3D Flip + QuizView Backend Grading Summary

**One-liner:** Rewrote FlashcardView to use CSS 3D rotateY(180deg) flip (480x280px, Show Answer/Next, no grading) and QuizView to call POST /quiz/{id}/answer with correct field names (question_id/type/question), backend feedback display, and final score screen; created QuizPage with GET /quiz/{id} SWR hook.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Rewrite FlashcardView with CSS 3D flip | f126be6 | frontend/components/FlashcardView.tsx |
| 2 | Rewrite QuizView with POST answer wiring + create QuizPage | 20dcd3d | frontend/components/QuizView.tsx, frontend/app/quiz/[id]/page.tsx |

---

## What Was Built

### Task 1: FlashcardView — CSS 3D Flip

**frontend/components/FlashcardView.tsx** (rewritten):

- **CSS 3D flip**: `.flashcard-container` (perspective) + `.flashcard-inner` + `.flashcard-inner.flipped` (rotateY 180deg) classes from globals.css, added in Wave 1
- **Card dimensions**: 480x280px (full), 320x200px when `embedded={true}`
- **Front face** (`.flashcard-front`): shows `card.front` at 24px/18px (embedded), cursor pointer, click to flip
- **Back face** (`.flashcard-back`): shows `card.back` at 14px after CSS 3D rotation
- **Buttons**: "Show Answer" (accent bg) when not flipped; "Next →" when flipped — no grading UI
- **Keyboard**: Space to flip, ArrowLeft/ArrowRight to navigate; event listener cleanup on unmount
- **Empty state**: "No flashcards yet" with explanation text (matches UI-SPEC copywriting)
- **onBack prop**: optional back button in embedded mode for ReadingDrawer navigation

### Task 2: QuizView — Backend Grading + QuizPage SWR

**frontend/components/QuizView.tsx** (rewritten):

- **Props**: `quizId: number` added (was missing; needed for POST URL)
- **POST /quiz/{id}/answer**: `apiFetch<AnswerResponse>` with `{ question_id: q.question_id, answer }` body
- **Field names fixed**: `q.question_id` (was q.id), `q.type` (was q.question_type), `q.question` (was q.prompt), removed q.explanation/q.topic references
- **Feedback UI**: After submit — correct/incorrect badge (green/red) + `grading.feedback` text from backend
- **"Next Question →" button**: appears after submit when not on last question
- **Final screen**: `correct_count / total correct` heading; `concepts_to_review` as concept ID badges; "Great work" fallback if no weak spots
- **MCQ options**: radio-style buttons with accentColor, disabled after submit
- **Free response**: textarea with 3 rows min, disabled after submit
- **Loading state**: "Grading…" button text during async submit

**frontend/app/quiz/[id]/page.tsx** (created):

- `useSWR<Quiz>` with `/quiz/${id}` key and explicit fetcher `(url: string) => apiFetch<Quiz>(url)`
- Error state: "Quiz generation failed. Make sure this course has processed sources." (matches UI-SPEC copy)
- Loading state: "Loading quiz…"
- Passes `quizId={quiz.id}` and `questions={quiz.questions}` to QuizView

---

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

### Notes

- The worktree does not contain `AppShell.tsx` or `ui/primitives.tsx` (these are in the main repo's frontend). The plan's QuizPage spec uses a plain `<main>` element, which is correct and matches the plan's exact implementation template. The old QuizPage (main repo) used AppShell but the plan's rewrite explicitly uses `<main style={{ minHeight: "100vh", ... }}>`.
- `tsconfig.tsbuildinfo` generated during tsc type check — left untracked (generated build artifact).

---

## Known Stubs

None — all UI is wired to real backend endpoints:
- FlashcardView renders `card.front` / `card.back` from API data
- QuizView calls POST /quiz/{id}/answer and renders `grading.feedback` from backend
- QuizPage fetches via GET /quiz/{id}

---

## Threat Flags

None — no new network surfaces beyond what the plan's threat model covers (POST /quiz/{id}/answer and GET /quiz/{id} are both accounted for in T-06-04-01 through T-06-04-04).

---

## Self-Check: PASSED

- FOUND: frontend/components/FlashcardView.tsx — contains "flashcard-inner", "Show Answer", no grading buttons
- FOUND: frontend/components/QuizView.tsx — contains "quiz/${quizId}/answer", "q.question_id", "q.question", "q.type"
- FOUND: frontend/app/quiz/[id]/page.tsx — contains "quizId={quiz.id}", "useSWR"
- FOUND: commit f126be6 (Task 1 — FlashcardView CSS 3D flip)
- FOUND: commit 20dcd3d (Task 2 — QuizView + QuizPage)
- TypeScript: no errors in new files (pre-existing errors in other worktree components are out of scope)
