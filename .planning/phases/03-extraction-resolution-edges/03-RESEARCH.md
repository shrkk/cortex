# Phase 3: Extraction, Resolution & Edges — Research

**Researched:** 2026-04-25
**Domain:** LLM-based concept extraction, pgvector cosine resolution, graph edge inference, asyncio parallelism
**Confidence:** HIGH (codebase verified, Anthropic SDK verified via Context7, pgvector verified via Context7)

---

## Summary

Phase 3 replaces three pipeline stubs (`_stage_extract_stub`, `_stage_resolve_stub`, `_stage_edges_stub`) in `backend/app/pipeline/pipeline.py` with real implementations. The existing pipeline infrastructure — session-per-stage pattern, `AsyncSessionLocal`, `AsyncAnthropic` client already used in `parsers.py` — provides a complete working foundation. No new Alembic migrations are needed: all target tables (`concepts`, `edges`, `extraction_cache`, `concept_sources`) are already created in `0001_initial.py`.

The three stages must be split into separate module files (`extractor.py`, `resolver.py`, `edges.py`) parallel to the existing `parsers.py`, keeping `pipeline.py` as an orchestrator only. Each file contains one pure async function that takes `source_id` (and possibly `course_id`) and opens its own `AsyncSessionLocal` sessions internally.

The critical design constraint is course-scoped concept resolution: every cosine similarity query MUST include `AND course_id = :course_id` — pgvector's ORM `.cosine_distance()` method combined with a `.where(Concept.course_id == course_id)` filter achieves this cleanly. The `extraction_cache` table has a unique composite index on `(chunk_hash, model_version)` already in place for O(1) cache lookups.

**Primary recommendation:** Split extract/resolve/edges into three separate module files; use `asyncio.Semaphore(5)` for parallel chunk extraction; use `Concept.embedding.cosine_distance(vec).label("dist")` for resolution queries; use Python BFS (`collections.deque`) for depth computation rather than a recursive SQL CTE.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EXTRACT-01 | 0–6 concepts per chunk; no generic titles or acronym-only titles | Extraction prompt engineering + negative instructions |
| EXTRACT-02 | Concept fields: title (Title Case, singular, canonical), definition, key_points, gotchas, examples, related_concepts | Tool schema JSON definition |
| EXTRACT-03 | Student questions extracted verbatim only for `chat_log` source types | Source type check before extraction call |
| EXTRACT-04 | LLM via tool_use with `additionalProperties: false`; retry once on parse failure | Anthropic SDK tool_use pattern |
| EXTRACT-05 | Max 5 chunks in parallel; extraction_cache checked before every call | asyncio.Semaphore(5) pattern |
| RESOLVE-01 | Course-scoped ONLY — `AND course_id = :course_id` in all cosine queries | pgvector `.cosine_distance()` + `.where()` filter |
| RESOLVE-02 | Cosine ≥ 0.92 → merge (append ConceptSource, merge key_points/gotchas/examples) | Direct ORM update pattern |
| RESOLVE-03 | Cosine 0.80–0.91 → LLM tiebreaker `{"same": bool, "reason": string}`; merge if same=true | Second tool_use call pattern |
| RESOLVE-04 | Cosine < 0.80 → create new concept node | INSERT Concept + ConceptSource |
| RESOLVE-05 | Two PDFs on "Gradient Descent" in same course → ONE concept | RESOLVE-01+02+03 working together |
| EDGE-01 | Course → concept `contains` edge when concept added | Special-cased virtual edge (edges table stores concept-to-concept only) |
| EDGE-02 | Co-occurrence edges between all concept pairs from same chunk; weight++ on repeat | SET-based pair enumeration + UPSERT |
| EDGE-03 | Prerequisite edges inferred by LLM per course (max 50 concepts/call, max 30 edges/output) | Batch LLM call with tool_use |
| EDGE-04 | `concepts.depth` recomputed via BFS from course root through `contains` + `prerequisite` edges | Python BFS using prerequisite edges; contains-linked concepts start at depth=1 |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Chunk-to-concept LLM extraction | API / Backend (pipeline stage 4) | — | Background task, no HTTP surface |
| ExtractionCache lookup/upsert | Database / Storage | API Backend | Keyed on SHA-256 + model version |
| Concept embedding | API Backend (OpenAI call) | Database | 1536-dim vector stored on concept row |
| Cosine resolution query | Database / Storage (pgvector HNSW) | API Backend | hnsw index on concepts.embedding already created |
| LLM tiebreaker (0.80–0.91) | API / Backend | — | Anthropic API call within resolver |
| Co-occurrence edge upsert | Database / Storage | API Backend | Weight increment on conflict |
| Prerequisite edge inference | API / Backend (LLM batch) | Database | Course-scoped LLM call → DB write |
| BFS depth computation | API / Backend (Python in-memory) | — | Cheaper than recursive SQL CTE for <1000 nodes |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `anthropic` | 0.97.0 (pinned) | Claude tool_use API calls | Already in requirements.txt; `AsyncAnthropic` already used in parsers.py |
| `openai` | 2.32.0 (pinned) | text-embedding-3-small for concept embeddings | Already in requirements.txt; already used for chunk embeddings in pipeline.py |
| `pgvector` | 0.4.2 (pinned) | `.cosine_distance()` ORM method on Vector column | Already in requirements.txt; hnsw index on concepts.embedding already live |
| `sqlalchemy` | 2.0.49 (pinned) | Async ORM queries | Already in requirements.txt; session-per-stage pattern established |

