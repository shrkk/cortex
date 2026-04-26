# Phase 3: Extraction, Resolution & Edges — Pattern Map

**Mapped:** 2026-04-25
**Files analyzed:** 7 (3 new modules, 1 modified orchestrator, 3 new test files)
**Analogs found:** 7 / 7

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/app/pipeline/extractor.py` | service | batch + request-response | `backend/app/pipeline/parsers.py` (lines 104–153) | exact — AsyncAnthropic tool_use, async, no DB |
| `backend/app/pipeline/resolver.py` | service | CRUD + request-response | `backend/app/pipeline/pipeline.py` (lines 161–188) | role-match — same session-per-stage + OpenAI embed pattern |
| `backend/app/pipeline/edges.py` | service | CRUD + batch | `backend/app/pipeline/pipeline.py` (lines 161–188) | role-match — same session-per-stage, SA queries |
| `backend/app/pipeline/pipeline.py` | service (orchestrator) | request-response | self — existing stub functions (lines 195–211) | exact — stubs being replaced with real calls |
| `backend/tests/test_extraction.py` | test | — | `backend/tests/test_pipeline.py` | exact — same AsyncMock/MagicMock structure |
| `backend/tests/test_resolution.py` | test | — | `backend/tests/test_pipeline.py` | exact — same mock pattern |
| `backend/tests/test_edges.py` | test | — | `backend/tests/test_pipeline.py` | exact — same mock pattern |

---

## Pattern Assignments

### `backend/app/pipeline/extractor.py` (service, batch + request-response)

**Analog:** `backend/app/pipeline/parsers.py`

**Imports pattern** (parsers.py lines 1–16, plus extractor additions):
```python
from __future__ import annotations

import asyncio
import hashlib
import re

import anthropic
import sqlalchemy as sa
from openai import AsyncOpenAI
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.models import Chunk, Concept, ConceptSource, ExtractionCache, Source
```

**AsyncAnthropic client instantiation pattern** (parsers.py lines 112–113):
```python
# Lazy import inside function body — only load when actually processing
import anthropic
client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
```

**Core tool_use call pattern** (parsers.py lines 122–153 adapted to tool_use):
```python
# parsers.py lines 122–151 — establishes the client.messages.create call shape
message = await client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,
    messages=[{"role": "user", "content": [...]}],
)
ocr_text = message.content[0].text if message.content else ""
```

**Adapt to tool_use** (force tool, extract dict without json.loads):
```python
# tool_choice forces Claude to always call the tool (never end_turn text fallback)
message = await client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,
    tools=[EXTRACT_TOOL],
    tool_choice={"type": "tool", "name": "extract_concepts"},
    messages=[{"role": "user", "content": f"Extract concepts from this chunk:\n\n{chunk.text[:8000]}"}],
)
if message.stop_reason == "tool_use":
    tool_block = next(b for b in message.content if b.type == "tool_use")
    concepts = tool_block.input.get("concepts", [])  # already a Python dict — no json.loads
else:
    concepts = []  # retry once on end_turn fallback
```

**AsyncSessionLocal session-per-stage pattern** (pipeline.py lines 50–55):
```python
async def _stage_set_processing(source_id: int) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            sa.update(Source).where(Source.id == source_id).values(status="processing")
        )
        await session.commit()
```

**SHA-256 chunk_hash pattern** (pipeline.py lines 72–77 — content_hash variant):
```python
# pipeline.py uses same hashlib.sha256 approach for content_hash
content_hash = hashlib.sha256(content_to_hash).hexdigest()
# Extractor adapts this for chunk_hash:
chunk_hash = hashlib.sha256(chunk.text.encode()).hexdigest()
```

**ExtractionCache upsert** (pg_insert + on_conflict_do_update):
```python
from sqlalchemy.dialects.postgresql import insert as pg_insert

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
```

**asyncio.Semaphore pattern for max-5 parallel chunks** (stdlib, consistent with pipeline.py gather usage):
```python
sem = asyncio.Semaphore(5)

async def extract_one(chunk):
    async with sem:
        return await _extract_chunk_with_cache(chunk, source_type, client)

