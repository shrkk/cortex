import Foundation

// Stub for plan 02-06 — fully implemented in plan 02-07 (CortexCourseTab.swift).
// Holds the session-scoped course ID chosen via the inline course tab or auto-match.
@MainActor
final class CortexCourseTabState {
    static let shared = CortexCourseTabState()
    private init() {}

    /// Course ID selected for the current session (populated by CortexCourseTab in 02-07).
    var sessionCourseId: Int?

    /// Pre-flight semantic match — wraps CortexClient.matchCourse.
    func resolve(hint: String) async -> Int? {
        await CortexClient.shared.matchCourse(hint: hint)
    }
}