[VERIFIED: backend/requirements.txt]

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `collections.deque` | stdlib | BFS queue for depth computation | EDGE-04 — Python BFS simpler than recursive CTE |
| `asyncio.Semaphore` | stdlib | Limit parallel chunk processing | EXTRACT-05 — max 5 parallel chunks |
| `hashlib.sha256` | stdlib | chunk_hash computation | EXTRACT-05 — already used in pipeline.py for content_hash |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Python BFS for depth | Recursive SQL CTE (`WITH RECURSIVE`) | SQL CTE elegant but harder to test; Python BFS testable with mocks and handles the virtual "course root" cleanly |
| `asyncio.gather` + semaphore | `asyncio.gather` alone | Without semaphore, all chunks run concurrently and may hit Anthropic rate limits |
| Tool_use for extraction | Free-text JSON parsing | Tool_use gives guaranteed schema; free-text requires regex/manual parsing and breaks unpredictably |

**Installation:** No new packages needed — all already in `requirements.txt`. [VERIFIED: backend/requirements.txt]

---

## Architecture Patterns

### System Architecture Diagram

```
pipeline.run_pipeline(source_id)
  │
  ├─ [stages 1-3 already implemented]
  │
  ├─ _stage_extract(source_id)  ← replaces _stage_extract_stub
  │    │
  │    ├─ SELECT chunks WHERE source_id = :sid
  │    ├─ asyncio.gather(*[_extract_chunk(c) for c in chunks], semaphore=5)
  │    │    ├─ SHA-256(chunk.text) → chunk_hash
  │    │    ├─ SELECT extraction_cache WHERE chunk_hash=X AND model_version=Y
  │    │    │    ├─ HIT → return cached extracted_concepts (skip LLM)
  │    │    │    └─ MISS → call Anthropic tool_use → INSERT extraction_cache
  │    │    └─ return list[ConceptData]
  │    └─ INSERT Concept rows (or queue for resolver)
  │
  ├─ _stage_resolve(source_id)  ← replaces _stage_resolve_stub
  │    │
  │    ├─ SELECT concepts WHERE source_id via concept_sources (newly created)
  │    ├─ for each new concept:
  │    │    ├─ embed(title + " " + definition) → vec
  │    │    ├─ SELECT concepts.cosine_distance(vec) WHERE course_id=X ORDER BY dist LIMIT 1
  │    │    │    ├─ dist < 0.08 (≥0.92 cosine) → MERGE: append ConceptSource, extend JSON fields
  │    │    │    ├─ 0.08–0.20 (0.80–0.91) → LLM tiebreaker → MERGE if same=true
  │    │    │    └─ dist > 0.20 (< 0.80) → CREATE new concept, embed, insert
  │    │    └─ return canonical concept_id
  │    └─ UPDATE concept_sources with canonical concept_ids
  │
  └─ _stage_edges(source_id)   ← replaces _stage_edges_stub
       │
       ├─ CO-OCCURRENCE: enumerate pairs from same chunk → UPSERT edges (weight++)
       ├─ PREREQUISITE: batch all course concepts (≤50) → LLM → INSERT edges
       └─ BFS DEPTH: load all concepts + prerequisite edges → Python BFS → UPDATE concepts.depth
```

### Recommended Project Structure
```
backend/app/pipeline/
├── pipeline.py        # Orchestrator — calls stage functions, error handling
├── parsers.py         # Existing — parse_pdf, parse_url, parse_image, parse_text
├── extractor.py       # NEW: _stage_extract(source_id) — LLM extraction + cache
├── resolver.py        # NEW: _stage_resolve(source_id) — cosine resolution + tiebreaker
└── edges.py           # NEW: _stage_edges(source_id) — co-occurrence + prerequisite + BFS
```

### Pattern 1: Anthropic tool_use for Structured Extraction

The `parsers.py:parse_image` function establishes the `AsyncAnthropic` pattern. Extend it:

```python
# Source: Context7 /anthropics/anthropic-sdk-python + parsers.py existing pattern
import anthropic

client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

EXTRACT_TOOL = {
    "name": "extract_concepts",
    "description": (
        "Extract 0–6 specific academic concepts from this text chunk. "
        "Do NOT extract generic study skills (e.g., 'Problem Solving', 'Note Taking'), "
        "acronym-only concepts (e.g., 'NN', 'ML', 'GD'), procedural steps, or "
        "course logistics. Extract only concrete technical concepts a student would "
        "need to understand and be tested on."
    ),
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["concepts"],
        "properties": {
            "concepts": {
                "type": "array",
                "maxItems": 6,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["title", "definition", "key_points", "gotchas", "examples", "related_concepts"],
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Title Case, singular, canonical name. E.g., 'Gradient Descent' not 'GD' or 'gradient descent optimization procedure'"
                        },
                        "definition": {"type": "string", "description": "1–3 sentence definition"},
                        "key_points": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "3–5 bullet points a student must know"
                        },
                        "gotchas": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Common mistakes or misconceptions about this concept"
                        },
                        "examples": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Concrete examples or applications"
                        },
                        "related_concepts": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Titles of related concepts mentioned in the chunk"
                        }
                    }
                }
            }
        }
    }
}

# Call pattern (async)
message = await client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,
    tools=[EXTRACT_TOOL],
    tool_choice={"type": "tool", "name": "extract_concepts"},  # force tool use
    messages=[{
        "role": "user",
        "content": f"Extract concepts from this lecture chunk:\n\n{chunk_text}"
    }]
)

# Extract tool_use result
if message.stop_reason == "tool_use":
    tool_block = next(b for b in message.content if b.type == "tool_use")
    concepts = tool_block.input["concepts"]  # already parsed dict — no JSON.loads needed
else:
    # Retry once: stop_reason was "end_turn" without tool call
    concepts = []
```

[VERIFIED: Context7 /anthropics/anthropic-sdk-python — tool_use pattern, force_tool_choice, stop_reason check]
[VERIFIED: backend/app/pipeline/parsers.py — AsyncAnthropic pattern, model="claude-sonnet-4-6"]

