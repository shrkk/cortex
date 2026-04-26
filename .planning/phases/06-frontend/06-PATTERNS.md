# Phase 6: Frontend - Pattern Map

**Mapped:** 2026-04-25
**Files analyzed:** 15 (11 frontend, 4 backend)
**Analogs found:** 14 / 15 (one genuine gap: `GET /sources` backend endpoint)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `frontend/lib/api.ts` | utility | request-response | self (exists, needs corrections) | self |
| `frontend/components/graph/GraphCanvas.tsx` | component | event-driven | self (exists, live bug only) | self |
| `frontend/components/graph/NodeTypes.tsx` | component | event-driven | self (exists, D-04 ring fix only) | self |
| `frontend/components/ReadingDrawer.tsx` | component | request-response | self (exists, missing SWR hook) | self |
| `frontend/components/FlashcardView.tsx` | component | request-response | self (exists, wiring only) | self |
| `frontend/components/QuizView.tsx` | component | request-response | self (exists, needs API rewrite) | self |
| `frontend/components/SourceLibrary.tsx` | component | CRUD | self (exists, uploader fields missing) | self |
| `frontend/app/page.tsx` | page | CRUD | self (exists, `c.name` bug) | self |
| `frontend/app/courses/[id]/page.tsx` | page | event-driven | self (exists, node click → quiz nav missing) | self |
| `frontend/app/quiz/[id]/page.tsx` | page | request-response | self (exists, QuizView wiring broken) | self |
| `frontend/app/library/page.tsx` | page | CRUD | self (exists, upload form incomplete) | self |
| `frontend/app/globals.css` | config | — | self (exists; dark-theme question is open) | self |
| `backend/app/api/courses.py` | route | CRUD | `backend/app/api/courses.py` list_courses pattern | exact |
| `backend/app/api/concepts.py` | route | CRUD | `backend/app/api/concepts.py` get_concept_detail | exact |
| `backend/app/api/quiz.py` | route | CRUD | `backend/app/api/quiz.py` quiz_results | exact |

---

## Pattern Assignments

### `frontend/lib/api.ts` (utility, request-response)

**Current state:** File exists at lines 1–89. Four interfaces are wrong vs. backend.

**Bug 1 — Course.name vs. title** (lines 14–19, current broken form):
```typescript
export interface Course {
  id: number;
  name: string;           // BUG: backend CourseResponse uses `title`
  concept_count?: number; // BUG: not in CourseResponse — backend has no such field
  struggle_count?: number;// BUG: not in CourseResponse — backend has no such field
}
```
**Fix — replace with** (matching `backend/app/schemas/courses.py` CourseResponse lines 11–18):
```typescript
export interface Course {
  id: number;
  user_id: number;
  title: string;        // was: name
  description?: string;
  created_at: string;
}
```

**Bug 2 — GraphNode structure mismatch** (lines 32–40, current broken form):
```typescript
export interface GraphNode {
  id: string;
  node_type: "course" | "concept" | "flashcard" | "quiz"; // BUG: backend uses root "type"
  label: string;     // BUG: backend puts label inside data{}
  source_count?: number;  // BUG: absent from backend response
  has_struggle?: boolean; // BUG: backend uses has_struggle_signals
  flashcard_count?: number;
  position?: { x: number; y: number };
}
```
**Backend actually returns** (verified in `backend/app/api/courses.py` _build_graph_payload, lines 176–213):
```typescript
// Backend shape per GraphNode Pydantic schema (backend/app/schemas/graph.py lines 8–12):
// { id: string; type: string; data: { label, concept_id, depth, has_struggle_signals, flashcard_count, ... } }
export interface GraphNodeData {
  label: string;
  concept_id?: number;
  depth?: number;
  has_struggle_signals?: boolean; // was: has_struggle
  flashcard_count?: number;
  source_count?: number;          // must be ADDED to backend payload to support D-02
  quiz_id?: number;
  question_count?: number;
}
export interface GraphNode {
  id: string;
  type: "course" | "concept" | "flashcard" | "quiz"; // was: node_type
  data: GraphNodeData;                                // was: flat fields
}
```

