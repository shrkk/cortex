---
phase: 06-frontend
plan: 02
subsystem: frontend-theme + frontend-data-wiring
tags: [dark-theme, css-variables, graph-canvas, dashboard, course-page, quiz-routing, polling]
dependency_graph:
  requires:
    - 06-01 (TypeScript interfaces, backend endpoints)
  provides:
    - Dark Cortex palette CSS variables applied to globals.css
    - Flashcard 3D flip CSS (.flashcard-inner.flipped)
    - cortex-pulse keyframe for struggle signal ring
    - GraphCanvas onNodeClick passes nodeData to parent (quiz_id routing)
    - CoursePage quiz node click routes to /quiz/{id}
    - CoursePage "Updating..." polling indicator while sources pending
    - EDGE_STYLE constants matching UI-SPEC dark palette (rgba white values)
  affects:
    - frontend wave 3 (all graph node visual rendering)
    - frontend wave 4 (library page uses --paper, --surface tokens)
    - frontend wave 5 (quiz page uses --ink, --accent tokens)
tech_stack:
  added: []
  patterns:
    - next.config.mjs (renamed from .ts — Next.js 14 does not support .ts config files)
    - onNodeClick callback passes node.data for quiz_id routing
    - hasPending pulsing indicator with CSS pulse animation
key_files:
  created:
    - frontend/app/globals.css
    - frontend/next.config.mjs
  modified:
    - frontend/components/graph/GraphCanvas.tsx
    - frontend/app/courses/[id]/page.tsx
decisions:
  - "next.config.ts renamed to next.config.mjs — Next.js 14 does not support TypeScript config files, build was failing"
  - "EDGE_STYLE constants updated to UI-SPEC rgba white values (dark theme) instead of CSS variable references"
  - "GraphCanvas onNodeClick now passes node.data as third argument enabling quiz_id extraction in CoursePage"
  - "hasPending polling indicator positioned absolute bottom-70 with dark semi-transparent background"
  - "Background dot color updated to rgba(255,255,255,0.06) for dark canvas visibility"
metrics:
  duration: ~20 minutes
  completed: "2026-04-25T21:30:00Z"
  tasks_completed: 2
  files_created: 2
  files_modified: 2
---

# Phase 6 Plan 2: Dark Theme + Data Wiring Fixes Summary