results = await asyncio.gather(*[extract_one(c) for c in chunks])
```

**Model-level constant** (module-level, matches naming in pipeline.py):
```python
MODEL_VERSION = "claude-sonnet-4-6:v1"  # bump suffix when extraction prompt changes
```

---

### `backend/app/pipeline/resolver.py` (service, CRUD + request-response)

**Analog:** `backend/app/pipeline/pipeline.py` (`_stage_embed`, lines 161–188)

**Imports pattern** (pipeline.py lines 10–20 extended):
```python
from __future__ import annotations

import anthropic
import sqlalchemy as sa
from openai import AsyncOpenAI
from pgvector.sqlalchemy import Vector  # already on Concept.embedding column

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.models import Concept, ConceptSource, Source
```

**OpenAI embedding client instantiation** (pipeline.py lines 164–165):
```python
# pipeline.py _stage_embed — exact pattern to copy
openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
```

**OpenAI embed call** (pipeline.py lines 181–184):
```python
# pipeline.py lines 181–184 — one-text embed variant
embed_resp = await openai_client.embeddings.create(
    model="text-embedding-3-small",
    input=texts,  # resolver uses: input=[f"{title}. {definition}"]
)
vec = embed_resp.data[0].embedding
```

**pgvector cosine_distance query — CRITICAL course_id filter** (SA ORM, pgvector 0.4.2):
```python
# RESOLVE-01: MUST pair cosine_distance with .where(Concept.course_id == course_id)
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
        Concept.course_id == course_id,       # RESOLVE-01 — NEVER omit
        Concept.embedding.isnot(None),
    )
    .order_by("dist")
    .limit(1)
)).first()
```

**New Concept INSERT with session.flush()** (models.py Concept fields):
```python
# Use flush() to get concept.id before session.commit()
concept = Concept(
    course_id=course_id,
    title=title,
    definition=definition,
    key_points=key_points,
    gotchas=gotchas,
    examples=examples,
    related_concepts=related_concepts,
    embedding=vec,
)
session.add(concept)
await session.flush()   # assigns concept.id without committing
session.add(ConceptSource(concept_id=concept.id, source_id=source_id))
await session.commit()
return concept.id
```

**LLM tiebreaker tool_use** (same parsers.py pattern, smaller schema):
```python
# Same tool_choice forcing pattern as extractor — small schema variant
TIEBREAKER_TOOL = {
    "name": "decide_merge",
    "description": "Decide if two concept descriptions refer to the same academic concept.",
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["same", "reason"],
        "properties": {
            "same": {"type": "boolean"},
            "reason": {"type": "string"},
        },
    },
}
message = await anthropic_client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=256,
    tools=[TIEBREAKER_TOOL],
    tool_choice={"type": "tool", "name": "decide_merge"},
    messages=[{"role": "user", "content": prompt}],
)
tool_block = next(b for b in message.content if b.type == "tool_use")
result = tool_block.input   # {"same": bool, "reason": str} — already a dict
```

**Merge JSON list fields** (dedup via dict.fromkeys, cap):
```python
# Extend JSON arrays without duplicates; cap to prevent unbounded growth
merged_key_points = list(dict.fromkeys(
    (existing.key_points or []) + new_data["key_points"]
))[:10]
merged_gotchas = list(dict.fromkeys(
    (existing.gotchas or []) + new_data["gotchas"]
))[:5]
merged_examples = list(dict.fromkeys(
    (existing.examples or []) + new_data["examples"]
))[:5]
```

---

### `backend/app/pipeline/edges.py` (service, CRUD + batch)

**Analog:** `backend/app/pipeline/pipeline.py` (stage functions pattern)

**Imports pattern**:
```python
from __future__ import annotations

import collections
from itertools import combinations

import anthropic
import sqlalchemy as sa

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.models import Concept, Edge, Source
```

**Session-per-stage query pattern** (pipeline.py lines 167–175):
```python
# Exact session-per-stage pattern from _stage_embed
async with AsyncSessionLocal() as session:
    result = await session.execute(
        sa.select(Chunk).where(
            Chunk.source_id == source_id,
            Chunk.embedding.is_(None),
        )
    )
    chunks = result.scalars().all()
```

**Co-occurrence SELECT-then-UPDATE pattern** (no unique index on edges table):
```python
# No unique index on (from_id, to_id, edge_type) — must SELECT first, then UPDATE or INSERT
async with AsyncSessionLocal() as session:
    for a, b in combinations(sorted(concept_ids), 2):
        result = await session.execute(
            sa.select(Edge).where(
                Edge.from_id == a,
                Edge.to_id == b,
                Edge.edge_type == "co_occurrence",
            )
        )
        existing_edge = result.scalar_one_or_none()
        if existing_edge:
            existing_edge.weight += 1.0
        else:
            session.add(Edge(from_id=a, to_id=b, edge_type="co_occurrence", weight=1.0))
    await session.commit()
