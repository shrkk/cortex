# Phase 2: Ingest + Parsing + Notch - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-25
**Phase:** 2-Ingest + Parsing + Notch
**Areas discussed:** Pipeline stopping point, Course matching algorithm, PDF chunking granularity, NotchDrop fork location

---

## Pipeline Stopping Point

| Option | Description | Selected |
|--------|-------------|----------|
| One continuous task, all stages | Background task wires all 8 stages; Phase 2 implements parse → chunk → embed; Phases 3–4 fill in stubs. Source hits status=done when all stages complete. | ✓ |
| Phase 2 stops at embedding | Background task ends after embed; source stays in a hand-off status; Phase 3 adds a separate trigger or polling loop. | |

**User's choice:** One continuous task, all stages (Recommended)
**Notes:** None

---

| Option | Description | Selected |
|--------|-------------|----------|
| status=processing until fully done | Source stays processing until all 8 stages complete; status=done only after the last real stage. | ✓ |
| Intermediate statuses per stage | Add statuses like chunked, embedded, extracting. More granular but adds schema complexity. | |
| status=done after Phase 2 stages | Phase 2 sets done after embedding; Phase 3 resets to processing. | |

**User's choice:** status=processing until fully done (Recommended)
**Notes:** None

---

| Option | Description | Selected |
|--------|-------------|----------|
| Fail immediately, no retry | Any exception sets status=error + traceback. Developer reruns manually. | ✓ |
| Retry once on transient errors | Wrap LLM/HTTP calls in a single retry for rate-limit blips. | |

**User's choice:** Fail immediately, no retry (Recommended)
**Notes:** None

---

| Option | Description | Selected |
|--------|-------------|----------|
| force=true skips source dedup only | Creates new source even if content_hash exists; extraction_cache still consulted. | ✓ |
| force=true skips both dedup AND cache | Full re-run: new source, fresh LLM calls on every chunk. | |

**User's choice:** force=true skips source dedup only (Recommended)
**Notes:** None

---

## Course Matching Algorithm

| Option | Description | Selected |
|--------|-------------|----------|
| Embed hint + cosine vs course title embeddings | Embed hint with text-embedding-3-small; cosine-compare against stored courses.embedding. Needs new migration. | ✓ |
| Fuzzy title match, no migration | Lowercase + token overlap or difflib ratio. No infra cost, breaks on abbreviations. | |
| Embed hint + fuzzy fallback hybrid | Try embedding first; fallback to fuzzy if all scores < 0.4. | |

**User's choice:** Embed hint + cosine vs course title embeddings (Recommended)
**Notes:** None

---

| Option | Description | Selected |
|--------|-------------|----------|
| Migration + backfill in seed script | Migration adds column; seed script embeds existing course titles. /courses/match works immediately after migration. | ✓ |
| Schema only, no backfill | Migration adds nullable column; embeddings only set going forward. | |

**User's choice:** Migration + backfill in seed script (Recommended)
**Notes:** None

---

| Option | Description | Selected |
|--------|-------------|----------|
| Return null when confidence < 0.65 | Response is null; Swift app shows full course picker. Clean contract. | ✓ |
| Return best guess + low confidence flag | Return {course_id, title, confidence, auto_assign: false}. Adds contract complexity. | |

**User's choice:** Return null when confidence < 0.65 (Recommended)
**Notes:** None

---

## PDF Chunking Granularity

| Option | Description | Selected |
|--------|-------------|----------|
| Page-per-chunk, no size cap | One chunk per PDF page. Simple, preserves page_num semantics. | ✓ |
| Cap at 800 tokens, split at sentence boundary | Split long pages; better embedding resolution but loses page boundary semantics. | |
| Split at paragraph/section headers | Align chunks to semantic units. Best extraction quality but adds parsing complexity. | |

**User's choice:** Page-per-chunk, no size cap (Recommended)
**Notes:** None

---

| Option | Description | Selected |
|--------|-------------|----------|
| Store raw markdown as-is | Claude vision output stored verbatim. Diagram descriptions and LaTeX included. | ✓ |
| Strip diagram descriptions, keep only text+LaTeX | Remove Claude's diagram description lines. Cleaner for embedding but loses visual context. | |

**User's choice:** Store raw markdown as-is (Recommended)
**Notes:** None

---

| Option | Description | Selected |
|--------|-------------|----------|
| Skip pages with < 50 characters | Near-empty pages skipped; avoids embedding title pages and blanks. | ✓ |
| Store all pages including blanks | Every page becomes a chunk regardless of length. | |

**User's choice:** Skip pages with < 50 characters (Recommended)
**Notes:** None

---

## NotchDrop Fork Location

| Option | Description | Selected |
|--------|-------------|----------|
| notch/ subdirectory in this repo | Clone fork into notch/ alongside backend/. One repo, one git history. | ✓ |
| Separate Xcode project outside this repo | Keep notch app as its own repo/directory. Cleaner separation but harder to coordinate. | |

**User's choice:** notch/ subdirectory in this repo (Recommended)
**Notes:** None

---

| Option | Description | Selected |
|--------|-------------|----------|
| Same plan: Cortex module + surgical edit together | One plan creates all 4 Cortex/ files AND edits the drop handler. Specialist has full context. | ✓ |
| Separate plans: module first, surgical edit second | Plan A adds files; Plan B adds the CORTEX_ENABLED guard. Cleaner git history. | |

**User's choice:** Same plan: Cortex module + surgical edit together (Recommended)
**Notes:** None

---

| Option | Description | Selected |
|--------|-------------|----------|
| http://localhost:8000 | Standard FastAPI dev server port. Hardcoded default in UserDefaults. | ✓ |
| http://127.0.0.1:8000 | Numerically equivalent; avoids DNS resolution. | |

**User's choice:** http://localhost:8000 (Recommended)
**Notes:** None

---

## Claude's Discretion

None — all decisions were made explicitly by the user.

## Deferred Ideas

- Retry logic for LLM/HTTP calls — too complex for hackathon scope; revisit in Phase 3/4 if needed
- Return top candidate course alongside low-confidence flag — v2 UX enhancement
- Token-based chunk splitting (cap at 800 tokens) — revisit if Phase 3 extraction quality suffers