**Bug 3 — GraphEdge.edge_type vs. type** (lines 42–47, current broken form):
```typescript
export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  edge_type: "contains" | "prerequisite" | "co_occurrence" | "related" | "flashcard_of" | "quiz_of"; // BUG: backend uses root "type"
}
```
**Fix — replace with** (matching `backend/app/schemas/graph.py` GraphEdge lines 14–19):
```typescript
export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: "contains" | "co_occurrence" | "prerequisite" | "related"; // was: edge_type
  data?: { weight?: number };
}
```

**Bug 4 — QuizQuestion field name mismatches** (lines 75–83, current broken form):
```typescript
export interface QuizQuestion {
  id: number;              // BUG: backend uses question_id
  question_type: "mcq" | "free"; // BUG: backend uses "type" with values "mcq"|"short_answer"|"application"
  prompt: string;          // BUG: backend uses "question"
  topic?: string;          // BUG: not in backend question dict
  options?: string[];
  correct_index?: number;
  explanation?: string;    // BUG: not in backend; backend has "grading" after answering
}
```
**Fix — replace with** (matching `backend/app/api/quiz.py` question dict structure, lines 272–276):
```typescript
export interface QuizQuestion {
  question_id: number;        // was: id
  type: "mcq" | "short_answer" | "application"; // was: question_type "mcq"|"free"
  question: string;           // was: prompt
  concept_id: number;         // new field
  options?: string[];         // MCQ only
  correct_index?: number;     // MCQ only
  answered?: boolean;
  grading?: { correct: boolean; feedback: string } | null;
}

export interface Quiz {
  id: number;
  course_id: number;
  questions: QuizQuestion[];
}
```

**Add new SourceResponse interface** (needed for library page and polling; Source model: `backend/app/models/models.py` lines 43–68):
```typescript
export interface Source {
  id: number;
  course_id: number;
  source_type: "pdf" | "url" | "image" | "text" | "chat_log";
  title?: string;
  status: "pending" | "processing" | "done" | "error";
  created_at: string;
}
```
Note: The existing `Source` interface (lines 21–30) is already correct — it matches the model. Keep it.

---

### `frontend/components/graph/GraphCanvas.tsx` (component, event-driven)

**Current state:** File fully exists (lines 1–344). Two live bugs.

**Bug 1 — buildLayout reads wrong field names** (lines 84–114):

Current broken code at lines 84–86:
```typescript
rawNodes.forEach((n) => {
  const { w, h } = nodeSize(n.node_type, n.source_count);  // BUG: n.node_type doesn't exist
  g.setNode(n.id, { width: w, height: h });
```

Current broken code at lines 93–106:
```typescript
const nodes: Node[] = rawNodes.map((n) => {
  const pos = g.node(n.id);
  return {
    id: n.id,
    type: n.node_type,              // BUG: should be n.type
    position: { x: pos.x - pos.width / 2, y: pos.y - pos.height / 2 },
    data: {
      label:        n.label,        // BUG: should be n.data.label
      source_count: n.source_count, // BUG: should be n.data.source_count
      has_struggle: n.has_struggle, // BUG: should be n.data.has_struggle_signals
      flashcard_count: n.flashcard_count, // BUG: should be n.data.flashcard_count
    },
  };
```

Current broken code at line 113:
```typescript
data: { edge_type: e.edge_type },  // BUG: backend has e.type not e.edge_type
```

**Fix pattern** — read from `n.type` and `n.data.*` (matching backend GraphNode schema):
```typescript
// In buildLayout():
rawNodes.forEach((n) => {
  const { w, h } = nodeSize(n.type, n.data.source_count);  // n.type, n.data.source_count
  g.setNode(n.id, { width: w, height: h });
});

const nodes: Node[] = rawNodes.map((n) => {
  const pos = g.node(n.id);
  return {
    id: n.id,
    type: n.type,                           // was: n.node_type
    position: { x: pos.x - pos.width / 2, y: pos.y - pos.height / 2 },
    data: {
      label:           n.data.label,        // was: n.label
      source_count:    n.data.source_count, // was: n.source_count
      has_struggle:    n.data.has_struggle_signals, // was: n.has_struggle (wrong name)
      flashcard_count: n.data.flashcard_count,
      quiz_id:         n.data.quiz_id,      // new: needed for quiz navigation
      concept_id:      n.data.concept_id,   // new: needed for panel open
    },
  };
});

const edges: Edge[] = rawEdges.map((e) => ({
  id: e.id,
  source: e.source,
  target: e.target,
  type: "cortex",
  data: { edge_type: e.type },  // was: e.edge_type (wrong — backend puts type at root)
}));
```

