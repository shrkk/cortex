# Phase 6: Frontend - Context

**Gathered:** 2026-04-25
**Status:** Ready for planning (pending UI-SPEC.md from /gsd-ui-phase 6)

<domain>
## Phase Boundary

Build the Cortex Web app from scratch as a Next.js 14 App Router project at `/frontend/`. Delivers: course dashboard, React Flow knowledge graph with detail panel + flashcard flip mode, quiz walkthrough, library page, and all empty states. Connects to the FastAPI backend at `http://localhost:8000`. No auth — user_id=1 hardcoded.

**UI-SPEC.md note:** The user plans to run `/gsd-ui-phase 6` with a Claude design template before planning. UI-SPEC.md will define colors, typography, spacing, and component specs. The planner MUST read it alongside this CONTEXT.md.

</domain>

<decisions>
## Implementation Decisions

### Graph Node Style
- **D-01:** Concept nodes are minimal **circles** with a title label below. No card previews or summary text inside the node.
- **D-02:** Node sizing is at Claude's discretion — scale diameter linearly by `source_count` (min 32px at 1 source, max 48px at 5+ sources) to convey coverage depth without cluttering the dagre layout.
- **D-03:** Course root node is a **60px circle** with the course name label rendered inside it. Visually larger than any concept node to anchor the hierarchy.
- **D-04:** Struggle signal indicator is a **pulsing red ring** (CSS animation) around the node circle — no filled color change, ring only. Concepts without signals get a neutral fill.
- **D-05:** Flashcard nodes and quiz node are also rendered as circles but visually distinct (different fill/border style at Claude's discretion — they must be distinguishable from concept nodes at a glance).

### Detail Panel Behavior
- **D-06:** Clicking a concept node opens a **slide-in right panel** (~380px wide) using the shadcn `Sheet` component. Panel overlays the graph; graph remains interactive behind it. URL stays at `/courses/[id]` — no route change on panel open.
- **D-07:** "View Flashcards" inside the detail panel **replaces the panel content in-place** — the panel transitions from concept detail view to flashcard flip-card view. A back button returns to the concept detail within the same panel. No navigation away from the graph page.
- **D-08:** The quiz node on the graph navigates to `/quiz/[id]` (separate page) — quiz is a full linear walkthrough, not suitable as a panel.

### Data Fetching
- **D-09:** Use **SWR** for all data fetching (`swr` package). Dead-simple with Next.js App Router; no additional provider setup needed.
- **D-10:** Graph polling uses `refreshInterval: hasPendingSources ? 5000 : 0` — polling is active while any source has `status === "pending"` or `status === "processing"`, stops automatically when all are `done` or `error`. `hasPendingSources` is derived from the sources response within the same SWR hook or a companion hook.
- **D-11:** Mutations (POST /quiz, POST /ingest from library page) use SWR's `mutate` for cache invalidation after success.

### Routing Structure
- **D-12:** Route structure at Claude's discretion, but must include: `/` (dashboard), `/courses/[id]` (graph page), `/quiz/[id]` (quiz walkthrough), `/library` (sources list). No catch-all routes — all four are discrete pages.

### Claude's Discretion
- Exact visual theme (colors, typography, dark/light mode) — deferred to UI-SPEC.md from `/gsd-ui-phase 6`
- Node size scaling formula (see D-02 guidance above)
- Edge visual treatment (thickness, dash patterns) for the four edge types — must follow requirements: contains=thick neutral, prerequisite=solid arrow, co_occurrence=dashed, related=dotted
- shadcn component selection for each surface (Card, Badge, Sheet, etc.)
- Exact flipcard animation (CSS 3D transform vs. framer-motion)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §Frontend (UI-01–UI-11) — all 11 frontend requirements
- `.planning/ROADMAP.md` §Phase 6 — goal, success criteria, stack notes (critical package name constraints)

### Stack Constraints (CRITICAL — wrong packages break the build)
- `.planning/ROADMAP.md` §Phase 6 "Stack notes" — `@xyflow/react` NOT `reactflow`; `@dagrejs/dagre` NOT `dagre`; `nodeTypes` outside component body; `ConceptNode` wrapped in `React.memo`
- `.planning/PROJECT.md` §Constraints — full tech stack locked: Next.js 14 App Router + TypeScript + Tailwind + shadcn/ui + React Flow

### Design Contract (to be generated)
- `.planning/phases/06-frontend/06-UI-SPEC.md` — visual design contract from `/gsd-ui-phase 6` — MUST be generated before planning begins; defines colors, spacing, typography, component specs

### Notch Design Tokens (reference for brand alignment)
- `notch/NotchDrop/NotchDrop/Cortex/CortexStatusView.swift` — Cortex color palette: bg `#1F1E1B`, text `#FAF7F2`, accent terracotta `#C96442`, amber `#C18A3F`, moss `#6B8E5A`

### Backend API (what frontend calls)
- `backend/app/api/courses.py` — GET /courses, POST /courses, GET /courses/{id}/graph, GET /courses/match
- `backend/app/api/` — ingest, quiz endpoints; planner should grep for full route list
- `backend/app/schemas/` — Pydantic response shapes (what JSON the frontend receives)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- No existing frontend code — this is a fresh Next.js project to be scaffolded at `/frontend/`
- shadcn/ui will be initialized as part of scaffolding; component list to be determined by planner

### Established Patterns (from backend)
- All API responses use snake_case JSON — frontend must handle snake_case field names or use a camelCase transform
- `user_id=1` hardcoded on all backend routes — frontend never needs to send auth headers

### Integration Points
- Backend runs at `http://localhost:8000` — store as `NEXT_PUBLIC_API_URL` in `.env.local`
- Graph data endpoint: `GET /courses/{id}/graph` returns `{nodes: [...], edges: [...]}`
- Node types in graph response: `"course"`, `"concept"`, `"flashcard"`, `"quiz"`
- Edge types in graph response: `"contains"`, `"prerequisite"`, `"co_occurrence"`, `"related"`
- Concept detail: `GET /concepts/{id}` returns summary, key_points, gotchas, examples, student_questions, source_citations, flashcard_count, struggle_signals

</code_context>

<specifics>
## Specific Ideas

- The user plans to supply a Claude design template via `/gsd-ui-phase 6` — this will be the authoritative visual spec. Do not invent a color scheme; wait for UI-SPEC.md.
- Struggle pulsing ring: CSS `@keyframes pulse` with `box-shadow` or `outline` — not a React Flow built-in; must be custom CSS on the node wrapper.
- `refreshInterval: hasPendingSources ? 5000 : 0` is the exact SWR pattern for auto-stop polling (D-10).
- `import * as dagre from '@dagrejs/dagre'` — this exact import form is required per ROADMAP stack notes.

</specifics>

<deferred>
## Deferred Ideas

- Visual theme / color scheme discussion — intentionally deferred to `/gsd-ui-phase 6` UI-SPEC.md rather than decided here
- Mobile responsive layout — explicitly out of scope (PROJECT.md Out of Scope)
- WebSocket/SSE real-time updates — out of scope; 5s polling is the spec

</deferred>

---

*Phase: 06-frontend*
*Context gathered: 2026-04-25*
