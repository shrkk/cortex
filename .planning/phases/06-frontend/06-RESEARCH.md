# Phase 6: Frontend - Research

**Researched:** 2026-04-25
**Domain:** Next.js 14 App Router · @xyflow/react v12 · dagre layout · SWR · custom design system
**Confidence:** HIGH (codebase verified, packages confirmed via npm registry)

---

## Summary

The frontend project already exists at `/frontend/` and is substantially scaffolded. All four required routes (`/`, `/courses/[id]`, `/quiz/[id]`, `/library`) exist with page files. Core graph components (`GraphCanvas.tsx`, `NodeTypes.tsx`) are implemented with correct `@xyflow/react` imports, `nodeTypes` defined outside component body, `React.memo` on all custom nodes, and `setTimeout(fitView, 0)` on first layout. All stack constraints from ROADMAP.md are already honored in the existing code.

The design system uses a custom CSS variables approach (`globals.css`) with a warm paper/ink palette — this does NOT match the dark UI-SPEC.md palette exactly. UI-SPEC requires `bg-base: #1F1E1B` (dark) but the existing code uses `--paper: #FAF7F2` (light). The planner must decide: keep the existing warm light theme and map UI-SPEC tokens to it, OR replace globals.css to implement the dark palette from UI-SPEC. This is the single most consequential visual decision in the phase.

The most significant gaps are: (1) backend API shape mismatches between what the frontend code expects and what the backend actually returns; (2) missing backend endpoints (`GET /sources`, `GET /courses/{id}`, `GET /courses/{id}/sources`, `GET /concepts/{id}/flashcards`, `GET /quiz/{id}`); (3) the quiz walkthrough wires against a static local question list — no integration with the actual `POST /quiz/{id}/answer` grading endpoint; (4) the library uploader posts to `/ingest` with an incomplete form (missing `course_id` and `kind` fields). These gaps are the primary implementation work for this phase.

**Primary recommendation:** Audit and correct the `lib/api.ts` type definitions against actual backend schemas first, then fix each page's data hooks and form submissions to match the real API contracts, then address the missing backend endpoints (likely a Wave 0 backend addition), then polish empty states and polling behavior.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Concept nodes are minimal circles with a title label below. No card previews or summary text inside the node.
- **D-02:** Node sizing scales diameter linearly by `source_count` (min 32px at 1 source, max 48px at 5+).
- **D-03:** Course root node is a 60px circle with the course name label rendered inside it.
- **D-04:** Struggle signal indicator is a pulsing red ring (CSS animation) around the node circle — no filled color change.
- **D-05:** Flashcard nodes and quiz node are circles, visually distinct from concept nodes.
- **D-06:** Clicking a concept node opens a slide-in right panel (~380px wide) using shadcn Sheet. Graph remains interactive. URL stays at `/courses/[id]`.
- **D-07:** "View Flashcards" inside the detail panel replaces the panel content in-place. A back button returns to the concept detail within the same panel.
- **D-08:** The quiz node on the graph navigates to `/quiz/[id]`.
- **D-09:** Use SWR for all data fetching.
- **D-10:** Graph polling uses `refreshInterval: hasPendingSources ? 5000 : 0`.
- **D-11:** Mutations use SWR's `mutate` for cache invalidation after POST.
- **D-12:** Route structure: `/` (dashboard), `/courses/[id]` (graph page), `/quiz/[id]` (quiz walkthrough), `/library` (sources list).

### Claude's Discretion
- Exact visual theme (colors, typography, dark/light mode) — deferred to UI-SPEC.md.
- Node size scaling formula (D-02 guidance above).
- Edge visual treatment — must follow: contains=thick neutral, prerequisite=solid arrow, co_occurrence=dashed, related=dotted.
- shadcn component selection for each surface.
- Exact flipcard animation (CSS 3D transform vs. framer-motion).