**Bug 2 — quiz node click does not navigate** — handleNodeClick (lines 143–148) only handles `concept` type. Needs quiz case:
```typescript
// Current at lines 143-148:
const handleNodeClick = useCallback(
  (_: React.MouseEvent, node: Node) => {
    onNodeClick?.(node.id, node.type ?? "concept");
  },
  [onNodeClick]
);
// The parent CoursePage.handleNodeClick (courses/[id]/page.tsx line 46-52) handles routing
// but currently only checks nodeType === "concept" — need to add quiz branch there.
```

**D-04 struggle ring** — ConceptNode currently uses a filled dot (line 96–110 in NodeTypes.tsx), not a pulsing ring. Per D-04, the spec is a pulsing ring around the node circle. The ring should be added as an absolute-positioned ring span outside the circle div:
```typescript
// Add ring span OUTSIDE the circle div (not inside):
{d.has_struggle && (
  <span style={{
    position: "absolute",
    inset: -4,           // 4px outside the circle edge
    borderRadius: 999,
    border: "2px solid var(--mastery-low)",
    animation: "graphPulse 1.6s ease-in-out infinite",
    pointerEvents: "none",
  }} />
)}
```
The `graphPulse` keyframe already exists in `globals.css` (lines 158–161).

---

### `frontend/components/NodeTypes.tsx` (component, event-driven)

**Current state:** Fully implemented (lines 1–168). One D-04 conformance fix needed (see GraphCanvas.tsx section above). No other changes required.

**Reference pattern for all node wrappers** (lines 12–41, CourseNode):
```typescript
export const CourseNode = memo(function CourseNode({ data }: NodeProps) {
  // Always React.memo — critical for performance (ROADMAP constraint)
  // Always include hidden Handle elements for edge rendering
  // Always use CSS variables (var(--accent), var(--surface), etc.) — not hardcoded colors
  return (
    <>
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Top}    style={{ opacity: 0 }} />
      <div style={{ ... }}>
        {d.label}
      </div>
    </>
  );
});
```

---

### `frontend/components/ReadingDrawer.tsx` (component, request-response)

**Current state:** Fully implemented (lines 1–427). Props-driven — parent page passes `concept` and `flashcards`. Missing: parent (CoursePage) does not pass `onGenerateQuiz` that actually does anything. The quiz node click needs to be wired separately.

**In-place panel mode switch pattern** (lines 21–22, 122–135) — copy this for any future panel content switch:
```typescript
const [mode, setMode] = useState<"detail" | "flashcards">("detail");

{mode === "flashcards" ? (
  <FlashcardView flashcards={flashcards} conceptTitle={concept.title} embedded />
) : (
  <ConceptDetail concept={concept} onViewFlashcards={() => setMode("flashcards")} ... />
)}
```

**Missing wiring:** `onGenerateQuiz` prop (line 18) is passed but the parent `CoursePage` passes `undefined`. The CoursePage `onGenerateQuiz` should call `POST /quiz` then `router.push('/quiz/${newQuizId}')`.

**Backend field mapping for ConceptDetailResponse** — already correctly handled in ReadingDrawer. The `Concept` interface in api.ts maps to `ConceptDetailResponse` (backend/app/schemas/concepts.py):
- `concept.summary` → `ConceptDetailResponse.summary` (which maps from `Concept.definition`) ✓
- `concept.struggle_signals` → `ConceptDetailResponse.struggle_signals` (dict | null — not an array)