```

**Prerequisite LLM tool_use** (same parsers.py + extractor pattern):
```python
# Batch up to 50 concepts per call; same tool_choice forcing pattern
PREREQ_TOOL = {
    "name": "infer_prerequisites",
    "description": "...",
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
                        "prerequisite": {"type": "string"},
                        "concept": {"type": "string"},
                    },
                },
            }
        },
    },
}
```

**BFS depth via Python collections.deque** (no SQL CTE needed):
```python
# Python BFS — each concept with no incoming prerequisite edges starts at depth=1
import collections

depths: dict[int, int] = {}
queue: collections.deque = collections.deque()
# roots = concepts in course with no incoming prerequisite edges
roots = concept_ids - has_prereq
for root_id in roots:
    depths[root_id] = 1
    queue.append(root_id)

while queue:
    node_id = queue.popleft()
    for child_id in children[node_id]:
        if child_id not in depths:
            depths[child_id] = depths[node_id] + 1
            queue.append(child_id)

# Assign depth=1 to isolated concepts unreachable from any root (EDGE-04 fallback)
for cid in concept_ids:
    if cid not in depths:
        depths[cid] = 1
```

**Bulk UPDATE pattern** (pipeline.py `sa.update` style):
```python
# Matches pipeline.py _stage_set_processing style: sa.update().where().values()
for cid, depth in depths.items():
    await session.execute(
        sa.update(Concept)
        .where(Concept.id == cid)
        .values(depth=depth)
    )
await session.commit()
```

---

### `backend/app/pipeline/pipeline.py` (modified orchestrator)

**Analog:** self — existing stub functions being replaced

**Stubs to replace** (pipeline.py lines 195–211):
```python
# These three stubs get replaced with real calls to the new modules:
async def _stage_extract_stub(source_id: int) -> None:
    pass

async def _stage_resolve_stub(source_id: int) -> None:
    pass

async def _stage_edges_stub(source_id: int) -> None:
    pass
```

**Replacement import + call pattern** (matches parsers.py lazy import style, pipeline.py lines 63–64):
```python
# pipeline.py already uses lazy imports inside stage functions:
from app.pipeline.parsers import parse_pdf, parse_url, parse_image, parse_text
# New stages follow same pattern:
async def _stage_extract(source_id: int) -> None:
    from app.pipeline.extractor import run_extraction
    await run_extraction(source_id)

async def _stage_resolve(source_id: int) -> None:
    from app.pipeline.resolver import run_resolution
    await run_resolution(source_id)

async def _stage_edges(source_id: int) -> None:
    from app.pipeline.edges import run_edges
    await run_edges(source_id)
```

**run_pipeline call sites** (pipeline.py lines 34–36 — these names change):
```python
# Before (Phase 2 stubs):
await _stage_extract_stub(source_id)
await _stage_resolve_stub(source_id)
await _stage_edges_stub(source_id)

# After (Phase 3 real functions):
await _stage_extract(source_id)
await _stage_resolve(source_id)
await _stage_edges(source_id)
```

---

### `backend/tests/test_extraction.py` (test)

**Analog:** `backend/tests/test_pipeline.py`

**File header + imports pattern** (test_pipeline.py lines 1–26):
```python
"""Tests for extractor.py (Plan 03-XX).

Covers EXTRACT-01 through EXTRACT-05.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.pipeline.extractor import _extract_chunk_with_cache, _stage_extract
```

**Mock Anthropic tool_use response helper** (test_pipeline.py _make_source pattern adapted):
```python
def _make_tool_response(concepts: list[dict]) -> MagicMock:
    """Build a mock Anthropic messages.create response with tool_use content."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.input = {"concepts": concepts}
    message = MagicMock()
    message.stop_reason = "tool_use"
    message.content = [tool_block]
    return message
```

**Async test decorator pattern** (test_pipeline.py lines 73–97):
```python
# asyncio_mode = auto in pytest.ini — no need for @pytest.mark.asyncio in pytest-asyncio 0.24
# BUT test_pipeline.py uses explicit decorator, so follow same style for consistency:
@pytest.mark.asyncio
async def test_cache_hit_skips_llm():
    mock_anthropic = AsyncMock()
    # ...
    mock_anthropic.messages.create.assert_not_called()