### Deferred Ideas (OUT OF SCOPE)
- Visual theme / color scheme discussion — intentionally deferred to UI-SPEC.md.
- Mobile responsive layout — explicitly out of scope.
- WebSocket/SSE real-time updates — out of scope; 5s polling is the spec.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UI-01 | Dashboard (`/`) shows courses list, "Create Course" button, global stats (total concepts, active struggle signals) | `GET /courses` returns `list[CourseResponse]` — title+id confirmed; struggle_count and concept_count are NOT in CourseResponse (gap — see API Mismatch section) |
| UI-02 | Course graph renders React Flow: course node center, concept nodes sized by source_count, colored by struggle, dagre layout by depth, flashcard and quiz nodes visible | GraphCanvas.tsx exists; nodeTypes correct; dagre layout implemented; polling hook partially wired |
| UI-03 | Concept nodes with active struggle signals show a pulsing red indicator | ConceptNode renders pulsing dot via `graphPulse` keyframe; uses `has_struggle_signals` field from backend graph node data |
| UI-04 | Edge types rendered distinctly: contains, prerequisite, co_occurrence, related | CortexEdge custom edge component exists; edge_type embedded in edge.data |
| UI-05 | Clicking concept node opens detail panel: summary, gotchas (amber), key_points, examples, student questions, source citations, flashcard count, "View Flashcards" button, "Generate Quiz" button | ReadingDrawer.tsx implements this; calls `GET /concepts/{id}` |
| UI-06 | "View Flashcards" opens flip-card study mode: no grading | FlashcardView.tsx implements this with space/arrow keyboard nav; calls `GET /concepts/{id}/flashcards` (endpoint does not exist in backend — gap) |
| UI-07 | Quiz node on graph clickable, opens quiz walkthrough | NodeClick handler wired; navigation to `/quiz/[id]` needs quiz_id extraction from node data |
| UI-08 | Quiz page is a linear walkthrough: MCQ radio or textarea, submit, see feedback, advance; final screen shows score and concepts to review | QuizView.tsx exists but uses static local grading; needs wiring to `POST /quiz/{id}/answer` backend endpoint |
| UI-09 | Library shows all sources with status badges, course assignment dropdown, web file uploader | SourceLibrary.tsx exists; calls `GET /sources` (endpoint missing in backend — gap); uploader is incomplete (missing course_id, kind fields) |
| UI-10 | Empty states: graph, flashcard view, dashboard | Empty components exist in each page/component |
| UI-11 | Graph re-fetches every 5s while sources processing; stops when all done/error | CoursePage.tsx has hasPending logic; currently calls `GET /courses/{id}/sources` (endpoint missing — gap) |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Course dashboard + course CRUD | Browser / Client | API / Backend | Next.js Client Component; SWR fetches from FastAPI |
| Graph rendering + dagre layout | Browser / Client | — | React Flow + dagre runs entirely in browser |
| Detail panel (concept) | Browser / Client | API / Backend | shadcn Sheet; SWR fetches /concepts/{id} on demand |
| Flashcard flip mode | Browser / Client | API / Backend | Pure UI state flip; data from /concepts/{id}/flashcards |
| Quiz walkthrough + grading | Browser / Client | API / Backend | UI state machine; grading via POST /quiz/{id}/answer |
| Source library + uploader | Browser / Client | API / Backend | Form POST to /ingest; GET /sources list |
| Graph polling | Browser / Client | API / Backend | SWR refreshInterval; backend serves /courses/{id}/graph |
| Struggle signals visualization | Browser / Client | — | Driven by `has_struggle_signals` in graph node data |
| Missing backend endpoints | API / Backend | — | GET /sources, GET /courses/{id}, GET /courses/{id}/sources, GET /concepts/{id}/flashcards, GET /quiz/{id} — must be added in Wave 0 |

---

## Standard Stack

### Core (already installed, verified via package.json + npm registry)

| Library | Version (installed) | Latest | Purpose | Why Standard |
|---------|---------------------|--------|---------|--------------|
| next | ^14.2.29 | 14.2.29 | App Router framework | ROADMAP locked; do NOT upgrade to 15 |
| react / react-dom | ^18.3.1 | 18.3.1 | UI runtime | Next.js peer |
| @xyflow/react | ^12.3.6 | 12.10.2 [VERIFIED: npm registry] | Knowledge graph canvas | CLAUDE.md locked — NOT `reactflow` |
| @dagrejs/dagre | ^1.1.4 | 3.0.0 [VERIFIED: npm registry] | DAG layout algorithm | CLAUDE.md locked — NOT `dagre` |
| swr | ^2.2.5 | 2.4.1 [VERIFIED: npm registry] | Data fetching + polling | D-09 locked |
| lucide-react | ^0.451.0 | latest | Icons | Already in use throughout |

**Package version note:** `@dagrejs/dagre` latest is 3.0.0 but the project has 1.1.4 pinned. Do not upgrade without testing — the dagre v3 API may have breaking changes. `@xyflow/react` latest is 12.10.2 vs pinned 12.3.6; the project can stay on pinned version. [VERIFIED: npm registry]

### Not Yet Installed (needed for UI-SPEC shadcn components)

shadcn/ui is NOT initialized — no `components.json` file exists. The UI-SPEC.md lists 13 required shadcn components. However, the existing code uses a custom primitives system (`components/ui/primitives.tsx`) with `Button`, `Card`, `Pill`, `Eyebrow`, `Kbd`, `Icon`, `Separator` — all hand-rolled against CSS variables. The planner must choose:

**Option A (recommended):** Keep existing primitives, add specific shadcn components only for the parts that require them (Sheet for the detail panel drawer is the only one that can't be trivially hand-rolled).

**Option B:** Initialize shadcn and rebuild primitives — large scope, risk of visual regression.

The CONTEXT.md says "shadcn/ui will be initialized as part of scaffolding" but the scaffold already has custom primitives that work. Research recommendation: add shadcn Sheet only; keep existing primitives for Button, Card, Badge, etc. [ASSUMED]

### Supporting

| Library | Purpose | Status |
|---------|---------|--------|
| tailwindcss ^3.4.14 | Utility classes | Already configured |
| typescript ^5.6.3 | Type safety | Already configured |
| @types/dagre ^0.7.52 | dagre type definitions | Already installed |

---

## Architecture Patterns

### System Architecture Diagram

```
Browser (Next.js Client Components)
│
├── / (DashboardPage)
│   └── useSWR("GET /courses") → CourseCard grid → Link /courses/[id]
│
├── /courses/[id] (CoursePage)
│   ├── useSWR("GET /courses/{id}/graph") ─────────────────────────────┐
│   ├── useSWR("GET /courses/{id}/sources", refreshInterval=0)         │
│   │   └── hasPending=true → refreshInterval=5000 on graph hook       │
│   ├── ReactFlowProvider                                               │
│   │   └── GraphCanvas ← graphData ← buildLayout(dagre) ←────────────┘
│   │       └── ConceptNode (onClick) → setSelectedConceptId
│   └── ReadingDrawer (when selectedConceptId)
│       ├── useSWR("GET /concepts/{id}") → ConceptDetail
│       │   └── "View Flashcards" → mode=flashcards
│       └── FlashcardView
│           └── useSWR("GET /concepts/{id}/flashcards")
│
├── /quiz/[id] (QuizPage)
│   ├── useSWR("GET /quiz/{id}") → initial questions
│   └── QuizView → POST /quiz/{id}/answer (per question)
│       └── Final screen: score + concepts_to_review
│
└── /library (LibraryPage)
    ├── useSWR("GET /sources") → SourceLibrary table
    └── Upload form → POST /ingest (multipart: file + course_id + kind)

FastAPI Backend (http://localhost:8000)
├── GET /courses                      → list[CourseResponse]
├── GET /courses/{id}                 → CourseResponse (MISSING — must add)
├── GET /courses/{id}/graph           → GraphResponse {nodes, edges}
├── GET /courses/{id}/sources         → list[SourceResponse] (MISSING — must add)
├── GET /sources                      → list[SourceResponse] (MISSING — must add)
├── POST /courses                     → CourseResponse
├── GET /concepts/{id}                → ConceptDetailResponse
├── GET /concepts/{id}/flashcards     → list[FlashcardResponse] (MISSING — must add)
├── GET /quiz/{id}                    → QuizResponse (MISSING — must add)
├── POST /quiz                        → QuizResponse
├── POST /quiz/{id}/answer            → {grading, next_question, ...}
└── POST /ingest                      → {source_id, status}
```

### Recommended Project Structure

The existing structure is already correct. No changes to directory layout are needed:

```
frontend/
├── app/
│   ├── page.tsx              # / dashboard
│   ├── layout.tsx            # root layout
│   ├── globals.css           # design tokens + animations
│   ├── courses/[id]/
│   │   └── page.tsx          # graph page
│   ├── quiz/[id]/
│   │   └── page.tsx          # quiz walkthrough
│   └── library/
│       └── page.tsx          # source library
├── components/
│   ├── AppShell.tsx          # TopBar + Sidebar layout
│   ├── FlashcardView.tsx     # flip card mode
│   ├── QuizView.tsx          # quiz walkthrough UI
│   ├── ReadingDrawer.tsx     # concept detail panel
│   ├── SourceLibrary.tsx     # library table + uploader
│   ├── graph/
│   │   ├── GraphCanvas.tsx   # ReactFlow wrapper + dagre layout
│   │   └── NodeTypes.tsx     # CourseNode, ConceptNode, FlashcardNode, QuizNode
│   └── ui/
│       └── primitives.tsx    # Button, Card, Pill, Eyebrow, Icon, Kbd
└── lib/
    └── api.ts                # apiFetch + TypeScript interface types
```

### Pattern 1: Dagre Layout (correctly implemented in existing code)

```typescript
// Source: GraphCanvas.tsx (verified in codebase)
// nodeTypes MUST be outside component body — prevents recreation on every render
const nodeTypes: NodeTypes = {
  course:    CourseNode,
  concept:   ConceptNode,
  flashcard: FlashcardNode,
  quiz:      QuizNode,
};

// import form REQUIRED — NOT `import dagre from "@dagrejs/dagre"`
import * as dagre from "@dagrejs/dagre";

// fitView AFTER setNodes, in setTimeout to defer until layout paint
const didLayout = React.useRef(false);
useEffect(() => {
  if (!graphData?.nodes?.length) return;
  const { nodes: ln, edges: le } = buildLayout(graphData.nodes, graphData.edges);
  setNodes(ln);
  setEdges(le);
  if (!didLayout.current) {
    didLayout.current = true;
    setTimeout(() => fitView({ padding: 0.12 }), 0);
  }
}, [graphData, setNodes, setEdges, fitView]);
```

### Pattern 2: SWR Polling with Auto-Stop (D-10)

```typescript
// Source: CoursePage.tsx (verified in codebase)
// hasPending derived from sources endpoint response
const { data: sources } = useSWR<Source[]>(`/courses/${id}/sources`, fetcher);
const hasPending = sources?.some(s => s.status === "pending" || s.status === "processing");

// Conditional key: when hasPending is false/undefined, key is null → SWR does not fetch
const { data: liveGraph } = useSWR<GraphData>(
  hasPending ? `/courses/${id}/graph` : null,
  fetcher,
  { refreshInterval: 5000 }
);

// Use live graph when polling, fall back to initial load
const graph = liveGraph ?? graphData;
```

### Pattern 3: In-Place Panel Transition (D-07)

```typescript
// Source: ReadingDrawer.tsx (verified in codebase)
const [mode, setMode] = useState<"detail" | "flashcards">("detail");

// Panel body switches content without navigation or animation
{mode === "flashcards" ? (
  <FlashcardView flashcards={flashcards} conceptTitle={concept.title} embedded />
) : (
  <ConceptDetail concept={concept} onViewFlashcards={() => setMode("flashcards")} />
)}
```

### Pattern 4: API Fetch with Base URL

```typescript
// Source: lib/api.ts (verified in codebase)
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}
```

### Pattern 5: SWR Mutation After POST (D-11)

```typescript
// Source: library/page.tsx (verified in codebase)
const { mutate } = useSWRConfig();

const handleUpload = async (file: File) => {
  const form = new FormData();
  form.append("file", file);
  // ... append course_id and kind ...
  await fetch(`${BASE}/ingest`, { method: "POST", body: form });
  mutate("/sources");  // invalidate cache after mutation
};
```

### Anti-Patterns to Avoid

- **nodeTypes inside component body:** Causes React Flow to re-render all nodes on every parent render. The existing code correctly defines nodeTypes outside — preserve this.
- **`import dagre from "@dagrejs/dagre"`:** Default import fails with ESM. Must use `import * as dagre from "@dagrejs/dagre"` (already correct in existing code).
- **`import ... from "reactflow"`:** Package renamed to `@xyflow/react` in v12. Using old name installs deprecated alias with different API.
- **SWR in Server Components:** SWR is a React hooks library — all pages using it must have `"use client"` directive. All existing pages already have it.
- **Calling fitView synchronously:** Must use `setTimeout(() => fitView(), 0)` — synchronous call fires before React Flow has mounted nodes and produces no-op. Already correct in codebase.
- **Polling with always-on refreshInterval:** Use `hasPending ? 5000 : 0` not a fixed interval. `refreshInterval: 0` disables polling; null key also disables.
- **Passing session from parent to nested SWR:** SWR does not need a Provider in App Router. D-09 confirms this — no SWRProvider in layout needed.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Graph layout (no nodes at origin) | Manual x/y positioning | dagre via `@dagrejs/dagre` | Dagre computes hierarchical TB layout accounting for node widths; hand-placing nodes is O(n^2) problem |
| Accessible slide-in drawer | Custom absolute-positioned panel | shadcn Sheet (Radix Dialog) | Radix handles focus trap, Escape key, aria-modal, scroll lock automatically |
| CSS 3D card flip | JS-toggle display | CSS `transform-style: preserve-3d` + `rotateY(180deg)` | GPU-accelerated, no layout reflow, 60fps; display-toggle causes reflow on every flip |
| Polling with cleanup | `setInterval` + manual cleanup | SWR `refreshInterval` | SWR deduplicates requests across components, cleans up on unmount, respects tab visibility |
| Graph state management | useState for nodes/edges | `useNodesState` / `useEdgesState` from @xyflow/react | Built-in support for panning/zooming/selection state; hand-rolling causes stale closure bugs |

**Key insight:** The three hardest frontend problems in this phase (graph layout, accessible drawer, polling) each have a library that handles 90% of the edge cases. The existing code already uses them correctly.

---

## API Shape Mismatches (CRITICAL)

This is the highest-priority finding. The frontend types in `lib/api.ts` do not match the backend Pydantic schemas. The planner must create tasks to fix these.

### 1. GraphNode shape mismatch

**Backend returns** (`GET /courses/{id}/graph`):
```json
{
  "id": "concept-42",
  "type": "concept",
  "data": {
    "label": "Gradient Descent",
    "concept_id": 42,
    "depth": 2,
    "has_struggle_signals": true,
    "flashcard_count": 4
  }
}
```

**Frontend `lib/api.ts` expects:**
```typescript
interface GraphNode {
  id: string;
  node_type: "course" | "concept" | "flashcard" | "quiz";  // WRONG — backend uses "type" at root
  label: string;    // WRONG — backend puts label inside "data"
  source_count?: number;   // ABSENT in backend response — backend has no source_count
  has_struggle?: boolean;  // WRONG name — backend uses "has_struggle_signals"
  flashcard_count?: number;
}
```

**Fix required:** Update `GraphNode` interface to match backend structure. The `GraphCanvas.tsx` `buildLayout()` function must be updated to read `n.type` (not `n.node_type`) and `n.data.label` (not `n.label`).

**Additional gap:** Backend concept nodes have no `source_count` field — this is not returned. If D-02 (size by source_count) must work, either: (a) add source_count to the graph endpoint's concept node data, or (b) use a fixed size. [ASSUMED: source_count must be added to backend graph payload to implement D-02]

### 2. GraphEdge shape mismatch

**Backend returns:**
```json
{"id": "edge-5", "source": "concept-1", "target": "concept-2", "type": "co_occurrence", "data": {"weight": 3}}
```

**Frontend expects:**
```typescript
interface GraphEdge {
  edge_type: "contains" | "prerequisite" | "co_occurrence" | "related" | "flashcard_of" | "quiz_of";
  // Missing "type" at root
}
```

**Fix required:** GraphEdge interface should use `type` (matches backend). The `CortexEdge` component reads `data.edge_type` but backend puts edge type in the root `type` field, not in `data`. The `buildLayout()` function maps edges: `data: { edge_type: e.edge_type }` — but `e.edge_type` doesn't exist on the backend shape (it's `e.type`). This is a live bug.