**Key insight:** `tool_choice={"type": "tool", "name": "extract_concepts"}` forces Claude to always call the tool. `tool_block.input` is already a Python dict — no JSON parsing needed. `additionalProperties: false` in the schema prevents extra keys.

### Pattern 2: ExtractionCache Lookup + Upsert

```python
# Source: backend/alembic/versions/0001_initial.py — unique index on (chunk_hash, model_version)
import hashlib
from sqlalchemy.dialects.postgresql import insert as pg_insert

MODEL_VERSION = "claude-sonnet-4-6:v1"  # bump string when prompt changes

chunk_hash = hashlib.sha256(chunk.text.encode()).hexdigest()

async with AsyncSessionLocal() as session:
    result = await session.execute(
        sa.select(ExtractionCache).where(
            ExtractionCache.chunk_hash == chunk_hash,
            ExtractionCache.model_version == MODEL_VERSION,
        )
    )
    cached = result.scalar_one_or_none()
    if cached:
        return cached.extracted_concepts  # list of concept dicts

    # --- LLM call here ---
    concepts = await _call_extract_llm(chunk.text)

    # Upsert on (chunk_hash, model_version) conflict
    stmt = pg_insert(ExtractionCache).values(
        chunk_hash=chunk_hash,
        model_version=MODEL_VERSION,
        extracted_concepts=concepts,
    ).on_conflict_do_update(
        index_elements=["chunk_hash", "model_version"],
        set_={"extracted_concepts": concepts},
    )
    await session.execute(stmt)
    await session.commit()
    return concepts
```

[VERIFIED: backend/alembic/versions/0001_initial.py — `ix_extraction_cache_chunk_model` unique index on (chunk_hash, model_version)]
[VERIFIED: backend/app/models/models.py — ExtractionCache model fields]

### Pattern 3: asyncio.Semaphore for Max-5 Parallel Chunks

```python
# Source: Python stdlib asyncio — standard semaphore pattern
import asyncio

async def _stage_extract(source_id: int) -> None:
    sem = asyncio.Semaphore(5)

    async def extract_one(chunk):
        async with sem:
            return await _extract_chunk_with_cache(chunk)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            sa.select(Chunk).where(Chunk.source_id == source_id)
        )
        chunks = result.scalars().all()

    # Run at most 5 simultaneously
    results = await asyncio.gather(*[extract_one(c) for c in chunks])
    # results is a list of lists of concept dicts
```

[ASSUMED] — asyncio.Semaphore is stdlib; pattern is standard Python concurrency idiom.

### Pattern 4: pgvector Cosine Resolution Query

```python
# Source: Context7 /pgvector/pgvector-python — .cosine_distance() ORM method
# cosine_distance = 1 - cosine_similarity
# similarity ≥ 0.92  →  distance ≤ 0.08
# similarity ≥ 0.80  →  distance ≤ 0.20

async with AsyncSessionLocal() as session:
    # Embed new concept's title + definition for comparison
    embed_resp = await openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=[f"{title} {definition}"],
    )
    vec = embed_resp.data[0].embedding

    # MUST include course_id filter — RESOLVE-01
    rows = await session.execute(
        sa.select(
            Concept,
            Concept.embedding.cosine_distance(vec).label("dist")
        )
        .where(
            Concept.course_id == course_id,
            Concept.embedding.isnot(None),
        )
        .order_by("dist")
        .limit(1)
    )
    row = rows.first()

    if row is None or row.dist > 0.20:
        # RESOLVE-04: < 0.80 similarity — create new concept
        ...
    elif row.dist <= 0.08:
        # RESOLVE-02: ≥ 0.92 similarity — auto-merge
        ...
    else:
        # RESOLVE-03: 0.80–0.91 — LLM tiebreaker
        ...
```

[VERIFIED: Context7 /pgvector/pgvector-python — `.cosine_distance()` method, `.label()`, `.order_by()`, `.where()` filter]
[VERIFIED: backend/alembic/versions/0001_initial.py — HNSW index on concepts.embedding with `vector_cosine_ops`]

**Critical note:** The HNSW index uses `vector_cosine_ops`, which matches the `.cosine_distance()` method. Using `.l2_distance()` here would NOT use the index.

### Pattern 5: Merge Strategy for RESOLVE-02

```python
# Merge: extend JSON list fields, keep existing title/definition
# Source: [ASSUMED] — standard list-merge strategy for JSON arrays
async with AsyncSessionLocal() as session:
    existing = await session.get(Concept, existing_concept_id)

    # Extend list fields without duplicates
    merged_key_points = list(dict.fromkeys(
        (existing.key_points or []) + new_concept_data["key_points"]
    ))
    merged_gotchas = list(dict.fromkeys(
        (existing.gotchas or []) + new_concept_data["gotchas"]
    ))
    merged_examples = list(dict.fromkeys(
        (existing.examples or []) + new_concept_data["examples"]
    ))

    existing.key_points = merged_key_points[:10]   # cap at 10 items
    existing.gotchas = merged_gotchas[:5]
    existing.examples = merged_examples[:5]

    # Add ConceptSource link
    session.add(ConceptSource(
        concept_id=existing_concept_id,
        source_id=source_id,
        student_questions=None,  # or questions if chat_log source
    ))
    await session.commit()
```

### Pattern 6: LLM Tiebreaker (RESOLVE-03)

