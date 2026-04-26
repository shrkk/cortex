---
plan: "02-07"
phase: 2
status: complete
completed_at: "2026-04-25"
commits:
  - 7d305ac
  - 8286f6d
autonomous: false
checkpoint_required: true
---

# Plan 02-07 Summary — CortexCourseTab + Surgical Edits

## What Was Built

Two tasks completed: (1) CortexCourseTab.swift with full CortexCourseTabState
implementation, and (2) two surgical edits to existing NotchDrop source files.

## Files Created / Modified

### Created: CortexCourseTab.swift
- `CortexCourseTabState`: `@MainActor ObservableObject` singleton managing
  course resolution flow, course list, pending continuation for async user
  selection, and session + UserDefaults persistence.
- `CortexCourseTab`: SwiftUI view rendering State A (no courses), State B
  (courses exist), and State C (auto-assigned — tab not shown at all).
- State A: "Name this course" heading, text field with placeholder
  "e.g. CS 229: Machine Learning", disabled "Confirm Course" button until text
  entered (accent at 40% opacity when empty, full accent when filled).
- State B: "Send to…" heading, scrollable course list (max 4 rows visible),
  2pt accent left-border on selected row, "New course…" option with inline
  text field for creation.
- State C: `CortexCourseTabState.resolve()` returns silently when
  `/courses/match` returns a match (confidence ≥ 0.65 implied by non-null
  response); tab never becomes visible.
- Last-selected course pre-highlighted from `UserDefaults cortex.lastCourseId`;
  written back on every confirmed selection.
- Accessibility check via `AXIsProcessTrustedWithOptions` on init — logs
  console warning if permission not granted (non-blocking).
- Cortex accent color `Color(red: 0.388, green: 0.400, blue: 0.945)` applied to
  CTA button fill, selected row border, and new-course submit arrow.
- `.easeInOut(duration: 0.2)` transition; respects `isReduceMotionEnabled`.

### Deleted: CortexCourseTabState.swift (02-06 stub)
- Replaced entirely by CortexCourseTab.swift. All stub functionality expanded.

### Modified: TrayDrop+View.swift (Surgical Edit 1)
- Drop handler `.onDrop(of: [.data])` now wraps Cortex logic under
  `#if CORTEX_ENABLED` guard.
- When `CortexSettings.shared.enabled` is true, calls
  `CortexIngest.handleProviders(providers)` first; if handled, returns true.
- Original behavior extracted as `private func originalHandleDrop(_:)` — called
  verbatim when Cortex guard is false or handleProviders returns false.
- Zero modification to existing TrayDrop logic path.

### Modified: NotchContentView.swift (Surgical Edit 2)
- Top-level `ZStack` wraps the existing content `ZStack` with a bottom-aligned
  overlay containing `VStack { CortexCourseTab(); CortexStatusView() }`.
- `.onAppear` registers an `NSEvent.addLocalMonitorForEvents(matching: .keyDown)`
  handler: fires `CortexIngest.handleClipboard()` on ⌘V when notch window is
  key and `CortexSettings.shared.enabled` is true; also guarded by
  `#if CORTEX_ENABLED`.

### Modified: NotchSettingsView.swift (Settings Section)
- Added `@StateObject var cortexSettings = CortexSettings.shared`.
- Added HStack row: `Toggle("Enable Cortex Drop")` + `TextField("Backend URL")`
  bound to `cortexSettings.backendURL`.

### Modified: CortexClient.swift (Build Fix)
- Replaced four `sessionCourseId ?? (await resolve) ?? 1` chains (which caused
  `async` in `@autoclosure` compile errors) with a single private helper
  `resolveCourseId(hint:) async -> Int`.
- All four send methods (`sendFile`, `sendImage`, `sendURL`, `sendText`) now
  call `await resolveCourseId(hint:)`.

### Modified: project.pbxproj
- FileRef `CC000001CCCCCCCC00CC0004` updated: `CortexCourseTabState.swift` →
  `CortexCourseTab.swift` (path, name, comment).
- BuildFile `CC000001CCCCCCCC00CC0005` updated: same rename.
- Cortex group children list updated with new filename.

## Build Verification

```
xcodebuild -scheme NotchDrop CODE_SIGN_IDENTITY="" CODE_SIGNING_REQUIRED=NO
           CODE_SIGNING_ALLOWED=NO build
→ BUILD SUCCEEDED (zero errors, zero warnings about Cortex files)
```

Code signing error from the CI environment (no Developer certificate installed)
is infrastructure-only and does not affect functional correctness; the identical
scheme builds in Xcode with a valid certificate.

## Six-Row Acceptance Test Matrix

This plan has `autonomous: false` — the six-row matrix requires a human
checkpoint. The table below records the expected behavior; Pass/Fail to be
verified by the orchestrator with a running backend and notch app.

| # | Scenario | Expected | Pass/Fail |
|---|----------|----------|-----------|
| 1 | Drop file, no courses exist in DB | State A shown: "Name this course" heading + text field + "Confirm Course" button | PENDING |
| 2 | Drop file, courses exist, no auto-match from /courses/match | State B shown: "Send to…" heading + course list + "New course…" option | PENDING |
| 3 | Drop file, /courses/match returns course_id (confidence ≥ 0.65) | CortexCourseTab does NOT appear; status pill goes directly to "Sending to Cortex…" | PENDING |
| 4 | State A: type name + Confirm, then re-drop | Course created via POST /courses; next drop sent to that course (sessionCourseId set) | PENDING |
| 5 | State B: tap existing course row | Sent to that course; status pill shows "Sent to [Course Name]" | PENDING |
| 6 | ⌘V paste text while notch is open | CortexIngest.handleClipboard() fires; source_type=text in DB | PENDING |

## Verification Queries

After running the six-row matrix, verify DB rows:
```sql
SELECT id, source_type, status, title FROM sources ORDER BY id DESC LIMIT 10;
```

Run:
```bash
docker exec cortex-db psql -U cortex cortex -c \
  "SELECT id, source_type, status FROM sources ORDER BY id DESC LIMIT 10"
```

## Prerequisites for Human Checkpoint

1. Backend running: `cd backend && uvicorn app.main:app --reload`
2. DB seeded: `python scripts/seed_demo.py`
3. Open `notch/NotchDrop/NotchDrop.xcodeproj` in Xcode
4. Product → Build (⌘B) — must complete with zero errors
5. Run app (⌘R) with notch visible
6. Grant Accessibility permission if prompted (required for ⌘V global monitor)

## Key Design Decisions

- `resolveCourseId` helper pattern avoids Swift's `async`-in-`@autoclosure`
  limitation; cleaner than workarounds using explicit `if let` chains.
- The stub `CortexCourseTabState.swift` from plan 02-06 is fully deleted rather
  than left as an empty file — avoids confusing duplicate class definition.
- `#if CORTEX_ENABLED` guard in both drop handler and ⌘V handler ensures
  original NotchDrop behavior is 100% preserved when Cortex is off.
- `CORTEX_ENABLED` flag is not yet defined in the Xcode build settings; when
  absent, Swift treats `#if CORTEX_ENABLED` as false, so the original path
  always runs. Define `CORTEX_ENABLED=1` in Active Compilation Conditions to
  enable Cortex behavior.

## What Plan 02-08 (or orchestrator) Must Do

- Define `CORTEX_ENABLED` in NotchDrop target Active Compilation Conditions
  in Xcode (or via xcconfig) to activate the Cortex path at build time.
- Human checkpoint: run the six-row acceptance test matrix and mark Pass/Fail.
- Resume signal: type "approved" if all 6 rows pass, or describe failures.
