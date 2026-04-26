# Phase 4: Flashcards, Struggle & Quiz - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-25
**Phase:** 4-flashcards-struggle-quiz
**Areas discussed:** Flashcard generation, Quiz answer storage, Struggle signal scope, Quiz question generation

---

## Flashcard Generation

| Option | Description | Selected |
|--------|-------------|----------|
| One call, all cards | Single LLM call per concept returns a JSON array of all 3–6 cards. Most efficient. | ✓ |
| One call per card type | Separate LLM calls for definition, application, gotcha, compare cards. More targeted prompts but 3–4× more API calls. | |

**User's choice:** One call, all cards

---

| Option | Description | Selected |
|--------|-------------|----------|
| Count toward the cap | Total cards capped at 6; gotcha cards count toward limit. | |
| Gotchas always included | Always include one card per gotcha entry regardless of total count. Cap applies to definition/application/compare only. | ✓ |

**User's choice:** Gotchas always included

---

| Option | Description | Selected |
|--------|-------------|----------|
| Always generate minimum 2 cards | Every concept gets at least definition + application. | ✓ |
| Skip if only 1 card possible | Skip concepts with insufficient content for at least 2 cards. | |

**User's choice:** Always generate minimum 2 cards

---

| Option | Description | Selected |
|--------|-------------|----------|
| Skip if flashcards exist | Idempotent — skip if Concept.flashcards non-empty. | ✓ |
| Always regenerate | Delete existing flashcards and regenerate on every run. | |

**User's choice:** Skip if flashcards exist (idempotent)

---

## Quiz Answer Storage

| Option | Description | Selected |
|--------|-------------|----------|
| Extend quiz JSON | Store answers inside quizzes.questions JSON. No new migration needed. | ✓ |
| New quiz_attempts table | Add a new Alembic migration with quiz_attempts table. More relational but adds scope. | |

**User's choice:** Extend quiz JSON

---

| Option | Description | Selected |
|--------|-------------|----------|
| Return final results inline | Terminal answer response IS the final results. No separate GET call needed. | ✓ |
| Return next=null, client fetches results | Last answer returns next_question: null; client must call GET /quiz/{id}/results. | |

**User's choice:** Return final results inline

---

## Struggle Signal Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Only concepts touched this run | Recompute signals only for concepts whose concept_sources include current source_id. | ✓ |
| Course-wide recompute | Recompute all concepts in the course on every ingest. Slower at scale. | |

**User's choice:** Only concepts touched this run

---

| Option | Description | Selected |
|--------|-------------|----------|
| Skip STRUGGLE-01, check other signals | If no chat_log ConceptSources exist, skip embedding comparison. Still check STRUGGLE-03/04. | ✓ |
| Set repeated_confusion=false explicitly | Always write the key so frontend knows it was evaluated. | |

**User's choice:** Skip STRUGGLE-01 when no chat_log sources; evaluate STRUGGLE-03/04 independently

---

## Quiz Question Generation

| Option | Description | Selected |
|--------|-------------|----------|
| Weighted thirds | ~40% MCQ, ~30% short_answer, ~30% application. | ✓ |
| Gotcha-concept weighting | Type distribution follows concept profile (gotcha-heavy → short_answer/application). | |

**User's choice:** Weighted thirds

---

| Option | Description | Selected |
|--------|-------------|----------|
| Inline options array | MCQ options as array with correct_index integer. | ✓ |
| Lettered dict | MCQ options as {A:..., B:..., C:..., D:...} with correct_key string. | |

**User's choice:** Inline options array

---

| Option | Description | Selected |
|--------|-------------|----------|
| One LLM call for full quiz | Single tool_use call with all selected concepts as context. | ✓ |
| One call per concept | Per-concept calls, more parallel but N× API calls. | |

**User's choice:** One LLM call for full quiz

---

## Claude's Discretion

- Exact flashcard prompt wording (front/back style and tone)
- Exact quiz question generation prompt
- STRUGGLE-02 (retention_gap) session boundary detection — use source `created_at` timestamps

## Deferred Ideas

None — discussion stayed within phase scope.