```python
# Source: same tool_use pattern; smaller schema
TIEBREAKER_TOOL = {
    "name": "decide_merge",
    "description": "Decide if two concept descriptions refer to the same academic concept.",
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["same", "reason"],
        "properties": {
            "same": {"type": "boolean"},
            "reason": {"type": "string", "description": "1 sentence explanation"}
        }
    }
}

message = await client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=256,
    tools=[TIEBREAKER_TOOL],
    tool_choice={"type": "tool", "name": "decide_merge"},
    messages=[{
        "role": "user",
        "content": (
            f"Concept A: {existing_title} — {existing_definition}\n"
            f"Concept B: {new_title} — {new_definition}\n"
            f"Are these the same concept? Both are from the same course."
        )
    }]
)
tool_block = next(b for b in message.content if b.type == "tool_use")
result = tool_block.input  # {"same": bool, "reason": str}
```

### Pattern 7: EDGE-01 Design — Course→Concept "Contains" Edges

**Critical design constraint:** The `edges` table has `from_id` and `to_id` both as FK to `concepts.id`. [VERIFIED: backend/alembic/versions/0001_initial.py]

This means "course → concept" contains edges CANNOT be stored in the `edges` table as written. Two valid interpretations:

**Option A (recommended for Phase 3):** "Contains" edges exist logically via the `concept.course_id` FK — every concept with `course_id = X` is implicitly "contained" by that course. The `edges` table stores only concept-to-concept relationships (co-occurrence, prerequisite, related). The BFS for EDGE-04 uses `course_id` FK as the "root" rather than explicit edge rows.

**Option B:** Add a Concept row representing the "course root" node, then all other concepts get `contains` edges from it. This would require an Alembic migration or special handling. Not recommended — adds complexity and contradicts the existing schema.

**Decision for Phase 3:** Use Option A. For EDGE-04 BFS depth:
- Concepts at `depth=1`: all concepts in the course that have NO prerequisite edges pointing to them from within the course (i.e., "direct" course concepts).
- Concepts at `depth=N`: have N levels of prerequisites before them.
- BFS starting set = all concepts with `course_id = X`, treated as distance=1 from virtual course root.

For the graph API (Phase 5), the `course` node will be synthesized from the `courses` table row, with synthetic `contains` edges constructed from `concept.course_id`. No edge rows are needed.

[ASSUMED] — interpretation of EDGE-01 given the edges table FK constraint. This is the design that requires zero schema changes and is consistent with the existing models.

### Pattern 8: BFS Depth Computation (EDGE-04)

```python
# Source: Python stdlib collections — standard BFS pattern
import collections

async def _compute_depths(course_id: int) -> None:
    async with AsyncSessionLocal() as session:
        # Load all concept IDs for this course
        concepts_result = await session.execute(
            sa.select(Concept.id).where(Concept.course_id == course_id)
        )
        concept_ids = {row.id for row in concepts_result}

        # Load prerequisite edges within this course
        edges_result = await session.execute(
            sa.select(Edge.from_id, Edge.to_id)
            .where(
                Edge.edge_type == "prerequisite",
                Edge.from_id.in_(concept_ids),
                Edge.to_id.in_(concept_ids),
            )
        )
        # Build adjacency: prereq_of[A] = {B, C} means A must be learned before B and C
        # For BFS depth: child.depth = parent.depth + 1
        children: dict[int, set[int]] = collections.defaultdict(set)
        has_prereq: set[int] = set()
        for from_id, to_id in edges_result:
            children[from_id].add(to_id)
            has_prereq.add(to_id)

        # BFS from "roots" = concepts with no prerequisites (depth=1 in course)
        depths: dict[int, int] = {}
        roots = concept_ids - has_prereq  # no incoming prerequisite edges
        queue = collections.deque()
        for root_id in roots:
            depths[root_id] = 1
            queue.append(root_id)

        while queue:
            node_id = queue.popleft()
            for child_id in children[node_id]:
                if child_id not in depths:
                    depths[child_id] = depths[node_id] + 1
                    queue.append(child_id)

        # Assign depth=1 to any concepts not reachable (isolated)
        for cid in concept_ids:
            if cid not in depths:
                depths[cid] = 1

        # Bulk update
        for cid, depth in depths.items():
            await session.execute(
                sa.update(Concept)
                .where(Concept.id == cid)
                .values(depth=depth)
            )
        await session.commit()
```

[ASSUMED] — BFS algorithm; standard Python idiom verified against collections.deque API.

### Pattern 9: Prerequisite Edge Inference by LLM (EDGE-03)

```python
PREREQ_TOOL = {
    "name": "infer_prerequisites",
    "description": (
        "Given a list of academic concepts from the same course, identify prerequisite "
        "relationships: concept A is a prerequisite of concept B if a student must understand "
        "A before they can understand B. Return at most 30 pairs."
    ),
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["prerequisites"],
        "properties": {
            "prerequisites": {
                "type": "array",
                "maxItems": 30,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["prerequisite", "concept"],
                    "properties": {
                        "prerequisite": {"type": "string", "description": "Title of the prerequisite concept"},
                        "concept": {"type": "string", "description": "Title of the concept that requires it"}
                    }
                }
            }
        }
    }
}

# Batch: max 50 concepts per call
concept_list = "\n".join(f"- {c.title}" for c in concepts[:50])
message = await client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=2048,
    tools=[PREREQ_TOOL],
    tool_choice={"type": "tool", "name": "infer_prerequisites"},
    messages=[{
        "role": "user",
        "content": f"These are all the concepts in a single course:\n{concept_list}\n\nInfer prerequisite relationships."
    }]
)
```

### Pattern 10: Co-occurrence Edge Upsert (EDGE-02)

```python
# For each chunk, enumerate all pairs of concept_ids extracted from that chunk
# Then UPSERT: increment weight on conflict
from itertools import combinations
from sqlalchemy.dialects.postgresql import insert as pg_insert

for chunk_id, concept_ids in chunk_concept_map.items():
    for a, b in combinations(sorted(concept_ids), 2):
        stmt = pg_insert(Edge).values(
            from_id=a,
            to_id=b,
            edge_type="co_occurrence",
            weight=1.0,
        ).on_conflict_do_update(
            # No unique index exists yet — need to check for existing edge first
            # OR use a raw SQL approach
            # [ASSUMED] — need to handle this via SELECT + UPDATE or add unique constraint
            index_elements=["from_id", "to_id", "edge_type"],
            set_={"weight": Edge.weight + 1}
        )
        await session.execute(stmt)
```

