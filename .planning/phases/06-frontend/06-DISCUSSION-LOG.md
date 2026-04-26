# Phase 6: Frontend - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-25
**Phase:** 06-frontend
**Areas discussed:** Graph node style, Detail panel vs. route, Data fetching approach

---

## Graph Node Style

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal circles | Colored circles with title label below | ✓ |
| Rounded-rect cards | Small card with title + gotcha snippet | |
| You decide | Claude picks | |

**User's choice:** Minimal circles

### Node sizing

| Option | Description | Selected |
|--------|-------------|----------|
| Small fixed (40px) | Same size all nodes | |
| Scaled by source_count | 30–70px range | |
| You decide | Claude picks | ✓ |

**User's choice:** You decide (Claude discretion — scaled 32–48px by source_count)

### Course root node

| Option | Description | Selected |
|--------|-------------|----------|
| Larger + labeled circle | 60px with name inside | ✓ |
| Different shape (square/rect) | Visually distinct type | |
| You decide | Claude picks | |

**User's choice:** Larger labeled circle (60px)

---

## Detail Panel vs. Route

### Where does concept detail appear?

| Option | Description | Selected |
|--------|-------------|----------|
| Slide-in right panel | shadcn Sheet, ~380px, overlays graph, URL unchanged | ✓ |
| Separate route (/concepts/[id]) | Full-page, loses graph context | |
| You decide | Claude picks | |

**User's choice:** Slide-in right panel

### Where do flashcards appear?

| Option | Description | Selected |
|--------|-------------|----------|
| Replace panel content | In-panel transition, back button returns to detail | ✓ |
| Full-page route (/flashcards/[concept-id]) | Navigates away from graph | |

**User's choice:** Replace panel content in-place

---

## Data Fetching Approach

### Library choice

| Option | Description | Selected |
|--------|-------------|----------|
| SWR | Vercel library, native Next.js fit, small bundle | ✓ |
| TanStack React Query | More powerful, heavier setup | |
| Native fetch/useEffect | No library, manual polling boilerplate | |

**User's choice:** SWR

### Polling stop mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Conditional refreshInterval | `refreshInterval: hasPendingSources ? 5000 : 0` | ✓ |
| You decide | Claude picks | |

**User's choice:** Conditional refreshInterval (exact SWR pattern locked in)

---

## Claude's Discretion

- Visual theme / color palette — deferred to `/gsd-ui-phase 6` UI-SPEC.md
- Node size scaling formula (guidance: 32–48px linear by source_count)
- Edge visual treatment (thickness, dash patterns per requirement spec)
- shadcn component selection per surface
- Exact flashcard flip animation

## Deferred Ideas

- Visual theme discussion — intentionally deferred to UI-SPEC.md (user has Claude design template to bring via `/gsd-ui-phase 6`)
- Mobile responsive layout — out of scope per PROJECT.md
- Real-time WebSocket/SSE — out of scope; polling is spec