**Type mismatch:** `api.ts` Concept interface (line 64) has `struggle_signals?: Array<{ label: string; detail: string }>` but backend returns `dict | None` (a raw dict, not an array). The ReadingDrawer iterates it as an array (line 283: `.map(...)`). Fix: either (a) normalize in the endpoint to always return a list, or (b) update the frontend to handle dict. Check actual backend output shape before fixing.

---

### `frontend/components/FlashcardView.tsx` (component, request-response)

**Current state:** Fully implemented (lines 1–193). Uses reveal-in-place (not 3D flip). Driven by props — no SWR inside it. All data fetching is in CoursePage which passes `flashcards` to ReadingDrawer which passes to FlashcardView.

**No changes needed to FlashcardView itself.** The gap is in CoursePage: the `flashcards` SWR hook at line 31 calls `GET /concepts/{id}/flashcards` which does not exist in backend yet (Wave 0 task).

**Current keyboard pattern** (lines 28–35) — reference for any keyboard-driven component:
```typescript
useEffect(() => {
  const onKey = (e: KeyboardEvent) => {
    if (e.key === " ") { e.preventDefault(); setRevealed((r) => !r); }
    if (e.key === "ArrowRight") setIdx((i) => (i + 1) % flashcards.length);
    if (e.key === "ArrowLeft")  setIdx((i) => (i - 1 + flashcards.length) % flashcards.length);
  };
  window.addEventListener("keydown", onKey);
  return () => window.removeEventListener("keydown", onKey);
}, [flashcards.length]);
```

---

### `frontend/components/QuizView.tsx` (component, request-response)

**Current state:** Implemented (lines 1–297) with static local grading. Three bugs.

**Bug 1 — reads wrong field names** (lines 30–31, 54, 104, 115–116, 120, 188, 213):
```typescript
// CURRENT (broken) — reads from wrong fields:
if (q.question_type === "mcq") {   // should be q.type
  setResults((r) => [...r, selected === q.correct_index]);
}
const canSubmit = q.question_type === "mcq" ? ...  // should be q.type
{q.topic && ...}                  // topic doesn't exist in backend
{q.prompt}                        // should be q.question
{q.question_type === "mcq" && q.options && ...}  // should be q.type
{q.question_type === "free" && ...}              // should be q.type !== "mcq"
{submitted && q.explanation && ...}              // explanation doesn't exist in backend
```

**Fix pattern** — update all field reads to match backend QuizQuestion dict:
```typescript
// After QuizQuestion interface fix in api.ts, update QuizView:
if (q.type === "mcq") { ... }
q.type === "mcq" ? selected !== null : freeText.trim().length > 0
{q.question}          // was: q.prompt
{q.type === "mcq" && q.options && ...}
{q.type !== "mcq" && ...}   // textarea for short_answer or application
```

**Bug 2 — static local grading instead of POST /quiz/{id}/answer**:

Current handleSubmit (lines 28–35) grades locally. Must call `POST /quiz/{id}/answer`:
```typescript
// Replacement pattern using apiFetch:
const handleSubmit = async () => {
  const answerText = q.type === "mcq"
    ? q.options![selected!]   // send option text, not index
    : freeText;
  const result = await apiFetch<AnswerResponse>(`/quiz/${quizId}/answer`, {
    method: "POST",
    body: JSON.stringify({ question_id: q.question_id, answer: answerText }),
  });
  setGrading(result.grading);
  setNextQuestion(result.next_question ?? null);
  setIsComplete(result.is_complete);
  if (result.is_complete) { setScore(result); }
};
```

**Bug 3 — QuizResults shows no concept review list**:

Current QuizResults (lines 256–297) receives no `weakConcepts`. The `AnswerResponse` includes `concepts_to_review: number[]` (concept IDs). QuizResults needs to show these concept IDs (or names if fetched).

**QuizView needs quizId prop** — currently accepts `questions: QuizQuestion[]` but needs quiz ID for POST /answer:
```typescript
// Signature change:
interface QuizViewProps {
  quizId: number;         // new
  questions: QuizQuestion[];
  onComplete?: (score: number, total: number, weakConcepts: number[]) => void;
}
```

---

