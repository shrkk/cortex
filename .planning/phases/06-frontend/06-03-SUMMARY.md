---
phase: 06-frontend
plan: 03
subsystem: frontend-graph-nodes + frontend-detail-panel
tags: [node-types, ui-spec, reading-drawer, struggle-signals, generate-quiz, examples, student-questions]
dependency_graph:
  requires:
    - 06-01 (TypeScript interfaces, backend endpoints)
    - 06-02 (dark theme CSS variables, cortex-pulse keyframe, globals.css)
  provides:
    - NodeTypes.tsx with all 4 node types at exact UI-SPEC colors/dimensions
    - ConceptNode struggle ring: box-shadow 0 0 0 3px #EF4444 + cortex-pulse animation
    - ReadingDrawer: struggle_signals as dict, gotchas amber highlight, examples, student_questions
    - CoursePage: onGenerateQuiz wired to POST /quiz with navigation to /quiz/{id}
    - CoursePage: ReadingDrawer conditionally rendered on selectedConceptId
  affects:
    - frontend wave 4 (library page references graph node styles)
    - frontend wave 5 (quiz page receives navigation from onGenerateQuiz)
tech_stack:
  added: []
  patterns:
    - ConceptNode diameter formula: d = 32 + min(max(source_count - 1, 0), 4) * 4 (D-02)
    - Struggle ring via CSS box-shadow (not fill change, per D-04)
    - cortex-pulse animation from globals.css applied via inline style
    - Object.entries() for Record<string,unknown> struggle_signals rendering
    - onGenerateQuiz async handler calls POST /quiz + router.push
key_files:
  created:
    - frontend/components/graph/NodeTypes.tsx
  modified:
    - frontend/app/courses/[id]/page.tsx
decisions:
  - "NodeTypes.tsx created fresh in worktree — file did not exist at wave 3 start (only GraphCanvas.tsx was in the graph/ directory)"
  - "ReadingDrawer.tsx was already correct from Wave 1 — struggle_signals Object.entries, var(--highlight-bg) gotchas, examples, student_questions all present; no changes needed"
  - "page.tsx: added onGenerateQuiz prop that calls POST /quiz with num_questions=7, routes to /quiz/{id} on success"
  - "ReadingDrawer wrapped in {selectedConceptId && ...} conditional (previously rendered unconditionally; component returned null anyway since concept=null, but conditional is more explicit and avoids unnecessary SWR mounts)"
metrics:
  duration: ~3 minutes
  completed: "2026-04-26T04:20:00Z"
  tasks_completed: 2
  files_created: 1
  files_modified: 1
---

# Phase 6 Plan 3: Node Visual Styles + ReadingDrawer Wiring Summary

**One-liner:** Created NodeTypes.tsx with all 4 node types at exact UI-SPEC colors/dimensions (CourseNode #C96442 60px, ConceptNode #3A3832 32-48px with cortex-pulse struggle ring, FlashcardNode #2A3D2F moss, QuizNode #3D2E1F amber-dashed), and wired ReadingDrawer's onGenerateQuiz to POST /quiz with navigation.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Apply UI-SPEC node visual styles to NodeTypes.tsx | 147ed27 | frontend/components/graph/NodeTypes.tsx (new) |
| 2 | Wire ReadingDrawer SWR + fix struggle_signals + render examples/student_questions | 064ab02 | frontend/app/courses/[id]/page.tsx |

---

## What Was Built

### Task 1: NodeTypes.tsx — All 4 Node Types

**frontend/components/graph/NodeTypes.tsx** (new file):

- **CourseNode**: 60px circle, `#C96442` terracotta fill, no border, `#FAF7F2` label centered inside. `role="button"` + `aria-label`. Handles visible.
- **ConceptNode**: 32–48px circle by `source_count` using formula `d = 32 + min(max(sc-1, 0), 4) * 4`. `#3A3832` fill, `rgba(255,255,255,0.15)` 1px border. Label below in `rgba(250,247,242,0.80)`. Struggle signal: `box-shadow: 0 0 0 3px #EF4444` + `animation: cortex-pulse 1.5s ease-in-out infinite` (no fill change, per D-04). Handles visible.
- **FlashcardNode**: 40px circle, `#2A3D2F` moss-tinted fill, `#6B8E5A` 1.5px solid border. No label on node. Both Handles.
- **QuizNode**: 40px circle, `#3D2E1F` amber-tinted fill, `#C18A3F` 1.5px dashed border. Small "Q" label inside. Both Handles.

All nodes use `React.memo`. All interactive nodes have `role="button"` and `aria-label`.

### Task 2: CoursePage + ReadingDrawer

**frontend/app/courses/[id]/page.tsx** — two changes:

1. **Conditional render**: `{selectedConceptId && <ReadingDrawer ... />}` — previously unconditional (component returned null when concept=null, but conditional is cleaner)
2. **onGenerateQuiz prop**: async handler calls `apiFetch<{id: number}>("/quiz", { method: "POST", body: JSON.stringify({ course_id: parseInt(id, 10), num_questions: 7 }) })` then `router.push('/quiz/${quiz.id}')`. Console error on failure (matches UI-SPEC copy: "Quiz generation failed. Make sure this course has processed sources.").

**frontend/components/ReadingDrawer.tsx** — already correct from Wave 1 (no changes needed):
- `Object.entries(concept.struggle_signals!)` — dict iteration correct
- `var(--highlight-bg)` for gotcha amber highlight — correct
- `concept.examples` section — present and rendered
- `concept.student_questions` section — present and rendered
- `onGenerateQuiz` prop wired to "Generate quiz" button — present

---

## Pre-existing Correct State (no changes needed)

ReadingDrawer.tsx was already fully compliant with UI-05 requirements from Wave 1's comprehensive interface fix. The plan's Task 2 description of "fixing" struggle_signals and "adding" examples/student_questions was already accomplished in plan 06-01 Task 2. This plan's only needed change was the `onGenerateQuiz` wiring in CoursePage.

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Functionality] ReadingDrawer rendered unconditionally without selectedConceptId guard**
- **Found during:** Task 2 — reviewing CoursePage render
- **Issue:** ReadingDrawer was rendered outside `{selectedConceptId && ...}` — functional but creates unnecessary SWR mounts even when no concept is selected
- **Fix:** Wrapped ReadingDrawer in `{selectedConceptId && ...}` conditional per plan spec
- **Files modified:** frontend/app/courses/[id]/page.tsx
- **Commit:** 064ab02

---

## Known Stubs

None — all node visual styles are hardcoded to UI-SPEC values. The `onGenerateQuiz` calls a real backend endpoint. The `concept.examples` and `concept.student_questions` render real API data when available.

---

## Threat Flags

None — this plan applies node visual styling and wires existing endpoints. No new network surfaces introduced beyond the `POST /quiz` call which was already in the backend from Phase 5. Course ID is from URL params; backend validates ownership.

---

## Self-Check: PASSED

- FOUND: frontend/components/graph/NodeTypes.tsx (contains `#C96442`, `#3A3832`, `#2A3D2F`, `#3D2E1F`, `cortex-pulse`, `#EF4444`)
- FOUND: frontend/app/courses/[id]/page.tsx (modified — contains `onGenerateQuiz`, `selectedConceptId &&`)
- FOUND: commit 147ed27 (Task 1 — NodeTypes.tsx)
- FOUND: commit 064ab02 (Task 2 — page.tsx onGenerateQuiz)
- TypeScript: `npx tsc --noEmit` exits 0 (verified via main repo toolchain)