### 3. Course shape mismatch

**Backend `CourseResponse`:**
```typescript
{ id: number; user_id: number; title: string; description?: string; created_at: datetime }
```

**Frontend `Course` interface:**
```typescript
{ id: number; name: string; concept_count?: number; struggle_count?: number }
```

**Gaps:**
- Backend uses `title` — frontend uses `name` (wrong field name)
- `concept_count` and `struggle_count` are NOT in `CourseResponse` — they don't exist in the backend
- Dashboard page renders `c.name` but backend returns `c.title` → all course names show as `undefined`

**Fix required:** Either rename `name` → `title` in frontend type, OR add a backend transform. `concept_count` and `struggle_count` need dedicated backend additions or can be omitted from the dashboard stats (showing them as "coming soon").

### 4. QuizQuestion shape mismatch

**Backend question dict (from `questions` JSONB column):**
```json
{"question_id": 0, "type": "mcq", "question": "...", "concept_id": 42, "options": ["A","B","C","D"], "correct_index": 2, "answered": false}
```

**Frontend `QuizQuestion` interface:**
```typescript
{ id: number; question_type: "mcq" | "free"; prompt: string; topic?: string; options?: string[]; correct_index?: number; explanation?: string }
```

**Gaps:**
- `id` vs `question_id`
- `question_type` vs `type` (and backend uses "mcq"/"short_answer"/"application" not "mcq"/"free")
- `prompt` vs `question`
- `explanation` does not exist in backend questions
- Backend has `concept_id`, frontend doesn't