### `frontend/components/SourceLibrary.tsx` (component, CRUD)

**Current state:** Implemented (lines 1–254). One gap: the `onUpload` callback only receives a `File`. The library page's `handleUpload` (library/page.tsx lines 14–18) posts the file but is missing `course_id` and `kind` fields.

**Current broken upload** (library/page.tsx lines 14–18):
```typescript
const handleUpload = async (file: File) => {
  const form = new FormData();
  form.append("file", file);              // MISSING: course_id, kind
  await fetch(`${process.env.NEXT_PUBLIC_API_URL}/ingest`, { method: "POST", body: form });
  mutate("/sources");
};
```

**Backend ingest requires** (`backend/app/schemas/ingest.py` lines 5–8):
```python
class IngestFileForm(BaseModel):
    course_id: int
    kind: Literal["pdf", "image", "text", "url"]
```

**Fix pattern** — SourceLibrary needs a course selector dropdown and the upload form must append `course_id` and `kind`:
```typescript
// SourceLibrary needs courses prop for dropdown:
interface SourceLibraryProps {
  sources: Source[];
  courses: Course[];   // new — for course selector
  onUpload?: (file: File, courseId: number, kind: string) => void; // signature change
}

// library/page.tsx handleUpload fix:
const handleUpload = async (file: File, courseId: number, kind: string) => {
  const form = new FormData();
  form.append("file", file);
  form.append("course_id", String(courseId));
  form.append("kind", kind);
  await fetch(`${BASE}/ingest`, { method: "POST", body: form });
  mutate("/sources");
};
```

---

### `frontend/app/page.tsx` (page, CRUD)

**Current state:** Implemented (lines 1–84). One field name bug.

**Bug — uses c.name instead of c.title** (lines 52, 58–60):
```typescript
// line 52: checks c.struggle_count — field doesn't exist
{(c.struggle_count ?? 0) > 0 && (
  <Pill tone="low" dot>{c.struggle_count} struggling</Pill>
)}
// line 58: renders c.name — backend returns c.title
<h2 ...>{c.name}</h2>          // BUG: shows undefined
// line 60: renders c.concept_count — field doesn't exist in backend
{c.concept_count ?? 0} concepts  // shows 0 always
```

**Fix pattern** — after `Course` interface fix in api.ts:
```typescript
// Replace c.name → c.title:
<h2 ...>{c.title}</h2>
// Remove/simplify c.struggle_count (not in backend):
// Either omit the struggling pill or derive from a separate SWR hook
// Remove/simplify c.concept_count (not in backend):
// Either show "0 concepts" always or add a backend field
```

**Correct SWR fetcher pattern** (lines 9–12) — copy for all new SWR hooks:
```typescript
const fetcher = (url: string) => apiFetch<Course[]>(url);
// ...
const { data: courses, error } = useSWR("/courses", fetcher);
```

---

### `frontend/app/courses/[id]/page.tsx` (page, event-driven)

**Current state:** Implemented (lines 1–113). Three gaps.

**Gap 1 — course?.name instead of title** (line 64):
```typescript
{course?.name ?? "Loading…"}  // BUG: backend returns course.title
// Fix:
{course?.title ?? "Loading…"}
```

**Gap 2 — node filter uses wrong field** (lines 65–68):
```typescript
{graph.nodes.filter(n => n.node_type === "concept").length}  // BUG: n.node_type
{graph.nodes.filter(n => n.node_type === "concept" && n.has_struggle).length} // BUG: n.node_type, n.has_struggle
// Fix after GraphNode interface fix:
{graph.nodes.filter(n => n.type === "concept").length}
{graph.nodes.filter(n => n.type === "concept" && n.data.has_struggle_signals).length}
```

