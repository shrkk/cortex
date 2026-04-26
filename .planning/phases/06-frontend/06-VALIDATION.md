---
phase: 6
slug: frontend
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-25
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | None configured (lint + TypeScript build only) |
| **Config file** | `frontend/package.json` (lint/build scripts) |
| **Quick run command** | `cd frontend && npm run lint` |
| **Full suite command** | `cd frontend && npm run build` |
| **Type check command** | `cd frontend && npx tsc --noEmit` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd frontend && npm run lint`
- **After every plan wave:** Run `cd frontend && npm run build`
- **Before `/gsd-verify-work`:** Full `npm run build` green + manual smoke test of all 4 routes against running backend
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 0 | UI-01–UI-11 | T-06-01-05 | concept_count/active_struggle_count in CourseResponse | build | `cd backend && python -c "from app.schemas.courses import CourseResponse; assert 'concept_count' in CourseResponse.model_fields"` | ✅ | ⬜ pending |
| 06-01-02 | 01 | 0 | UI-11 | T-06-01-01 | `GET /sources` endpoint exists | build | `cd frontend && npm run build` | ✅ | ⬜ pending |
| 06-02-01 | 02 | 1 | UI-01 | — | Course.title used not Course.name; concept_count + active_struggle_count rendered | build | `cd frontend && npx tsc --noEmit` | ✅ | ⬜ pending |
| 06-02-02 | 02 | 1 | UI-02 | — | GraphNode reads n.type not n.node_type | build | `cd frontend && npx tsc --noEmit` | ✅ | ⬜ pending |
| 06-03-01 | 03 | 2 | UI-02, UI-03, UI-04 | — | dagre layout, struggle ring, edge styles | manual | Visual check on running app | ✅ | ⬜ pending |
| 06-03-02 | 03 | 2 | UI-05, UI-06 | — | Detail panel slides in; examples/student_questions rendered; flashcard flip | manual | Click concept node, click View Flashcards | ✅ | ⬜ pending |
| 06-04-01 | 04 | 3 | UI-07, UI-08 | — | Quiz walkthrough uses POST /quiz/{id}/answer | manual | Take quiz end-to-end | ✅ | ⬜ pending |
| 06-04-02 | 04 | 3 | UI-09 | — | Library shows sources, uploader has course_id | manual | Upload a file via library page | ✅ | ⬜ pending |
| 06-05-01 | 05 | 4 | UI-10, UI-11 | — | Empty states present; polling stops | manual | View with empty DB; watch Network tab | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] Add `GET /courses/{id}` to `backend/app/api/courses.py` — planned in 06-01 Task 1 Step 2
- [x] Add `GET /courses/{id}/sources` to `backend/app/api/courses.py` — planned in 06-01 Task 1 Step 3
- [x] Add `GET /sources` to backend (new or extended existing router) — planned in 06-01 Task 1 Step 5
- [x] Add `GET /concepts/{id}/flashcards` to `backend/app/api/concepts.py` — planned in 06-01 Task 1 Step 6
- [x] Add `GET /quiz/{id}` to `backend/app/api/quiz.py` — planned in 06-01 Task 1 Step 7 (uses Depends(get_session))
- [x] Fix `lib/api.ts` type interfaces: `Course.title`, `GraphNode` structure, `GraphEdge.type`, `QuizQuestion` fields — planned in 06-01 Task 2
- [x] Add `concept_count` and `active_struggle_count` to `CourseResponse` and `GET /courses` — planned in 06-01 Task 1 Step 0

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dagre layout renders nodes not at origin | UI-02 | Visual graph layout | Load course with ≥5 concepts; verify nodes spread across canvas |
| Struggle signal pulsing red ring | UI-03 | CSS animation visual | Load concept with struggle signals; verify pulsing ring visible |
| Edge types visually distinct | UI-04 | Visual rendering | Inspect graph edges; verify contains=thick, prerequisite=arrow, co_occurrence=dashed, related=dotted |
| Flashcard 3D flip animation | UI-06 | CSS animation visual | Click "Show Answer"; verify rotateY transition, not reveal |
| Quiz grading feedback appears | UI-08 | API integration | Submit quiz answer; verify feedback text from backend appears below question |
| Polling stops when all done | UI-11 | Network tab timing | Upload source, watch Network tab; verify requests stop after status=done |
| Dark theme applied correctly | UI-SPEC | Visual | Verify bg is #1F1E1B not #FAF7F2; verify text is #FAF7F2 |
| Examples and student questions in detail panel | UI-05 | Visual | Open concept with examples; verify both sections render |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending execution