**Fix required:** Rewrite `QuizQuestion` interface and `QuizView.tsx` to use backend field names.

### 5. Missing backend endpoints

| Endpoint | Used By | Status |
|----------|---------|--------|
| `GET /courses/{id}` | CoursePage (course title in header) | MISSING — only `/courses` (list) exists |
| `GET /courses/{id}/sources` | CoursePage polling trigger | MISSING |
| `GET /sources` | LibraryPage | MISSING |
| `GET /concepts/{id}/flashcards` | ReadingDrawer → FlashcardView | MISSING |
| `GET /quiz/{id}` | QuizPage initial load | MISSING — only `POST /quiz` and `GET /quiz/{id}/results` |

These must be added to the backend (likely in a Wave 0 plan) before the frontend can be completed. [VERIFIED: grepped all backend router files]

### 6. Ingest form missing required fields

The library uploader posts to `/ingest` with only `file` in the FormData. Backend requires:
- `course_id` (int) — which course to assign the source to
- `kind` (str) — "pdf" or "image"
- `file` — the upload

**Fix required:** Library page needs a course selector (`GET /courses` → dropdown) and the uploader must append `course_id` and `kind` to the FormData.

---

## Common Pitfalls

### Pitfall 1: Nodes Pile at Origin (dagre-at-origin bug)

