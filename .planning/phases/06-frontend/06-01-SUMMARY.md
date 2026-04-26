---
phase: 06-frontend
plan: 01
subsystem: backend-api + frontend-types
tags: [api-fixes, typescript, endpoints, graph, quiz, flashcards, sources]
dependency_graph:
  requires: []
  provides:
    - GET /sources
    - GET /courses/{id}
    - GET /courses/{id}/sources
    - GET /concepts/{id}/flashcards
    - GET /quiz/{id}
    - concept_count and active_struggle_count in GET /courses
    - source_count in graph concept node data
    - corrected TypeScript interfaces in frontend/lib/api.ts
  affects:
    - frontend wave 2 (SWR hooks)
    - frontend wave 3 (graph, detail panel, quiz)
    - frontend wave 4 (library page)
tech_stack:
  added:
    - FlashcardResponse Pydantic schema (backend/app/schemas/concepts.py)
    - SourceResponse Pydantic schema (backend/app/schemas/courses.py)
    - backend/app/api/sources.py (new file)
    - GraphNodeData TypeScript interface (frontend/lib/api.ts)
    - AnswerResponse TypeScript interface (frontend/lib/api.ts)
  patterns:
    - Correlated SQLAlchemy subqueries for aggregate counts in list_courses
    - ConceptSource IN-query for source_count per concept in get_course_graph
    - Depends(get_session) pattern for get_quiz (not AsyncSessionLocal)
    - Object.entries() iteration for Record<string,unknown> struggle_signals
key_files:
  created:
    - backend/app/api/sources.py
  modified:
    - backend/app/schemas/courses.py
    - backend/app/api/courses.py
    - backend/app/schemas/concepts.py
    - backend/app/api/concepts.py
    - backend/app/api/quiz.py
    - backend/app/api/router.py
    - frontend/lib/api.ts
    - frontend/app/page.tsx
    - frontend/app/courses/[id]/page.tsx
    - frontend/components/graph/GraphCanvas.tsx
    - frontend/components/Sidebar.tsx
    - frontend/components/FlashcardView.tsx
    - frontend/components/QuizView.tsx
    - frontend/components/ReadingDrawer.tsx
decisions:
  - "struggle_count in active_struggle_count subquery uses cast(JSON, String) != '{}' to detect empty JSONB dict"
  - "source_count defaults to 1 in _build_graph_payload when concept has no concept_sources rows"
  - "GET /quiz/{quiz_id} uses Depends(get_session) not AsyncSessionLocal for consistency with other endpoints"
  - "struggle_signals rendered in ReadingDrawer via Object.entries() since backend returns dict not array"
  - "QuizView: explanation field removed; grading.feedback used instead (matches backend AnswerResponse)"
metrics:
  duration: ~25 minutes
  completed: "2026-04-26T04:01:41Z"
  tasks_completed: 2
  files_created: 1
  files_modified: 13
---

# Phase 6 Plan 1: API Shape Fixes + Missing Endpoints Summary

**One-liner:** Added 5 missing backend endpoints (GET /sources, /courses/{id}, /courses/{id}/sources, /concepts/{id}/flashcards, /quiz/{id}), concept stats aggregates (concept_count, active_struggle_count), source_count to graph nodes, and corrected all 4 TypeScript interface mismatches in lib/api.ts.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add SourceResponse schema + 5 missing backend endpoints + concept stats aggregates | e911c09 | backend/app/schemas/courses.py, api/courses.py, api/sources.py, api/concepts.py, schemas/concepts.py, api/quiz.py, api/router.py |
| 2 | Fix all 4 TypeScript interface mismatches in frontend/lib/api.ts + update components | f4988dd | frontend/lib/api.ts + 7 component files |

---

## What Was Built

### Task 1: Backend API Additions

**backend/app/schemas/courses.py**
- Extended `CourseResponse` with `concept_count: int = 0` and `active_struggle_count: int = 0` (optional with defaults so POST /courses and other single-course responses continue to work)
- Added `SourceResponse` Pydantic schema with `from_attributes = True` for ORM serialization

**backend/app/api/courses.py**
- Updated `list_courses` to use correlated SQLAlchemy subqueries on the `concepts` table to compute `concept_count` and `active_struggle_count` per course (efficient: single query, no N+1)
- Added `GET /courses/{course_id}` — single course by ID with user_id=1 ownership guard
- Added `GET /courses/{course_id}/sources` — sources list ordered by created_at desc with ownership check
- Added `source_count` to `_build_graph_payload` concept node data via a ConceptSource IN-query in `get_course_graph`; defaults to 1 if concept has no concept_sources rows
- Updated `_build_graph_payload` signature to accept `source_count_by_concept: dict[int, int] | None = None`