**Gap 3 — quiz node click not handled** (lines 46–52):
```typescript
// Current:
const handleNodeClick = (nodeId: string, nodeType: string) => {
  if (nodeType === "concept") {
    const numId = parseInt(nodeId, 10);
    if (!isNaN(numId)) setSelectedConceptId(numId);
  }
  // quiz node → navigate (handled by link in node or here)  ← TODO comment never implemented
};
// Fix — add router and quiz branch:
import { useRouter } from "next/navigation";
const router = useRouter();

const handleNodeClick = (nodeId: string, nodeType: string, nodeData?: GraphNodeData) => {
  if (nodeType === "concept") {
    const numId = nodeData?.concept_id ?? parseInt(nodeId.replace("concept-", ""), 10);
    if (!isNaN(numId)) setSelectedConceptId(numId);
  }
  if (nodeType === "quiz") {
    const quizId = nodeData?.quiz_id;
    if (quizId) router.push(`/quiz/${quizId}`);
  }
};
```

**Gap 4 — polling refreshInterval callback uses wrong form** (lines 21–25):
```typescript
// Current broken:
refreshInterval: (data) => {
  return 0;  // Never actually polls — always 0
},
// Correct per D-10 (and verified pattern in research):
// The polling is already correctly implemented separately at lines 38-43
// BUT the initial graphData hook (line 19) does not need refreshInterval
// The hasPending → liveGraph pattern (lines 37-44) is correct; keep it.
```

**SWR with async params pattern** (lines 14–15) — copy for all dynamic pages:
```typescript
export default function CoursePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);  // React.use() for async params in Next.js 14
```

---

### `frontend/app/quiz/[id]/page.tsx` (page, request-response)

**Current state:** Implemented (lines 1–40). One wiring gap.

**Gap — QuizView receives questions array but needs quizId for answer submission**:
```typescript
// Current at line 37:
<QuizView questions={quiz.questions} />
// Fix — pass quiz.id:
<QuizView quizId={quiz.id} questions={quiz.questions} />
```

The SWR hook `useSWR('/quiz/${id}', fetcher)` (line 13) calls `GET /quiz/{id}` which does NOT EXIST yet in the backend (Wave 0 task). The endpoint must be added before this page works.

---

### `frontend/app/library/page.tsx` (page, CRUD)

**Current state:** Implemented (lines 1–26). Missing `course_id` and `kind` in upload form (documented in SourceLibrary section above). Also missing: `GET /sources` backend endpoint does not exist yet (Wave 0 task).

**SWR mutation pattern** (lines 12–18) — copy for any POST-then-invalidate:
```typescript
const { mutate } = useSWRConfig();
// ... after POST:
mutate("/sources");  // invalidates the /sources cache key
```

---

### `frontend/app/globals.css` (config)

**Current state:** Full warm light theme (lines 1–181). Key design tokens:
- Base: `--paper: #FAF7F2` (light warm cream) — contradicts UI-SPEC dark theme `#1F1E1B`
- Accent: `--accent: #C96442` (terracotta — matches notch palette)
- All animations already defined: `fadeIn`, `slideInRight`, `graphPulse`, `pulse` (lines 148–166)
- React Flow overrides already applied (lines 171–181)

**Open decision (block for human confirmation):** Keep warm light theme vs. replace with dark theme from UI-SPEC. Dark theme would require replacing all `--paper`, `--surface`, `--ink` values. The animations and accent colors would stay.

**CSS 3D flip addition** (if D-07 3D flip chosen over current reveal approach):
```css
/* Add to globals.css after existing animations */
.flashcard-container { perspective: 1000px; }
.flashcard-inner {
  transform-style: preserve-3d;
  transition: transform 400ms var(--ease);
}
.flashcard-inner.flipped { transform: rotateY(180deg); }
.flashcard-front, .flashcard-back {
  backface-visibility: hidden;
  -webkit-backface-visibility: hidden;
}
.flashcard-back { transform: rotateY(180deg); }
```

---

### `backend/app/api/courses.py` (route, CRUD) — additions

**Current state:** Has `GET /courses`, `POST /courses`, `GET /courses/match`, `GET /courses/{id}/graph`. Missing: `GET /courses/{id}` and `GET /courses/{id}/sources`.

**Pattern to copy for GET /courses/{id}** — from existing `list_courses` (lines 22–27) + ownership check from `get_course_graph` (lines 117–121):
```python
@router.get("/{course_id}", response_model=CourseResponse)
async def get_course(course_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        sa.select(Course).where(Course.id == course_id, Course.user_id == 1)
    )
    course = result.scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return course
```