```

**patch target naming convention** (test_pipeline.py lines 85–93):
```python
# Patch by full module path — same convention as test_pipeline.py:
# "app.pipeline.pipeline._stage_set_processing" style
with patch("app.pipeline.extractor.AsyncSessionLocal") as mock_session_cls:
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session_cls.return_value = mock_session
    # ...
```

**Session mock structure** (test_pipeline.py lines 189–217):
```python
# Standard session mock — used in all three test files:
mock_session = AsyncMock()
mock_session.__aenter__ = AsyncMock(return_value=mock_session)
mock_session.__aexit__ = AsyncMock(return_value=False)
mock_result = MagicMock()
mock_result.scalar_one_or_none.return_value = None   # cache miss
mock_result.scalars.return_value.all.return_value = [chunk]
mock_session.execute = AsyncMock(return_value=mock_result)
mock_session.commit = AsyncMock()
mock_session.flush = AsyncMock()
mock_session.add = MagicMock()
```

**Module-level source inspection tests** (test_pipeline.py lines 258–308):
```python
# test_pipeline.py uses inspect.getsource for structural assertions — copy this approach:
def test_extractor_module_has_model_version():
    import inspect
    import app.pipeline.extractor as extractor_mod
    source = inspect.getsource(extractor_mod)
    assert "MODEL_VERSION" in source

def test_extractor_uses_tool_choice():
    import inspect
    import app.pipeline.extractor as extractor_mod
    source = inspect.getsource(extractor_mod)
    assert 'tool_choice' in source
    assert '"type": "tool"' in source or "\"type\": \"tool\"" in source
```

---

### `backend/tests/test_resolution.py` (test)

**Analog:** `backend/tests/test_pipeline.py`

**File header + imports**:
```python
"""Tests for resolver.py (Plan 03-XX).

Covers RESOLVE-01 through RESOLVE-04.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.pipeline.resolver import _resolve_concept, _stage_resolve
```

**Mock OpenAI embedding response helper**:
```python
def _make_embed_response(vector: list[float]) -> MagicMock:
    """Build a mock openai embeddings.create response."""
    embed_data = MagicMock()
    embed_data.embedding = vector
    response = MagicMock()
    response.data = [embed_data]
    return response
```

**Mock cosine query row helper**:
```python
def _make_concept_row(id: int = 1, title: str = "T", definition: str = "D", dist: float = 0.05):
    """Build a mock SA row result with .dist attribute (from .label('dist'))."""
    row = MagicMock()
    row.id = id
    row.title = title
    row.definition = definition
    row.key_points = []
    row.gotchas = []
    row.examples = []
    row.dist = dist
    return row
```

**RESOLVE-01 course_id filter assertion** (structural test pattern):
```python
def test_resolver_always_filters_by_course_id():
    """resolver.py must always include course_id in cosine queries (RESOLVE-01)."""
    import inspect
    import app.pipeline.resolver as resolver_mod
    source = inspect.getsource(resolver_mod)
    assert "course_id" in source
    assert "Concept.course_id ==" in source or "course_id ==" in source
```

---

### `backend/tests/test_edges.py` (test)

**Analog:** `backend/tests/test_pipeline.py`

**File header + imports**:
```python
"""Tests for edges.py (Plan 03-XX).

Covers EDGE-01 through EDGE-04.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.pipeline.edges import _stage_edges, _compute_depths
```

**BFS depth unit test pattern** (pure Python, no mocks needed):
```python
@pytest.mark.asyncio
async def test_bfs_assigns_depth_to_all_concepts():
    """BFS must assign non-null depth to isolated concepts (EDGE-04 fallback)."""
    # _compute_depths can be tested with a mocked session returning known data
    # concept IDs: 1, 2, 3 with no edges → all should get depth=1
    ...
```

**Co-occurrence pair enumeration test**:
```python
@pytest.mark.asyncio
async def test_co_occurrence_creates_pairs_for_same_chunk_concepts():
    """All (a, b) pairs from same chunk get co_occurrence edges (EDGE-02)."""
    # Mock session; assert Edge inserted for each combination
    ...