**Important note:** The `edges` table has NO unique index on `(from_id, to_id, edge_type)` in the current migration. [VERIFIED: backend/alembic/versions/0001_initial.py] This means the `on_conflict_do_update` pattern requires either:
1. A Phase 3 Alembic migration adding `UNIQUE(from_id, to_id, edge_type)` — but the phase description says no migration needed.
2. A SELECT-then-UPDATE pattern within the same session.

**Recommended approach:** Use SELECT-then-UPDATE (check for existing edge, then increment weight or insert). This avoids needing a new migration but is slightly more code.

### Anti-Patterns to Avoid

- **Cross-course concept merging:** Never query concepts without `WHERE course_id = :course_id`. Single most-critical correctness invariant.
- **Parsing tool_block.input as JSON string:** `tool_block.input` is already a Python dict when using the Messages API. Calling `json.loads(tool_block.input)` will fail with a TypeError.
- **Single session across extract+resolve:** Opening one session for all 8 stages exhausts the connection pool. Each of the three new stages must open its own `AsyncSessionLocal` sessions.
- **Using ivfflat index for resolution:** The concepts HNSW index uses `vector_cosine_ops`. Cosine queries will use it automatically. Do NOT use L2 distance — it won't use the index.
- **Embedding concept titles only (without definition):** Short titles like "Gradient Descent" are near-synonyms in embedding space but mean different things in different contexts. Always embed `f"{title} {definition}"` for resolution.
- **Not truncating model_version when prompt changes:** After every extraction prompt edit during development, run `TRUNCATE extraction_cache;` — the cache key includes `model_version` but callers must remember to bump the version string constant.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON schema enforcement | Custom validation logic | `additionalProperties: false` in tool schema | Claude honors it; custom validation misses edge cases |
| Approximate nearest neighbor search | Manual cosine scan of all concepts | pgvector HNSW index via `.cosine_distance()` | HNSW is O(log n) with 99%+ recall vs. O(n) exact scan |
| Structured output parsing | Regex on `message.content[0].text` | tool_use + `tool_block.input` | Free-text parsing breaks when Claude adds commentary |
| Async rate limiting | `asyncio.sleep` between calls | `asyncio.Semaphore(5)` | Semaphore is cleaner and doesn't over-sleep |

**Key insight:** The biggest risk in extraction is getting back free-text JSON that fails silently. Tool_use with `tool_choice={"type": "tool", "name": "..."}` is the correct solution — it forces Claude to always call the tool and return structured data.

---

## Common Pitfalls

### Pitfall 1: Cross-Course Concept Merging
**What goes wrong:** A concept "Gradient Descent" from CS229 gets merged with a concept from a different course (e.g., CS231n), producing incorrect cross-course contamination.
**Why it happens:** Forgetting `.where(Concept.course_id == course_id)` in the cosine query.
**How to avoid:** Always write `.where(Concept.course_id == course_id, Concept.embedding.isnot(None))` as a pair.
**Warning signs:** Two different courses sharing concept node IDs; queries returning concepts from unexpected courses.

### Pitfall 2: extraction_cache Never Hits
**What goes wrong:** Every pipeline run makes fresh LLM calls even on identical chunks, wasting money and time.
**Why it happens:** `model_version` string mismatch (e.g., spaces, version format inconsistency) or prompt was edited without `TRUNCATE extraction_cache`.
**How to avoid:** Define `MODEL_VERSION = "claude-sonnet-4-6:v1"` as a module-level constant. After any prompt edit, bump the `:v1` suffix.
**Warning signs:** `extraction_cache` table stays empty; every run costs similar tokens.

### Pitfall 3: tool_use Not Forced
**What goes wrong:** Claude returns `stop_reason="end_turn"` with a text response instead of calling the tool, crashing `next(b for b in message.content if b.type == "tool_use")` with a `StopIteration`.
**Why it happens:** `tool_choice` omitted from the API call; Claude may choose to not use the tool on easy/short inputs.
**How to avoid:** Always pass `tool_choice={"type": "tool", "name": "extract_concepts"}`.
**Warning signs:** `StopIteration` in extractor; `message.stop_reason == "end_turn"` in logs.

### Pitfall 4: Embedding Mismatch in Resolution
**What goes wrong:** Cosine similarity query always returns distance > 0.20 even for clearly identical concepts, so no merging happens.
**Why it happens:** New concept embedded with just the title ("Gradient Descent") while existing concepts were embedded with title + definition. The embedding distributions differ.
**How to avoid:** Standardize on `f"{title}. {definition}"` for ALL concept embeddings throughout the pipeline.
**Warning signs:** Every resolution call creates a new concept; concept count grows unboundedly after dropping the same PDF twice.

### Pitfall 5: Prerequisite LLM Call With No Course Context
**What goes wrong:** LLM infers prerequisites between unrelated concepts because the prompt doesn't convey that all concepts are from the same course.
**Why it happens:** Prompt says "infer prerequisites" but doesn't specify the domain.
**How to avoid:** Include course title in the prompt: `"These concepts are all from a single course: {course.title}. Infer prerequisite relationships within this course only."`
**Warning signs:** Prerequisites like "Mathematics" → "Gradient Descent" that don't make sense in context.

