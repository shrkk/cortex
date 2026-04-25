---
phase: 2
plan: "02-02"
subsystem: backend/pipeline
tags: [parsers, pdf, url, image, text, tdd, pymupdf, trafilatura, httpx, anthropic]
dependency_graph:
  requires:
    - "02-01"  # courses.embedding migration (pipeline package lives in same backend)
  provides:
    - "parse_pdf"
    - "parse_url"
    - "parse_image"
    - "parse_text"
  affects:
    - "02-05"  # ingest pipeline calls these parsers
tech_stack:
  added:
    - "pymupdf (fitz) — PDF page-by-page extraction"
    - "httpx — async HTTP client for URL fetching"
    - "trafilatura — HTML-to-text extraction"
    - "anthropic (lazy import) — Claude vision OCR in parse_image"
  patterns:
    - "Async stateless pure functions returning (list[dict], str) tuples"
    - "Lazy anthropic import inside parse_image to avoid import-time crash when key absent"
    - "arXiv abs-to-pdf URL rewrite via compiled regex"
    - "TDD: RED (failing tests) → GREEN (implementation) → no refactor needed"
key_files:
  created:
    - "backend/app/pipeline/__init__.py"
    - "backend/app/pipeline/parsers.py"
    - "backend/tests/test_parsers.py"
  modified: []
decisions:
  - "requirements.txt already had all four dependencies pre-declared — no modification needed (pymupdf==1.27.2, httpx==0.28.1, trafilatura==2.0.0, anthropic==0.97.0)"
  - "Used lazy import for anthropic inside parse_image to avoid ValidationError at test collection time when ANTHROPIC_API_KEY is absent"
  - "parse_text normalizes multiple spaces/tabs but preserves single newlines (paragraph structure) using [^\S\n]+ pattern"
metrics:
  duration: "3 minutes"
  completed_date: "2026-04-25T23:36:11Z"
  tasks_completed: 3
  tasks_total: 3
  tests_added: 24
  tests_passing: 24
---

# Phase 2 Plan 02: Parsers Module Summary

**One-liner:** Async parsers for PDF (pymupdf page-per-chunk), URL (httpx+trafilatura+arXiv rewrite), image (Claude claude-sonnet-4-6 vision OCR), and text (whitespace normalization) returning uniform `(list[dict], str)` tuples.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create pipeline package init | 7236647 | backend/app/pipeline/__init__.py |
| 2 (RED) | Add failing tests for parsers | 6dbfd76 | backend/tests/test_parsers.py |
| 2 (GREEN) | Implement parsers module | 68d3e4a | backend/app/pipeline/parsers.py |
| 3 | Verify requirements.txt | (no-op) | — |

## Implementation Details

### parse_pdf (PARSE-01)
- Uses `fitz.open(stream=data, filetype="pdf")` — streams bytes without temp file
- Skips pages with `len(text.strip()) < 50` (D-09 blank page threshold)
- Returns `page_num = page.number + 1` (1-indexed)
- Title = filename without extension via `rsplit(".", 1)[0]`

### parse_url (PARSE-03 + PARSE-04)
- `_ARXIV_ABS` regex rewrites `arxiv.org/abs/XXXX` → `arxiv.org/pdf/XXXX`, then routes to `parse_pdf`
- Uses `trafilatura.extract(raw_html)` for clean text; fallback strips HTML tags if trafilatura returns < 50 chars
- `<title>` tag extracted via regex for page title; falls back to URL string
- httpx `follow_redirects=True, timeout=10.0`

### parse_image (PARSE-02)
- Lazy `import anthropic` inside the function body — avoids `ValidationError` on `Settings()` when API key absent
- MIME type inferred from filename extension; defaults to `image/png`
- Claude model: `claude-sonnet-4-6`, `max_tokens=4096`
- Title = `"Image: " + ocr_text[:60].replace("\n", " ")`

### parse_text (PARSE-05)
- `re.sub(r"[^\S\n]+", " ", text)` — collapses spaces/tabs but preserves newlines
- `re.sub(r"\n{3,}", "\n\n", ...)` — collapses 3+ blank lines to 1 blank line
- Auto-derived title = first 60 chars with embedded newlines replaced by spaces

## Deviations from Plan

### No-op: Task 3 (requirements.txt)
- **Found during:** Task 3 pre-check
- **Issue:** All four required packages (`pymupdf==1.27.2`, `httpx==0.28.1`, `trafilatura==2.0.0`, `anthropic==0.97.0`) were already declared in requirements.txt under the "Future phases" comment block added in Phase 1
- **Action:** No modification needed — acceptance criteria already satisfied
- **Files modified:** None

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED (test commit) | 6dbfd76 | PASS — 24 tests failed on missing module |
| GREEN (feat commit) | 68d3e4a | PASS — 24 tests passing |
| REFACTOR | skipped | No cleanup needed |

## Threat Mitigations Applied

| Threat ID | Mitigation |
|-----------|-----------|
| T-02-02-03 | `anthropic` client initialized inside `parse_image` (lazy import); API key from `settings.anthropic_api_key` (env var); never logged |
| T-02-02-01 | parse_pdf documented for pipeline-level try/except in Plan 02-05 |
| T-02-02-04 | httpx timeout=10.0 enforced; file size cap deferred to /ingest (Plan 02-05) |

## Known Stubs

None — all four parsers are fully implemented. `parse_image` requires a live Anthropic API key and network access at runtime; this is expected behavior, not a stub.

## Self-Check

- [x] `backend/app/pipeline/__init__.py` exists
- [x] `backend/app/pipeline/parsers.py` exists with 4 parse functions
- [x] `backend/tests/test_parsers.py` exists with 24 tests
- [x] Commits 7236647, 6dbfd76, 68d3e4a exist in git log
- [x] 24/24 tests passing

## Self-Check: PASSED