**Pattern to copy for GET /courses/{id}/sources** — same ownership guard, filter by course_id:
```python
@router.get("/{course_id}/sources", response_model=list[SourceResponse])
async def list_course_sources(course_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        sa.select(Source)
        .where(Source.course_id == course_id)
        .order_by(Source.created_at.desc())
    )
    return result.scalars().all()
```

**SourceResponse schema needed** — does not exist yet. Model at `backend/app/models/models.py` lines 43–68:
```python
class SourceResponse(BaseModel):
    id: int
    course_id: int
    source_type: str
    title: str | None = None
    status: str
    created_at: datetime
    model_config = {"from_attributes": True}
```

**GET /sources (all sources for user)** — for library page:
```python
# Add to a new or existing sources router
@router.get("", response_model=list[SourceResponse])
async def list_sources(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        sa.select(Source)
        .join(Course, Source.course_id == Course.id)
        .where(Course.user_id == 1)
        .order_by(Source.created_at.desc())
    )
    return result.scalars().all()
```
This needs a new `backend/app/api/sources.py` file OR a prefix on courses router. Check `backend/app/api/router.py` for where to mount it.

---

### `backend/app/api/concepts.py` (route, CRUD) — addition

**Current state:** Has `GET /concepts/{id}` only (lines 1–88). Missing: `GET /concepts/{id}/flashcards`.

**Pattern to copy** — same ownership guard from existing endpoint (lines 34–41), then query Flashcard table:
```python
@router.get("/{concept_id}/flashcards")
async def list_concept_flashcards(
    concept_id: int,
    session: AsyncSession = Depends(get_session),
):
    # Ownership check (same as get_concept_detail lines 34-41):
    result = await session.execute(
        sa.select(Concept)
        .join(Course, Concept.course_id == Course.id)
        .where(Concept.id == concept_id, Course.user_id == 1)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Concept not found")

    fc_result = await session.execute(
        sa.select(Flashcard).where(Flashcard.concept_id == concept_id)
    )
    return fc_result.scalars().all()
```

**FlashcardResponse schema needed** — Flashcard model at `backend/app/models/models.py` lines 163–177:
```python
class FlashcardResponse(BaseModel):
    id: int
    concept_id: int
    front: str
    back: str
    card_type: str  # "definition" | "application" | "gotcha" | "compare"
    created_at: datetime
    model_config = {"from_attributes": True}
```

---

### `backend/app/api/quiz.py` (route, CRUD) — addition

**Current state:** Has `POST /quiz`, `GET /quiz/{id}/results`, `POST /quiz/{id}/answer`. Missing: `GET /quiz/{id}`.

**Pattern to copy** — from existing `quiz_results` (lines 302–340), same DB read + strip reference answers:
```python
@router.get("/{quiz_id}", response_model=QuizResponse)
async def get_quiz(quiz_id: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            sa.select(Quiz).where(Quiz.id == quiz_id)
        )
        quiz = result.scalar_one_or_none()
    if not quiz:
        raise HTTPException(404, "Quiz not found")
    return QuizResponse(
        id=quiz.id,
        course_id=quiz.course_id,
        questions=_strip_reference_answers(quiz.questions or []),
    )
```
Note: `_strip_reference_answers` is already defined at lines 115–124 in quiz.py.

**Route ordering constraint** — `GET /{quiz_id}` must be registered AFTER `GET /{quiz_id}/results` in the router (or use different path), otherwise FastAPI will match `/results` as a quiz_id. Current ordering has `/{quiz_id}/results` first (line 302), which is correct. New `GET /{quiz_id}` can be appended after.

---

## Shared Patterns

### SWR Fetcher
**Source:** `frontend/app/page.tsx` line 9, `frontend/app/quiz/[id]/page.tsx` line 9
**Apply to:** All pages using SWR
```typescript
const fetcher = (url: string) => apiFetch<T>(url);
const { data, error } = useSWR("/path", fetcher);
```