### Pitfall 6: Co-occurrence Weight Not Incrementing
**What goes wrong:** Every pipeline run on the same source creates new co-occurrence edge rows instead of incrementing weights.
**Why it happens:** No unique constraint on `(from_id, to_id, edge_type)` → `ON CONFLICT DO UPDATE` fails silently or inserts duplicates.
**How to avoid:** Use SELECT-then-UPDATE pattern. Or add a unique index (Phase 3 may need a migration for this).
**Warning signs:** Many co-occurrence edges with weight=1.0; no edges with weight > 1.

### Pitfall 7: BFS Doesn't Cover All Concepts
**What goes wrong:** Some concepts get `depth=NULL` after BFS because they form a cycle or are isolated.
**Why it happens:** BFS only traverses reachable nodes from roots; isolated concepts (no edges) are unreachable.
**How to avoid:** After BFS, assign `depth=1` to any concept with `depth IS NULL`. See Pattern 8 above.
**Warning signs:** Success criterion 4 fails — some concepts still have null depth.

---

## Code Examples

### Complete Extraction Cache Check + LLM + Upsert

```python
# Source: backend/app/pipeline/pipeline.py (sha256 pattern), 
#         backend/alembic/versions/0001_initial.py (unique index pattern)
import hashlib
from sqlalchemy.dialects.postgresql import insert as pg_insert

MODEL_VERSION = "claude-sonnet-4-6:v1"

async def _extract_chunk_with_cache(
    chunk: Chunk,
    source_type: str,
    anthropic_client: anthropic.AsyncAnthropic,
    openai_client: AsyncOpenAI,
) -> list[dict]:
    chunk_hash = hashlib.sha256(chunk.text.encode()).hexdigest()

    async with AsyncSessionLocal() as session:
        cached = await session.scalar(
            sa.select(ExtractionCache).where(
                ExtractionCache.chunk_hash == chunk_hash,
                ExtractionCache.model_version == MODEL_VERSION,
            )
        )
        if cached:
            return cached.extracted_concepts or []

    # LLM call (outside session — pure I/O)
    try:
        message = await anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            tools=[EXTRACT_TOOL],
            tool_choice={"type": "tool", "name": "extract_concepts"},
            messages=[{
                "role": "user",
                "content": f"Extract concepts from this chunk:\n\n{chunk.text[:8000]}"
            }]
        )
        if message.stop_reason == "tool_use":
            tool_block = next(b for b in message.content if b.type == "tool_use")
            concepts = tool_block.input.get("concepts", [])
        else:
            concepts = []
    except Exception:
        # Retry once
        try:
            # ... same call again ...
            pass
        except Exception:
            concepts = []

    # Handle chat_log student questions (EXTRACT-03)
    student_questions = None
    if source_type == "chat_log":
        # Extract verbatim questions from chunk text — simple regex or second LLM pass
        student_questions = _extract_questions(chunk.text)

    # Cache result
    async with AsyncSessionLocal() as session:
        stmt = pg_insert(ExtractionCache).values(
            chunk_hash=chunk_hash,
            model_version=MODEL_VERSION,
            extracted_concepts=concepts,
        ).on_conflict_do_update(
            index_elements=["chunk_hash", "model_version"],
            set_={"extracted_concepts": concepts},
        )
        await session.execute(stmt)
        await session.commit()

    return concepts
```

### Full Resolution Query

