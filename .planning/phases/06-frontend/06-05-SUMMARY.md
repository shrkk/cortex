---
phase: 06-frontend
plan: 05
subsystem: frontend-library
tags: [library, source-upload, status-badges, empty-states, course-selector]
status: partial — awaiting checkpoint human-verify
dependency_graph:
  requires:
    - 06-01 (TypeScript interfaces — Source, Course, SourceStatus, SourceType)
    - 06-02 (globals.css dark theme CSS variables)
    - 06-04 (FlashcardView, QuizView patterns for embedded mode)
  provides:
    - SourceLibrary: sources table + status badges + course selector + kind selector + upload FormData
    - library/page.tsx: GET /sources SWR + GET /courses SWR + handleUpload with course_id + kind
    - AppShell, TopBar, ui/primitives: layout infrastructure for all pages
  affects:
    - All 4 routes now have correct empty state copy matching UI-SPEC
tech_stack:
  added: []
  patterns:
    - FormData multipart upload with course_id (int) and kind (string) fields
    - Status badge using exact hex colors from UI-SPEC (#9A9388/#C18A3F/#6B8E5A/#B5604A)
    - useSWR for GET /sources and GET /courses in single page component
    - mutate("/sources") after successful upload
key_files:
  created:
    - frontend/components/SourceLibrary.tsx
    - frontend/app/library/page.tsx
    - frontend/components/AppShell.tsx
    - frontend/components/TopBar.tsx
    - frontend/components/ui/primitives.tsx
  modified:
    - frontend/app/page.tsx (empty state copy fix)
    - frontend/app/courses/[id]/page.tsx (two-state graph empty — building vs. nothing)
decisions:
  - "SourceLibrary uses a native <table> for sources list matching UI-SPEC column spec (Title/Type/Course/Status/Uploaded)"
  - "Status badge colors hardcoded as exact hex per UI-SPEC — not derived from CSS variables since they are brand-specific values"
  - "Library page does NOT poll — single fetch on page load, manual refresh via mutate after upload"
  - "AppShell/TopBar/primitives added to worktree as they are needed by library page and existing pages"
  - "GraphEmpty now accepts isProcessing prop to show two distinct empty states per UI-SPEC"
metrics:
  duration: ~10 minutes
  completed: "2026-04-26T05:00:00Z"
  tasks_completed: 1
  files_created: 5
  files_modified: 2
---

# Phase 6 Plan 5: Library Page + Empty States Summary

**One-liner:** Wired library page to GET /sources and GET /courses via SWR; added course_id + kind fields to FormData uploader; applied exact UI-SPEC status badge colors and empty state copy across all 4 routes.

**Status: PARTIAL — Task 1 complete, awaiting human smoke test checkpoint.**

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Fix SourceLibrary.tsx upload form + status badges + empty states | a217b60 | frontend/components/SourceLibrary.tsx, frontend/app/library/page.tsx, frontend/app/page.tsx, frontend/app/courses/[id]/page.tsx, + infrastructure files |

---

## What Was Built

### Task 1: SourceLibrary + Library Page + Empty State Fixes

**frontend/components/SourceLibrary.tsx** (created):

- **Props interface updated**: accepts `courses: Course[]` for dropdown population and `onUpload(file, courseId, kind)` (was just `file`)
- **Course selector**: `<select>` populated from `courses` prop, defaults to `courses[0].id`
- **Kind selector**: `<select>` with options pdf/image/text; defaults to "pdf"
- **Status badge colors** — exact hex per UI-SPEC:
  - `pending` → `#9A9388` (idle-muted)
  - `processing` → `#C18A3F` (amber)
  - `done` → `#6B8E5A` (moss)
  - `error` → `#B5604A` (destructive)
- **Source type badge**: font-mono, uppercase, surface background, border per UI-SPEC
- **Source table**: Title/Type/Course/Status/Uploaded columns; relative time for Uploaded
- **Empty state** (when `sources.length === 0`):
  - Heading: "No sources yet" (exact UI-SPEC copy)
  - Body: "Prefer dropping into the notch. Or use the uploader below as a fallback."
  - Uploader still rendered below empty state
- **Uploader card label**: "Fallback uploader — prefer dropping into the notch" (exact UI-SPEC copy)
- **Upload flow**: click triggers file input with `accept=".pdf,.png,.jpg,.jpeg,.txt,.md"`, async error handling, uploading state

**frontend/app/library/page.tsx** (created):

- `useSWR<Source[]>("/sources", ...)` — GET /sources for source list
- `useSWR<Course[]>("/courses", ...)` — GET /courses for course selector dropdown
- `handleUpload(file, courseId, kind)` appends `file`, `course_id`, `kind` to FormData and POSTs to `/ingest`
- `mutate("/sources")` called after successful upload to invalidate cache
- No Content-Type header set (browser sets multipart boundary automatically)

**frontend/app/page.tsx** (modified):

- Empty state heading: "No courses yet" (was "Nothing in your graph yet.")
- Empty state body: "Drop something into the notch to create your first course automatically." (exact UI-SPEC copy)

**frontend/app/courses/[id]/page.tsx** (modified):

- `GraphEmpty` component now accepts `isProcessing?: boolean` prop
- When `isProcessing=true`: "Building your graph…" / "Cortex is extracting concepts from your sources. Check back in a moment."
- When `isProcessing=false`: "Nothing here yet" / "Drop a PDF, URL, or image into the notch to start building this course."
- Call site passes `isProcessing={hasPending}` (wired to polling state)

**Infrastructure files added to worktree** (needed by library page):
- `frontend/components/AppShell.tsx` — top-level shell with TopBar + Sidebar
- `frontend/components/TopBar.tsx` — header bar with search/command trigger
- `frontend/components/ui/primitives.tsx` — Icon, Button, Pill, Card, Eyebrow, Kbd

---

## Verification

```
npm run build  → exit 0 (all 5 routes compiled: /, /library, /courses/[id], /quiz/[id], /_not-found)

grep "course_id" components/SourceLibrary.tsx  → 2 matches
grep "kind" components/SourceLibrary.tsx        → 4 matches
grep "9A9388" components/SourceLibrary.tsx      → 1 match (pending badge)
grep "6B8E5A" components/SourceLibrary.tsx      → 1 match (done badge)
grep "No sources yet" components/SourceLibrary.tsx   → 1 match
grep "Fallback uploader" components/SourceLibrary.tsx → 1 match
grep "courses" app/library/page.tsx             → 4 matches
grep "course_id" app/library/page.tsx           → 1 match
```

---

## Deviations from Plan

### Auto-fixed Issues

**[Rule 2 - Missing Infrastructure] Added AppShell, TopBar, ui/primitives to worktree**

- **Found during**: Task 1 — creating library/page.tsx which imports AppShell
- **Issue**: Worktree only contained files explicitly committed in waves 1-4. AppShell/TopBar/primitives existed in main repo as untracked files (not committed), so they were absent from the worktree.
- **Fix**: Copied infrastructure files into worktree so TypeScript compilation and build succeed.
- **Files modified**: `frontend/components/AppShell.tsx`, `frontend/components/TopBar.tsx`, `frontend/components/ui/primitives.tsx`
- **Commit**: a217b60

### Notes

- `SourceLibrary` uses native `<table>` instead of Pill-based badges for status (matches plan's explicit STATUS_BADGE_STYLE approach with hex colors rather than CSS variable tones from Pill component)
- The `onUpload` prop is typed as `Promise<void>` to allow error handling in the uploader component; the library page wrapper calls it async

---

## Known Stubs

None — all data is wired to real backend endpoints:
- `GET /sources` returns real source list (endpoint added in wave 1, plan 01)
- `GET /courses` returns real course list (existing endpoint)
- `POST /ingest` receives real FormData with file + course_id + kind

---

## Threat Flags

None — no new network surfaces beyond what the plan's threat model covers (T-06-05-01 through T-06-05-04 are all accounted for in the implementation):
- Frontend `accept` attribute is UX-only; backend validates actual content (T-06-05-01: accepted)
- `kind` field validated as Literal by Pydantic on backend (T-06-05-02: accepted)
- Source titles are user-supplied, no PII (T-06-05-03: accepted)
- No polling on library page (T-06-05-04: accepted)

---

## Checkpoint Reached

Task 2 is a `checkpoint:human-verify` — human smoke test of all 4 routes required before plan can be declared complete.

See checkpoint details in the plan executor output.

---

## Self-Check: PASSED

- FOUND: frontend/components/SourceLibrary.tsx — contains "course_id", "kind", "#9A9388", "#6B8E5A", "No sources yet", "Fallback uploader"
- FOUND: frontend/app/library/page.tsx — contains GET /sources SWR, GET /courses SWR, "course_id" in FormData
- FOUND: frontend/app/page.tsx — contains "No courses yet", "Drop something into the notch"
- FOUND: frontend/app/courses/[id]/page.tsx — contains "Building your graph", "Nothing here yet"
- FOUND: commit a217b60
- BUILD: npm run build exits 0, /library route present in output
