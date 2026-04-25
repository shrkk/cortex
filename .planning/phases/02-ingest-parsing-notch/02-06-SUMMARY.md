---
plan: "02-06"
phase: 2
status: complete
completed_at: "2026-04-25"
commits:
  - 1f184b9
  - c952a9d
  - d1e8f44
  - eda871c
---

# Plan 02-06 Summary — Swift Cortex Module

## What Was Built

Four Swift files in `notch/NotchDrop/NotchDrop/Cortex/` implementing the Cortex Drop notch integration foundation.

## Files Created

### CortexSettings.swift
- `ObservableObject` with `@Published` properties for `enabled`, `backendURL`, `courseId`
- UserDefaults keys: `cortex.enabled`, `cortex.backendURL`, `cortex.courseId`
- Default backend URL: `http://localhost:8000`
- Backward-compatible `courseId` property (fallback: 1) for plan 02-07 forward reference

### CortexClient.swift
- `@MainActor` singleton (`CortexClient.shared`) with `@Published var status: CortexStatus`
- Four send methods: `sendFile(at:)`, `sendImage(_:)`, `sendURL(_:)`, `sendText(_:title:)`
- Three course resolution methods: `matchCourse(hint:)`, `fetchCourses()`, `createCourse(title:)`
- Course resolution flow per method: `CortexCourseTabState.shared.sessionCourseId ?? resolve(hint:) ?? 1`
- Status auto-dismiss: success 2s (`2_000_000_000` ns), error 4s (`4_000_000_000` ns)
- Multipart upload for file/image, JSON body for url/text
- `CortexCourseTabState` forward-referenced — defined in plan 02-07

### CortexIngest.swift
- `handleProviders(_:)` for drag-and-drop from `NSItemProvider` array
- `handleClipboard()` for ⌘V paste from `NSPasteboard.general`
- **Critical UTI ordering**: `UTType.image.identifier` checked at line 17 BEFORE `canLoadObject(ofClass: URL.self)` at line 27 — prevents browser image drag temp-file trap
- Clipboard priority: image (`NSImage(pasteboard:)`) → URL (`NSURL`) → string (`NSString`)
- Debug logging of available UTIs on no-match

### CortexStatusView.swift
- SwiftUI pill view with 3 active states + idle (hidden)
- Sending: Cortex Indigo `#6366F1` at 85% opacity, `arrow.up.circle` icon, "Sending to Cortex…"
- Success: `systemGreen` at 15% opacity + white 0.5pt border, `checkmark.circle.fill` icon, dynamic message
- Error: `systemRed` at 85% opacity, `exclamationmark.circle.fill` icon, "Upload failed — check settings"
- Entry animation: `.spring(response: 0.3, dampingFraction: 0.7)`
- Exit animation: `.easeOut(duration: 0.25)`
- Respects `NSAccessibility.isReduceMotionEnabled` — falls back to `.animation(nil)`
- Accessibility label: `"Cortex status: [state copy]"`

## Acceptance Criteria — All Passed

| Check | Result |
|-------|--------|
| All four files exist in Cortex/ | PASS |
| `cortex.enabled\|cortex.backendURL\|cortex.courseId` (3 keys × 2 = 6 occurrences) | PASS (6) |
| `localhost:8000` default | PASS |
| `ObservableObject\|@Published` at least 3 occurrences | PASS (4) |
| `func matchCourse\|func fetchCourses\|func createCourse` = 3 | PASS |
| `sendFile\|sendImage\|sendURL\|sendText` at least 4 | PASS (4 definitions) |
| `2_000_000_000\|4_000_000_000` = 2 | PASS |
| `courses/match\|/courses` at least 2 | PASS (6) |
| UTI ordering: image line < URL line | PASS (17 < 27) |
| `handleProviders\|handleClipboard` = 2 | PASS |
| `NSPasteboard.general\|NSImage(pasteboard` | PASS |
| `Sending to Cortex\|Upload failed` = 2 | PASS |
| `arrow.up.circle\|checkmark.circle.fill\|exclamationmark.circle.fill` = 3 | PASS |
| `spring\|easeOut` at least 2 | PASS (3) |
| `accessibilityLabel\|isReduceMotionEnabled` = 2 | PASS |

## Key Design Decisions

- `CortexCourseTabState` is forward-referenced in `CortexClient.swift` — Swift resolves this at compile time since both files are in the same Xcode target. No stubs or conditionals needed.
- The `.gitkeep` file in `Cortex/` was pre-created by plan 02-04; the four Swift files were added alongside it.
- No third-party Swift package dependencies — only Foundation, AppKit, SwiftUI, UniformTypeIdentifiers.

## What Plan 02-07 Must Do

- Add `CortexCourseTab.swift` (defines `CortexCourseTabState` — resolves the forward reference)
- Surgical edit to `TrayDrop+View.swift`: replace `.onDrop(of: [.data])` with Cortex-aware handler under `#if CORTEX_ENABLED` guard
- Add ⌘V global keyboard monitor gated on notch open state
- Add `CortexSettings` section to `NotchSettingsView.swift`
- Wire `CortexStatusView` and `CortexCourseTab` into `NotchContentView.swift`
- Verify Xcode build: zero errors (build verification deferred to 02-07 per plan spec)