```python
# Source: Context7 /pgvector/pgvector-python, backend/app/models/models.py
async def _resolve_concept(
    title: str,
    definition: str,
    course_id: int,
    source_id: int,
    source_type: str,
    openai_client: AsyncOpenAI,
    anthropic_client: anthropic.AsyncAnthropic,
) -> int:  # returns canonical concept_id
    """Returns the canonical concept_id (existing or newly created)."""
    embed_text = f"{title}. {definition}"
    embed_resp = await openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=[embed_text],
    )
    vec = embed_resp.data[0].embedding

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            sa.select(
                Concept.id,
                Concept.title,
                Concept.definition,
                Concept.key_points,
                Concept.gotchas,
                Concept.examples,
                Concept.embedding.cosine_distance(vec).label("dist"),
            )
            .where(
                Concept.course_id == course_id,    # RESOLVE-01: MUST have this
                Concept.embedding.isnot(None),
            )
            .order_by("dist")
            .limit(1)
        )).first()

        if rows is None or rows.dist > 0.20:
            # RESOLVE-04: new concept
            concept = Concept(
                course_id=course_id,
                title=title,
                definition=definition,
                # ... other fields ...
                embedding=vec,
            )
            session.add(concept)
            await session.flush()  # get concept.id
            session.add(ConceptSource(concept_id=concept.id, source_id=source_id))
            await session.commit()
            return concept.id

        elif rows.dist <= 0.08:
            # RESOLVE-02: auto-merge
            # ... extend JSON fields, add ConceptSource ...
            await session.commit()
            return rows.id

        else:
            # RESOLVE-03: LLM tiebreaker
            tiebreaker = await _llm_tiebreaker(title, definition, rows.title, rows.definition, anthropic_client)
            if tiebreaker["same"]:
                # merge
                await session.commit()
                return rows.id
            else:
                # create new
                # ...
                await session.commit()
                return new_concept.id
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Parsing free-text JSON from LLM | `tool_use` with `additionalProperties: false` | Anthropic added tool_use in 2023 | Eliminates JSON parse failures; required by EXTRACT-04 |
| Exact cosine scan (O(n)) | HNSW approximate ANN (O(log n)) | pgvector 0.5.0+ | Already using — hnsw index created in 0001_initial.py |
| `.reactflow` package | `@xyflow/react` | React Flow v12 | Frontend only; irrelevant to Phase 3 |
| `tool_choice={"type": "any"}` | `tool_choice={"type": "tool", "name": "..."}` | Anthropic API | Force specific tool prevents fallback to text response |

**Deprecated/outdated:**
- `@app.on_event("startup")` decorator: replaced by `lifespan` context manager (already done in main.py).
- `reactflow` npm package: deprecated alias — use `@xyflow/react` (Phase 6 concern only).

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | BFS for EDGE-04 starts from "all concepts with no incoming prerequisite edges" as depth=1 from virtual course root; depth=0 belongs to the course node in the graph API, not any concept | Pattern 8, EDGE-01 Design | If depth=0 is expected on a specific concept, BFS assignments will be off by one; success criterion 4 may fail |
| A2 | "Contains" edges (EDGE-01) are implicitly represented by `concept.course_id` FK rather than rows in the `edges` table, because `edges.from_id` FK points only to `concepts.id` | EDGE-01 Design | If a future migration adds a polymorphic `from_table` column, this assumption is wrong — but for Phase 3 with no new migrations, it holds |
| A3 | Co-occurrence weight increment should use SELECT-then-UPDATE pattern (not ON CONFLICT) because no unique index exists on `(from_id, to_id, edge_type)` | Pattern 10 | If a unique index is added in Phase 3 migration, ON CONFLICT is cleaner — but the phase description explicitly states no new migration needed |
| A4 | `asyncio.Semaphore` semaphore pattern for max-5 parallel chunks is thread-safe and won't cause session pool exhaustion when combined with session-per-stage pattern | Pattern 3 | If pool_size=10 with max_overflow=5 is insufficient for 5 concurrent sessions, chunk extraction may fail with pool timeout; may need to reduce semaphore to 3 |
| A5 | `tool_block.input["concepts"]` returns a Python dict list directly (not a JSON string) when using `client.messages.create` with the Python SDK | Pattern 1 | SDK version regression could break this; test with `type(tool_block.input)` assertion in tests |

---

## Open Questions

1. **Co-occurrence unique constraint**
   - What we know: No unique index on `(from_id, to_id, edge_type)` in 0001_initial.py.
   - What's unclear: Should Phase 3 add a migration `0003_edge_unique.py` to enable ON CONFLICT DO UPDATE? Or is SELECT-then-UPDATE sufficient?
   - Recommendation: Use SELECT-then-UPDATE in Phase 3 (no migration). If Phase 3 testing reveals performance issues, add migration in Phase 5 when graph queries are built.

2. **Concept embedding strategy during extraction vs resolution**
   - What we know: During extraction, a concept dict is returned by LLM. During resolution, we need to embed the concept.
   - What's unclear: Should the concept be embedded immediately during `_stage_extract` and the vector stored in a temp dict, or should embedding happen in `_stage_resolve` for each candidate?
   - Recommendation: Embed in `_stage_resolve` just-in-time. This keeps extraction pure (LLM only) and avoids embedding concepts that will be merged away.

3. **EXTRACT-03: How to extract student questions from chat_log chunks**
   - What we know: EXTRACT-03 says "extracted verbatim ONLY for chat_log source types."
   - What's unclear: Should questions be extracted by regex (find lines ending in `?`) or by a separate LLM tool call?
   - Recommendation: Regex approach first (`re.findall(r'[^.!?]*\?', chunk.text)`) — low complexity, sufficient for demo. Add to `ConceptSource.student_questions` JSON array.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Docker / PostgreSQL+pgvector | All DB queries | ✓ | pgvector/pgvector:pg16, running healthy | — |
| Python 3 | Backend execution | ✓ | 3.14.3 | — |
| `anthropic` SDK | LLM extraction, tiebreaker, prereq inference | ✓ | 0.97.0 (latest on PyPI) | — |
| `openai` SDK | Concept embedding | ✓ | 2.32.0 (pinned) | — |
| `pgvector` Python | Cosine distance ORM queries | ✓ | 0.4.2 (pinned) | — |
| `ANTHROPIC_API_KEY` | All LLM calls | ✓ | Set in .env | Tests mock the client |
| `OPENAI_API_KEY` | Concept embeddings | ✓ | Set in .env | Tests mock the client |

[VERIFIED: docker ps — backend-db-1 healthy, port 5432 open]
[VERIFIED: pip3 show anthropic — 0.97.0 installed]
[VERIFIED: backend/requirements.txt — all packages pinned]

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio 0.24.0 |
| Config file | `backend/pytest.ini` (`asyncio_mode = auto`, `testpaths = tests`) |
| Quick run command | `pytest tests/test_extractor.py tests/test_resolver.py tests/test_edges.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EXTRACT-01 | 0–6 concepts returned; titles not generic | unit | `pytest tests/test_extractor.py::test_extract_concept_count -x` | ❌ Wave 0 |
| EXTRACT-02 | All 6 fields present in output | unit | `pytest tests/test_extractor.py::test_concept_fields -x` | ❌ Wave 0 |
| EXTRACT-03 | student_questions only for chat_log | unit | `pytest tests/test_extractor.py::test_chat_log_questions -x` | ❌ Wave 0 |
| EXTRACT-04 | tool_use forced, retry on failure | unit | `pytest tests/test_extractor.py::test_tool_use_retry -x` | ❌ Wave 0 |
| EXTRACT-05 | Max 5 parallel, cache checked first | unit | `pytest tests/test_extractor.py::test_cache_hit_skips_llm -x` | ❌ Wave 0 |
| RESOLVE-01 | course_id always in cosine query | unit | `pytest tests/test_resolver.py::test_course_scope -x` | ❌ Wave 0 |
| RESOLVE-02 | High cosine → merge (no new concept) | unit | `pytest tests/test_resolver.py::test_auto_merge -x` | ❌ Wave 0 |
| RESOLVE-03 | Mid cosine → LLM tiebreaker called | unit | `pytest tests/test_resolver.py::test_tiebreaker -x` | ❌ Wave 0 |
| RESOLVE-04 | Low cosine → new concept created | unit | `pytest tests/test_resolver.py::test_create_new -x` | ❌ Wave 0 |
| EDGE-01 | concept.course_id FK relationship verified | unit | `pytest tests/test_edges.py::test_contains_represented_by_fk -x` | ❌ Wave 0 |
| EDGE-02 | Co-occurrence pairs created for same-chunk concepts | unit | `pytest tests/test_edges.py::test_co_occurrence_pairs -x` | ❌ Wave 0 |
| EDGE-03 | Prerequisite edges created from LLM output | unit | `pytest tests/test_edges.py::test_prerequisite_inference -x` | ❌ Wave 0 |
| EDGE-04 | BFS assigns non-null depth to all concepts | unit | `pytest tests/test_edges.py::test_bfs_depth -x` | ❌ Wave 0 |