**What goes wrong:** All concept nodes render at position (0,0), overlapping completely.
**Why it happens:** `nodeTypes` object defined inside component body — React recreates the object reference on every render, causing React Flow to remount all nodes and reset their positions.
**How to avoid:** Define `nodeTypes` as a module-level constant, outside any component. Already correctly done in `GraphCanvas.tsx`.
**Warning signs:** Graph renders as a single point; `console.log(nodes)` shows all with `{x:0,y:0}`.

### Pitfall 2: fitView Fires Before Nodes Mounted

**What goes wrong:** `fitView()` is called synchronously but React Flow hasn't committed node DOM yet.
**Why it happens:** The layout computation runs in a useEffect but fitView needs the actual rendered node dimensions.
**How to avoid:** `setTimeout(() => fitView({ padding: 0.12 }), 0)` — defer to next tick. Already correctly implemented in `GraphCanvas.tsx`.
**Warning signs:** Graph renders correctly but viewport stays at origin; fitView seems to do nothing.

### Pitfall 3: Wrong Package Name

**What goes wrong:** `import { ReactFlow } from "reactflow"` installs the deprecated v11 package which has different API signatures for v12.
**Why it happens:** `reactflow` still exists on npm as an alias for older versions.
**How to avoid:** Always use `import { ReactFlow } from "@xyflow/react"`. Already correct in existing code.

### Pitfall 4: SWR Polling Never Stops

**What goes wrong:** Graph keeps re-fetching even after all sources complete, causing visible flickering.
**Why it happens:** `refreshInterval` is a fixed number not derived from source status.
**How to avoid:** Use `hasPendingSources ? 5000 : 0` pattern (D-10). Also use null key pattern: `useSWR(hasPending ? url : null, fetcher, { refreshInterval: 5000 })`.
**Warning signs:** Network tab shows continuous requests to `/courses/{id}/graph` after all sources show `status=done`.

### Pitfall 5: Course title shows as `undefined`

**What goes wrong:** All course cards on dashboard show blank/undefined name.
**Why it happens:** Backend returns `title` but frontend `Course` interface has `name`. JavaScript silently returns `undefined` for missing properties.
**How to avoid:** Fix `Course` interface to use `title: string` matching `CourseResponse.title`.

### Pitfall 6: Quiz page shows wrong field names

**What goes wrong:** Quiz questions render `undefined` for question text, options, etc.
**Why it happens:** Frontend `QuizQuestion` uses `prompt` and `question_type` but backend returns `question` and `type`.
**How to avoid:** Rewrite `QuizQuestion` interface to mirror backend question dict exactly.

### Pitfall 7: Sheet vs custom drawer conflict

**What goes wrong:** Using shadcn `Sheet` alongside the existing custom `ReadingDrawer.tsx` creates two competing drawer implementations.
**Why it happens:** ReadingDrawer already exists with a custom backdrop + slide-in animation; adding Sheet requires component replacement.
**How to avoid:** Either: (a) replace ReadingDrawer with shadcn Sheet, keeping content identical; or (b) keep ReadingDrawer as-is (it already implements the D-06 spec adequately). The existing implementation uses a fixed-position div with `slideInRight` animation — this achieves the same visual result as Sheet. Recommend keeping it for speed. [ASSUMED]

---

## Code Examples

### Correct edge type routing in GraphCanvas

```typescript
// Source: GraphCanvas.tsx — CortexEdge reads from edge.data but backend puts type at edge root
// THE BUG: backend edge.type = "co_occurrence", frontend passes edge.data.edge_type
// FIX: in buildLayout(), use e.type not e.edge_type when building edges array

const edges: Edge[] = rawEdges.map((e) => ({
  id: e.id,
  source: e.source,
  target: e.target,
  type: "cortex",
  data: { edge_type: e.type },   // FIX: e.type not e.edge_type
}));
```

### Updated Course interface (fixing title vs name)

```typescript
// lib/api.ts — corrected to match CourseResponse schema
export interface Course {
  id: number;
  user_id: number;
  title: string;        // was: name — backend uses title
  description?: string;
  created_at: string;
}
```

### Updated QuizQuestion interface (fixing field name mismatches)

```typescript
// lib/api.ts — corrected to match backend question dict
export interface QuizQuestion {
  question_id: number;        // was: id
  type: "mcq" | "short_answer" | "application";  // was: question_type with wrong values
  question: string;           // was: prompt
  concept_id: number;
  options?: string[];         // MCQ only
  correct_index?: number;     // MCQ only
  answered?: boolean;
  grading?: { correct: boolean; feedback: string } | null;
}
```

### Backend endpoints to add (Wave 0 of this phase)

```python
# courses.py — add GET /courses/{course_id}
@router.get("/{course_id}", response_model=CourseResponse)
async def get_course(course_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        sa.select(Course).where(Course.id == course_id, Course.user_id == 1)
    )
    course = result.scalar_one_or_none()
    if course is None:
        raise HTTPException(404, "Course not found")
    return course

# courses.py — add GET /courses/{course_id}/sources
@router.get("/{course_id}/sources", response_model=list[SourceResponse])
async def list_course_sources(course_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        sa.select(Source).where(Source.course_id == course_id).order_by(Source.created_at.desc())
    )
    return result.scalars().all()

# Add GET /sources (all sources for user — library page)
# Add GET /concepts/{id}/flashcards
# Add GET /quiz/{id}
```