### SWR Conditional Fetch (null key = disabled)
**Source:** `frontend/app/courses/[id]/page.tsx` lines 27–34
**Apply to:** Any data that only loads on user action (concept panel, flashcard view)
```typescript
const { data: concept } = useSWR(
  selectedConceptId ? `/concepts/${selectedConceptId}` : null,
  fetcher as any
);
```

### SWR Polling with Auto-Stop (D-10)
**Source:** `frontend/app/courses/[id]/page.tsx` lines 37–44
**Apply to:** Graph polling in CoursePage
```typescript
const hasPending = sources?.some(s => s.status === "pending" || s.status === "processing");
const { data: liveGraph } = useSWR<GraphData>(
  hasPending ? `/courses/${id}/graph` : null,
  fetcher as any,
  { refreshInterval: 5000 }
);
const graph = liveGraph ?? graphData;
```

### SWR Mutation After POST
**Source:** `frontend/app/library/page.tsx` lines 12–18
**Apply to:** Library upload, course creation, quiz generation
```typescript
const { mutate } = useSWRConfig();
// ... after successful POST:
mutate("/sources");  // or whichever key to invalidate
```

### Async Params (Next.js 14 App Router)
**Source:** `frontend/app/courses/[id]/page.tsx` lines 14–15
**Apply to:** All dynamic route pages
```typescript
export default function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
```

### FastAPI Route Pattern
**Source:** `backend/app/api/courses.py` lines 22–27
**Apply to:** All new backend route handlers
```python
@router.get("", response_model=list[CourseResponse])
async def list_courses(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        sa.select(Course).where(Course.user_id == 1).order_by(Course.created_at)
    )
    return result.scalars().all()
```

### FastAPI Ownership Guard
**Source:** `backend/app/api/concepts.py` lines 34–41
**Apply to:** All new backend endpoints that access per-user data (sources, flashcards, quiz)
```python
result = await session.execute(
    sa.select(Concept)
    .join(Course, Concept.course_id == Course.id)
    .where(Concept.id == concept_id, Course.user_id == 1)
)
concept = result.scalar_one_or_none()
if concept is None:
    raise HTTPException(status_code=404, detail="Concept not found")
```

### CSS Variable Usage
**Source:** `frontend/app/globals.css` lines 10–88, used throughout all components
**Apply to:** All new CSS and inline styles — never use hardcoded color values
```css
var(--ink)           /* primary text */
var(--ink-muted)     /* secondary text */
var(--ink-faint)     /* placeholder/disabled */
var(--surface)       /* card/panel background */
var(--paper)         /* page background */
var(--accent)        /* terracotta #C96442 — buttons, highlights */
var(--border)        /* default border */
var(--mastery-low)   /* red/danger — struggle signals */
var(--mastery-high)  /* green/success */
var(--ease)          /* cubic-bezier(0.2, 0.6, 0.2, 1) — all transitions */
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `backend/app/api/sources.py` (new file) | route | CRUD | No sources list endpoint exists anywhere in backend; GET /sources must be a new router file or added to an existing file |

---

## Critical Implementation Order (Wave 0 must precede Wave 1)

The following backend gaps **block** frontend integration. They must be the first wave:

1. `backend/app/schemas/courses.py` — add `SourceResponse` model
2. `backend/app/api/courses.py` — add `GET /courses/{id}` and `GET /courses/{id}/sources`
3. `backend/app/api/sources.py` — new file with `GET /sources`
4. `backend/app/api/concepts.py` — add `GET /concepts/{id}/flashcards`
5. `backend/app/api/quiz.py` — add `GET /quiz/{id}`
6. `backend/app/api/courses.py` `_build_graph_payload` — add `source_count` to concept node data (needed for D-02 node sizing)
7. `frontend/lib/api.ts` — fix all four interface mismatches (Course, GraphNode, GraphEdge, QuizQuestion)

Only after Wave 0 can the frontend SWR hooks be validated against real responses.

---

## Metadata

**Analog search scope:** `/frontend/` (all), `/backend/app/api/` (all), `/backend/app/schemas/` (all), `/backend/app/models/models.py`
**Files read:** 15 source files
**Pattern extraction date:** 2026-04-25