```

---

## Shared Patterns

### AsyncAnthropic Client Pattern
**Source:** `backend/app/pipeline/parsers.py` lines 111–113
**Apply to:** `extractor.py`, `resolver.py` (tiebreaker), `edges.py` (prereq inference)
```python
import anthropic
client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
```

Note: `parsers.py` uses a lazy `import anthropic` inside the function body. `extractor.py` and `edges.py` may use a module-level client (instantiated once) since they're pipeline stages, not parsers. Match the lazy-import style of parsers.py for consistency.

### AsyncOpenAI Client Pattern
**Source:** `backend/app/pipeline/pipeline.py` lines 164–165
**Apply to:** `resolver.py` (concept embedding)
```python
openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
```

### Session-Per-Stage Pattern
**Source:** `backend/app/pipeline/pipeline.py` — every stage function
**Apply to:** `extractor.py`, `resolver.py`, `edges.py`
```python
# Each stage opens its own AsyncSessionLocal context — NEVER pass session across stages
async with AsyncSessionLocal() as session:
    result = await session.execute(sa.select(...).where(...))
    items = result.scalars().all()
    # ... mutations ...
    await session.commit()
```
Critical: `expire_on_commit=False` is set in `database.py` line 14 — ORM objects remain accessible after commit.

### Settings API Key Guard
**Source:** `backend/app/pipeline/pipeline.py` lines 162–163
**Apply to:** `extractor.py`, `resolver.py`, `edges.py`
```python
# Skip stage if API key absent (dev without key) — matches _stage_embed pattern
if not settings.anthropic_api_key:
    return
if not settings.openai_api_key:
    return
```

### Error Handling (no try/except in stages — bubble to orchestrator)
**Source:** `backend/app/pipeline/pipeline.py` lines 40–43
**Apply to:** All three new stage functions
```python
# pipeline.py catches ALL exceptions at the top level with traceback.format_exc()
# Individual stages do NOT catch exceptions — they let them propagate up to run_pipeline.
# Exception: extraction uses a single retry on tool_use failure (EXTRACT-04).
try:
    await _stage_extract(source_id)
    # ...
except _DuplicateContent:
    await _stage_set_done(source_id)
except Exception:
    await _stage_set_error(source_id, traceback.format_exc())
```

### ORM Model Field Names
**Source:** `backend/app/models/models.py`
**Apply to:** All three new modules — use these exact field names:

| Model | Field | Type |
|-------|-------|------|
| `Concept` | `id`, `course_id`, `title`, `definition`, `key_points`, `gotchas`, `examples`, `related_concepts`, `embedding`, `depth` | as declared |
| `ConceptSource` | `concept_id`, `source_id`, `student_questions` | JSON for student_questions |
| `ExtractionCache` | `chunk_hash`, `model_version`, `extracted_concepts` | JSON for extracted_concepts |
| `Edge` | `from_id`, `to_id`, `edge_type`, `weight`, `edge_metadata` | Float for weight |
| `Chunk` | `id`, `source_id`, `text`, `page_num`, `embedding` | — |
| `Source` | `id`, `course_id`, `source_type` | — |

### Test Mock Session Structure
**Source:** `backend/tests/test_pipeline.py` lines 189–217
**Apply to:** All three new test files
```python
mock_session = AsyncMock()
mock_session.__aenter__ = AsyncMock(return_value=mock_session)
mock_session.__aexit__ = AsyncMock(return_value=False)
mock_session.execute = AsyncMock(return_value=MagicMock())
mock_session.commit = AsyncMock()
mock_session.flush = AsyncMock()
mock_session.add = MagicMock()

with patch("app.pipeline.extractor.AsyncSessionLocal", return_value=mock_session):
    ...
```

### pytest.ini — asyncio_mode = auto
**Source:** `backend/pytest.ini` (referenced in RESEARCH.md)
**Apply to:** All test files
```python
# asyncio_mode = auto means @pytest.mark.asyncio is optional
# test_pipeline.py uses it explicitly — new test files should too for clarity
@pytest.mark.asyncio
async def test_something():
    ...
```

---

## No Analog Found

All 7 files have close analogs in the codebase. No file requires research-only patterns.

---

## Metadata

**Analog search scope:** `backend/app/pipeline/`, `backend/app/models/`, `backend/app/core/`, `backend/tests/`
**Files scanned:** 7 primary analog files read in full
**Pattern extraction date:** 2026-04-25