**One-liner:** Applied dark Cortex palette (#1F1E1B/#14120F/#FAF7F2) to globals.css, added 3D flashcard flip CSS + cortex-pulse keyframe, fixed GraphCanvas edge styles for dark theme, wired quiz node click routing to /quiz/{id}, and added polling "Updating..." indicator.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Override globals.css with dark Cortex palette + fix next.config | a98965d | frontend/app/globals.css, frontend/next.config.mjs |
| 2 | Fix GraphCanvas onNodeClick, EDGE_STYLE, CoursePage quiz routing + polling indicator | b541d25 | frontend/components/graph/GraphCanvas.tsx, frontend/app/courses/[id]/page.tsx |

---

## What Was Built

### Task 1: Dark Cortex Palette + CSS Infrastructure

**frontend/app/globals.css** (new file — was untracked):
- Replaced entire `:root` CSS variables block with dark Cortex palette from UI-SPEC §Color
- `--paper: #1F1E1B` (was `#FAF7F2` — flipped from light to dark)
- `--surface: #14120F` (was `#FDFBF7`)
- `--ink: #FAF7F2` (was `#1F1E1B` — flipped text color)
- Borders converted from hex to rgba white-overlay (`rgba(255,255,255,0.06)`, `rgba(255,255,255,0.15)`)
- Shadows updated for dark background (`rgba(0,0,0,0.20-0.40)` values)
- Mastery soft colors converted to rgba overlays
- Highlight and accent-soft converted to rgba overlays for dark bg
- Added flashcard 3D flip CSS: `.flashcard-container`, `.flashcard-inner`, `.flashcard-front/back`
- Added `@keyframes cortex-pulse` for struggle signal pulsing ring
- Updated React Flow overrides to use dark tokens

**frontend/next.config.mjs** (renamed from next.config.ts):
- Next.js 14 does not support `.ts` config extension — build was failing with "Configuring Next.js via 'next.config.ts' is not supported"
- Converted to `.mjs` with equivalent config

### Task 2: GraphCanvas + CoursePage Fixes

**frontend/components/graph/GraphCanvas.tsx**:
- Updated `EDGE_STYLE` constants to UI-SPEC dark palette: rgba white strokes instead of CSS variable references (variables resolve to light theme values at build time in some renderers)
  - `contains`: `rgba(255,255,255,0.25)` 2.5px solid
  - `prerequisite`: `rgba(255,255,255,0.55)` 1.5px solid with arrow
  - `co_occurrence`: `rgba(255,255,255,0.20)` 1px dashed "6 4"
  - `related`: `rgba(255,255,255,0.15)` 1px dotted "2 4"
- Updated `onNodeClick` prop type: added `nodeData?: Record<string, unknown>` third parameter
- Updated `handleNodeClick` callback: now passes `node.data as Record<string,unknown>` to parent
- Fixed Legend background: `rgba(253,251,247,.85)` → `rgba(20,18,15,0.90)` (dark surface)
- Fixed graph dot grid color: `rgba(31,30,27,.06)` → `rgba(255,255,255,0.06)` (visible on dark bg)

**frontend/app/courses/[id]/page.tsx**:
- Added `useRouter` from `next/navigation`
- Added `const router = useRouter()` in component
- Updated `handleNodeClick` signature to accept `nodeData?: Record<string, unknown>`
- Added quiz node routing: `router.push('/quiz/${quizId}')` when `nodeType === "quiz"`
- Added concept_id extraction from nodeData (with fallback to parseInt on nodeId)
- Added "Updating..." pulsing indicator: absolute positioned, shown when `hasPending`, with amber pulsing dot and dark glass background

---

## Pre-existing Correct State (no changes needed)

From 06-01 Wave 0 fixes already applied:
- `frontend/app/page.tsx` — already uses `c.title`, `c.active_struggle_count`, `c.concept_count` (CORRECT)
- `frontend/app/courses/[id]/page.tsx` — already uses `course?.title`, `n.type`, `n.data.has_struggle_signals` for raw graph stats (CORRECT)
- `frontend/components/graph/GraphCanvas.tsx` — `buildLayout()` already reads `n.type`, `n.data.*`, `e.type` (CORRECT from 06-01)

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] next.config.ts unsupported by Next.js 14**
- **Found during:** Task 1 verification (`npm run build`)
- **Issue:** Build failed with "Configuring Next.js via 'next.config.ts' is not supported. Please replace the file with 'next.config.js' or 'next.config.mjs'"
- **Fix:** Deleted `next.config.ts`, created `next.config.mjs` with equivalent config using ES module syntax
- **Files modified:** frontend/next.config.mjs (new), frontend/next.config.ts (deleted)
- **Commit:** a98965d (included in Task 1 commit)

**2. [Rule 2 - Missing Functionality] Graph dot grid color invisible on dark background**
- **Found during:** Task 2 — reviewing GraphCanvas for dark theme
- **Issue:** Background dot grid used `rgba(31,30,27,.06)` which is a near-black color (invisible on #1F1E1B dark background)
- **Fix:** Changed to `rgba(255,255,255,0.06)` — white with low opacity, visible on dark canvas
- **Files modified:** frontend/components/graph/GraphCanvas.tsx
- **Commit:** b541d25

---

## Known Stubs

None — all data flows from real backend endpoints. The dark theme is applied via CSS variables; no hardcoded color values block data rendering.

---

## Threat Flags

None — this plan only applies visual styling and wires existing data to UI. No new network endpoints or auth paths introduced.

---

## Self-Check: PASSED

- FOUND: frontend/app/globals.css (contains `--paper: #1F1E1B`)
- FOUND: frontend/next.config.mjs
- FOUND: frontend/components/graph/GraphCanvas.tsx (modified — contains `rgba(20,18,15,0.90)` Legend bg)
- FOUND: frontend/app/courses/[id]/page.tsx (modified — contains `quiz_id` and `useRouter`)
- FOUND: commit a98965d (Task 1)
- FOUND: commit b541d25 (Task 2)
- BUILD: `npm run build` exits 0