**backend/app/api/sources.py** (new file)
- `GET /sources` — all sources for user_id=1 via Course JOIN; used by library page

**backend/app/schemas/concepts.py**
- Added `FlashcardResponse` schema with all flashcard fields and `from_attributes = True`

**backend/app/api/concepts.py**
- Added `GET /concepts/{concept_id}/flashcards` — ownership check via Course.user_id=1 JOIN, then returns flashcards ordered by id

**backend/app/api/quiz.py**
- Added `GET /quiz/{quiz_id}` using `Depends(get_session)` (not AsyncSessionLocal) with `_strip_reference_answers()` called before returning (T-06-01-02 threat mitigation)

**backend/app/api/router.py**
- Mounted `sources.router` at `/sources`

### Task 2: TypeScript Interface Fixes

**frontend/lib/api.ts** — corrected 4 interface mismatches and added 2 new interfaces:

1. **Course** — `name: string` → `title: string`; added `concept_count: number` and `active_struggle_count: number` (was missing/wrong field names)
2. **GraphNode** — flat structure → `type: string` at root + `data: GraphNodeData` nested (was `node_type` + flat fields)
3. **GraphEdge** — `edge_type` → `type` at root (backend uses `type`)
4. **QuizQuestion** — `id/question_type/prompt` → `question_id/type/question`; corrected type values `"mcq"/"free"` → `"mcq"/"short_answer"/"application"`
5. **New: `GraphNodeData`** — nested data struct for graph nodes
6. **New: `AnswerResponse`** — POST /quiz/{id}/answer response shape
7. **Concept** — `struggle_signals` changed from `Array<{label,detail}>` to `Record<string,unknown>|null`
8. **Source** — added `course_id: number`
9. **Flashcard** — added `concept_id: number`; removed `concept_title`
10. **Quiz** — added `course_id: number`

**Frontend component fixes** (cascaded from interface corrections):
- `GraphCanvas.tsx` — `buildLayout` now reads `n.type` (not `n.node_type`), `n.data.*` (not flat), `e.type` (not `e.edge_type`)
- `app/page.tsx` — `c.name` → `c.title`; `c.struggle_count` → `c.active_struggle_count`
- `app/courses/[id]/page.tsx` — `course?.name` → `course?.title`; `n.node_type` → `n.type`; `n.has_struggle` → `n.data.has_struggle_signals`
- `Sidebar.tsx` — `c.struggle_count` → `c.active_struggle_count`; `c.name` → `c.title`
- `FlashcardView.tsx` — removed `card.concept_title` reference (field no longer exists)
- `QuizView.tsx` — `q.question_type` → `q.type`; `q.prompt` → `q.question`; `q.explanation` → `q.grading?.feedback`; `"free"` → `"short_answer" | "application"`
- `ReadingDrawer.tsx` — `struggle_signals` now rendered via `Object.entries()` (dict not array); `s.type` → `s.source_type`; removed `s.meta` reference

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Functionality] Component files used old API interface field names**
- **Found during:** Task 2 — `npx tsc --noEmit` showed 37 TypeScript errors across 6 files
- **Issue:** All frontend component files (GraphCanvas, page.tsx, Sidebar, FlashcardView, QuizView, ReadingDrawer) were using the old broken interface field names that the plan's Task 2 was correcting in lib/api.ts
- **Fix:** Updated all 7 component files to use the corrected field names from the new interfaces
- **Files modified:** frontend/app/page.tsx, frontend/app/courses/[id]/page.tsx, frontend/components/graph/GraphCanvas.tsx, frontend/components/Sidebar.tsx, frontend/components/FlashcardView.tsx, frontend/components/QuizView.tsx, frontend/components/ReadingDrawer.tsx
- **Commit:** f4988dd (included in Task 2 commit since these are inseparable from the interface fix)

---

## Known Stubs

None — all data flows from real backend endpoints. The frontend components render real API data via SWR hooks.

---

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: info_disclosure | backend/app/api/quiz.py | GET /quiz/{id} correctly mitigated via _strip_reference_answers() before return (T-06-01-02) |
| threat_flag: info_disclosure | backend/app/api/concepts.py | GET /concepts/{id}/flashcards correctly mitigated via Course.user_id=1 JOIN ownership check (T-06-01-03) |

---

## Self-Check: PASSED

- FOUND: backend/app/api/sources.py
- FOUND: frontend/lib/api.ts
- FOUND: .planning/phases/06-frontend/06-01-SUMMARY.md
- FOUND: commit e911c09 (Task 1)
- FOUND: commit f4988dd (Task 2)
