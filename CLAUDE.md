# Cortex — Claude Code Guide

## Project

Second brain for students: NotchDrop-fork ingestion → course-rooted knowledge graph → flashcards + quizzes.
Three surfaces: Swift macOS notch app, Next.js frontend, FastAPI backend.

Planning docs: `.planning/` — read PROJECT.md and ROADMAP.md for full context.

## GSD Workflow

This project uses GSD for phased execution.

- **Next step**: `/gsd-plan-phase 1` (Infrastructure)
- **Build order**: Phase 1 → 2 → 3 → 4 → 5 → 6 → 7
- **Mode**: YOLO (auto-approve), parallel execution

Do not deviate from the spec without asking. Ask before architectural changes.

## Critical Stack Notes

- Docker image: `pgvector/pgvector:pg16` (NOT `postgres:16`)
- React Flow: `@xyflow/react` (NOT `reactflow`)
- Dagre: `@dagrejs/dagre` (NOT `dagre`)
- Alembic migrations: hand-written only — autogenerate does not detect Vector columns
- CORS: must allow missing `Origin` header (Swift URLSession sends none)
- FastAPI startup: reset `status=processing` → `status=pending` on boot

## Key Design Decisions

- Flashcards are graph nodes attached to concept nodes — no SRS, no due dates, flip-only
- Quiz is a standalone node hanging off the course root
- Course assignment is dynamic via `/courses/match` pre-flight + `CortexCourseTab` inline in notch
- No mastery scoring — struggle signals feed quiz generation only
- Concept resolution is strictly course-scoped — never merge across courses

## Notch Work

Use the `notch-specialist` agent (`.claude/agents/notch-specialist.md`) for all Swift/Xcode work.