### Mocking Strategy (ALL LLM tests use mocks)

```python
# Source: backend/tests/test_pipeline.py — established mock pattern for this project
from unittest.mock import AsyncMock, MagicMock, patch

def _make_tool_response(concepts: list[dict]):
    """Build a mock Anthropic message with tool_use content."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.input = {"concepts": concepts}
    message = MagicMock()
    message.stop_reason = "tool_use"
    message.content = [tool_block]
    return message

@pytest.mark.asyncio
async def test_cache_hit_skips_llm():
    mock_anthropic = AsyncMock()
    mock_openai = AsyncMock()
    # Simulate cache hit — verify LLM client is never called
    with patch("app.pipeline.extractor.AsyncSessionLocal") as mock_session:
        # ... mock returns ExtractionCache row ...
        await _extract_chunk_with_cache(chunk, "pdf", mock_anthropic, mock_openai)
    mock_anthropic.messages.create.assert_not_called()
```

### Sampling Rate
- **Per task commit:** `pytest tests/test_extractor.py tests/test_resolver.py tests/test_edges.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_extractor.py` — covers EXTRACT-01 through EXTRACT-05
- [ ] `tests/test_resolver.py` — covers RESOLVE-01 through RESOLVE-04
- [ ] `tests/test_edges.py` — covers EDGE-01 through EDGE-04
- [ ] `backend/app/pipeline/extractor.py` — module stub (importable, functions defined but `pass`)
- [ ] `backend/app/pipeline/resolver.py` — module stub
- [ ] `backend/app/pipeline/edges.py` — module stub

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A — user_id=1 hardcoded, no auth |
| V3 Session Management | no | N/A — no web sessions |
| V4 Access Control | no | N/A — single user |
| V5 Input Validation | yes | Chunk text truncated to 8000 chars before LLM send; tool schema rejects extra fields |
| V6 Cryptography | no | SHA-256 used for chunk_hash (integrity, not confidentiality) — not hand-rolled |

### Known Threat Patterns for LLM Pipeline

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection via malicious PDF content | Tampering | Tool_use schema rejects non-schema fields; chunk text is user-supplied but Claude is the parser, not executor |
| SSRF via URL sources (already addressed) | Elevation of Privilege | POST /ingest SSRF protection from Phase 2 (private IP blocklist) |
| LLM response with oversized concepts array | Denial of Service | `maxItems: 6` in JSON schema; `[:10]` cap on merged key_points/gotchas |

---

## Sources

### Primary (HIGH confidence)
- Context7 `/anthropics/anthropic-sdk-python` — tool_use pattern, tool_choice forcing, stop_reason handling, tool_block.input dict access
- Context7 `/pgvector/pgvector-python` — `.cosine_distance()` ORM method, `.label()`, `.where()` filter, HNSW index creation
- `backend/app/pipeline/parsers.py` — `AsyncAnthropic` async client pattern, `model="claude-sonnet-4-6"` confirmed
- `backend/app/pipeline/pipeline.py` — session-per-stage pattern, `AsyncSessionLocal`, stub function names to replace
- `backend/alembic/versions/0001_initial.py` — confirmed all Phase 3 target tables exist; confirmed HNSW index on concepts.embedding with `vector_cosine_ops`; confirmed unique index on `(chunk_hash, model_version)`; confirmed NO unique index on `(from_id, to_id, edge_type)` in edges table
- `backend/app/models/models.py` — all ORM field names confirmed: `ExtractionCache.extracted_concepts`, `Edge.from_id/to_id/edge_type/weight`, `Concept.depth`, `ConceptSource.student_questions`
- `backend/requirements.txt` — all package versions verified: anthropic==0.97.0 (matches PyPI latest)

### Secondary (MEDIUM confidence)
- Python `asyncio.Semaphore` documentation — standard semaphore pattern for concurrency limiting
- `backend/tests/test_pipeline.py` — AsyncMock/MagicMock pattern established; `asyncio_mode = auto` confirmed in pytest.ini

### Tertiary (LOW confidence)
- Merge strategy (dict.fromkeys dedup + cap at 10) — [ASSUMED] based on reasonable list-merge heuristic
- Student question extraction via regex — [ASSUMED] as simpler alternative to LLM for EXTRACT-03

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified in requirements.txt, versions confirmed on PyPI
- Architecture patterns: HIGH — tool_use verified via Context7; pgvector verified via Context7; session-per-stage and AsyncAnthropic verified from existing code
- Edge design (EDGE-01 contains edges): MEDIUM — design interpretation derived from schema constraints; ambiguity flagged as assumption A1/A2
- BFS depth algorithm: HIGH — standard Python pattern; flagged as ASSUMED for traceability
- Pitfalls: HIGH — verified against actual schema constraints and existing code patterns

**Research date:** 2026-04-25
**Valid until:** 2026-05-25 (stable APIs; anthropic SDK minor versions may change)

---

## RESEARCH COMPLETE