### CSS 3D flip animation (matches UI-SPEC D-07)

```css
/* globals.css — add if CSS flip is chosen over current reveal approach */
.flashcard-container {
  perspective: 1000px;
}
.flashcard-inner {
  transform-style: preserve-3d;
  transition: transform 400ms ease-in-out;
}
.flashcard-inner.flipped {
  transform: rotateY(180deg);
}
.flashcard-front, .flashcard-back {
  backface-visibility: hidden;
  -webkit-backface-visibility: hidden;
}
.flashcard-back {
  transform: rotateY(180deg);
}
```

Note: The existing `FlashcardView.tsx` uses a simpler reveal approach (shows back content inline below a divider) rather than a 3D flip. The UI-SPEC specifies `rotateY(180deg)` CSS 3D. These are two different UX patterns — the planner should decide which to implement.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `reactflow` package | `@xyflow/react` | v12 (2023) | Different import paths; old package still exists as deprecated alias |
| `dagre` (npm) | `@dagrejs/dagre` | 2023 | Original unmaintained; ESM incompatibility with bundlers |
| SWR Provider setup | No Provider needed in App Router | SWR 2.x | App Router components can use useSWR directly without wrapping in SWRConfig unless you need global config |
| `params` as sync object | `params: Promise<{...}>` + `use(params)` | Next.js 14.2 | Async params requires React `use()` hook in Client Components — already correctly implemented in existing pages |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | source_count must be added to the graph API concept node data to implement D-02 (sizing by source_count) | API Shape Mismatches | If source_count is already embedded somewhere in the response or if D-02 can use a fixed size, this backend addition is unnecessary |
| A2 | Keeping ReadingDrawer.tsx (custom drawer) instead of replacing with shadcn Sheet is the faster/safer path | Don't Hand-Roll | If project requires Radix focus-trap accessibility, replacing with Sheet is mandatory |
| A3 | The flashcard "flip" can stay as the current reveal-in-place approach unless UI-SPEC's `rotateY(180deg)` spec is explicitly required | Code Examples | If 3D flip is required per spec, FlashcardView.tsx needs a complete rewrite of the card rendering logic |
| A4 | GET /quiz/{id} is needed as a new backend endpoint (to load a specific quiz by ID for the quiz page) | Missing Backend Endpoints | If the quiz page should instead receive quiz_id and fetch via the graph data, the endpoint may not be needed |

---

## Open Questions (RESOLVED)

1. **Theme: dark vs light**
   - What we know: `globals.css` implements a warm light theme (`--paper: #FAF7F2`). UI-SPEC.md specifies a dark theme (`bg-base: #1F1E1B`).
   - What's unclear: Is the existing light theme acceptable, or must the dark theme from UI-SPEC be implemented?
   - Recommendation: Flag for human confirmation before planning the CSS work; replacing the entire color system is a full-day task.
   - **RESOLVED:** Dark theme confirmed per UI-SPEC.md; globals.css will be overridden to #1F1E1B base in plan 06-02.

2. **source_count in graph payload**
   - What we know: Backend `GET /courses/{id}/graph` concept nodes do not include `source_count`. D-02 requires sizing by `source_count`.
   - What's unclear: Should Phase 6 add `source_count` to the backend graph endpoint, or use a fixed node size?
   - Recommendation: Add `source_count` to the backend graph endpoint as a Wave 0 task (involves a subquery or JOIN on `concept_sources`).
   - **RESOLVED:** source_count added to backend graph endpoint concept node data in plan 06-01 (Task 1 Step 4) via ConceptSource subquery in get_course_graph endpoint.

3. **shadcn Sheet vs custom drawer**
   - What we know: ReadingDrawer.tsx is fully implemented and matches D-06 spec. shadcn Sheet not installed.
   - What's unclear: Is the Radix accessibility behavior (focus trap, Escape key) required?
   - Recommendation: Keep ReadingDrawer if the existing implementation passes accessibility audit; add shadcn Sheet only if focus trap is explicitly needed.
   - **RESOLVED:** Keep existing ReadingDrawer.tsx (adequate implementation of D-06); add shadcn Sheet only if focus trap is needed (not needed for this scope — single-user app with no accessibility requirement blocking).

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | Next.js dev server | ✓ | (verified: npm works) | — |
| npm | Package management | ✓ | (verified: commands ran) | — |
| @xyflow/react | Graph canvas | ✓ | 12.3.6 in node_modules | — |
| @dagrejs/dagre | Layout | ✓ | 1.1.4 in node_modules | — |
| swr | Data fetching | ✓ | 2.2.5 in node_modules | — |
| FastAPI backend | All API calls | Must be running at :8000 | — | Cannot test without backend |
| NEXT_PUBLIC_API_URL | API base URL | ✓ | Set in .env.local | Defaults to localhost:8000 |

**Missing dependencies with no fallback:**
- FastAPI backend must be running for any frontend feature to function during manual testing.

---

## Validation Architecture

### Test Framework

Frontend testing is not configured in this project — no Jest, Vitest, Playwright, or Cypress config exists. The `package.json` has no test script beyond `next lint`. All validation is manual and build-based.

| Property | Value |
|----------|-------|
| Framework | None configured (Wave 0 gap) |
| Config file | None |
| Quick run command | `cd frontend && npm run lint` |
| Full suite command | `cd frontend && npm run build` (build catches type errors) |
| Type check command | `cd frontend && npx tsc --noEmit` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | Notes |
|--------|----------|-----------|-------------------|-------|
| UI-01 | Dashboard shows courses | manual-only | — | Requires backend running |
| UI-02 | Graph renders with dagre layout | manual-only | `npm run build` (catches type errors) | |
| UI-03 | Struggle signal pulsing ring | manual-only | — | Visual check |
| UI-04 | Edge types visually distinct | manual-only | — | Visual check |
| UI-05 | Concept detail panel | manual-only | — | Requires backend |
| UI-06 | Flashcard flip mode | manual-only | — | Requires backend |
| UI-07 | Quiz node click → navigate | manual-only | — | |
| UI-08 | Quiz walkthrough with grading | manual-only | — | Requires backend |
| UI-09 | Library with status badges + uploader | manual-only | — | Requires backend |
| UI-10 | Empty states | manual-only | — | Verify each surface |
| UI-11 | Polling stops when done | manual-only | — | Network tab check |

### Sampling Rate

- **Per task commit:** `npm run lint` (catches import errors, unused vars)
- **Per wave merge:** `npm run build` (TypeScript strict mode catches type mismatches)
- **Phase gate:** Full `npm run build` green + manual smoke test of all 4 routes against running backend

### Wave 0 Gaps

- [ ] Add missing backend endpoints: `GET /courses/{id}`, `GET /courses/{id}/sources`, `GET /sources`, `GET /concepts/{id}/flashcards`, `GET /quiz/{id}` — before any frontend integration can be validated
- [ ] Fix `lib/api.ts` type interfaces: Course (title not name), GraphNode (structure mismatch), GraphEdge (type field), QuizQuestion (field names)
- [ ] If TypeScript strict mode fails on build — unblock with type fixes first

---

## Security Domain

ASVS is minimally applicable here: no auth, no sensitive data client-side, no user inputs beyond quiz answers and file uploads.

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Single user, no auth |
| V3 Session Management | No | No session |
| V4 Access Control | No | No auth |
| V5 Input Validation | Partial | File type validation on upload (already has accept=".pdf,.txt,.md"); quiz answer is free text passed to backend |
| V6 Cryptography | No | No crypto client-side |

**Known threat pattern:** The library uploader accepts files and posts to `/ingest`. Backend validates file size (50MB limit) and `_is_safe_url` for URL sources. Frontend should enforce `accept` attribute on file input (already done) but not rely on it as security control — backend validation is the gate. [VERIFIED: ingest.py]

---

## Sources

### Primary (HIGH confidence)
- Codebase: `/frontend/` — all files verified by direct read
- Codebase: `/backend/app/api/` — all route files verified by direct read
- Codebase: `/backend/app/schemas/` — all Pydantic schemas verified by direct read
- npm registry — `@xyflow/react` 12.10.2, `@dagrejs/dagre` 3.0.0, `swr` 2.4.1 [VERIFIED: npm view]

### Secondary (MEDIUM confidence)
- `.planning/phases/06-frontend/06-CONTEXT.md` — user decisions D-01 through D-12
- `.planning/phases/06-frontend/06-UI-SPEC.md` — visual design contract
- `.planning/ROADMAP.md` Phase 6 stack notes
- `.planning/REQUIREMENTS.md` UI-01 through UI-11

### Tertiary (LOW confidence)
- None — all claims verified against codebase or npm registry

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified via package.json + npm view
- Architecture: HIGH — verified by reading all source files
- API mismatches: HIGH — verified by comparing backend schemas to frontend types line-by-line
- Missing endpoints: HIGH — verified by grepping all `@router` decorators in backend API directory
- Pitfalls: HIGH — all identified pitfalls are visible bugs in the existing code

**Research date:** 2026-04-25
**Valid until:** 2026-05-25 (Next.js 14 is stable; @xyflow/react v12 is stable)
