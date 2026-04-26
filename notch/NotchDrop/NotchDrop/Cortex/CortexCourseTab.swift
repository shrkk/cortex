import AppKit
import SwiftUI

// MARK: - Accent color

private let cortexAccent = Color(red: 0.388, green: 0.400, blue: 0.945)

// MARK: - CortexCourseTabState

/// Manages the inline course-assignment UI state.
/// Replaces the stub in CortexCourseTabState.swift (plan 02-06).
@MainActor
final class CortexCourseTabState: ObservableObject {
    static let shared = CortexCourseTabState()

    @Published var isVisible = false
    @Published var courses: [CourseOption] = []
    @Published var newCourseName = ""
    @Published var selectedCourseId: Int? = nil

    /// Course ID remembered for the whole session after first pick.
    var sessionCourseId: Int?

    struct CourseOption: Identifiable {
        let id: Int
        let title: String
    }

    private var pendingContinuation: CheckedContinuation<Int?, Never>?

    private init() {
        // Check Accessibility permission on init — log a warning if missing.
        // This is required for global keyboard monitors (⌘V paste).
        // "AXTrustedCheckOptionPrompt" is the raw CF string key value.
        let options = ["AXTrustedCheckOptionPrompt": false] as CFDictionary
        let trusted = AXIsProcessTrustedWithOptions(options)
        if !trusted {
            print("[CortexCourseTabState] WARNING: Accessibility permission not granted. " +
                  "⌘V paste monitoring may not fire. Grant in System Settings → Privacy → Accessibility.")
        }
    }

    // MARK: - Resolution

    /// Resolve a course ID for the given hint.
    /// Returns immediately if a session course is already set.
    /// Otherwise: pre-flight match → if confidence ≥ 0.65, silent assignment.
    /// If no match, shows the picker (State A or B) and waits for user input.
    func resolve(hint: String) async -> Int? {
        // 1. Use session-scoped course if already set
        if let id = sessionCourseId { return id }

        // 2. Pre-flight semantic match (State C — silent assignment)
        if let match = await CortexClient.shared.matchCourse(hint: hint) {
            sessionCourseId = match
            return match
        }

        // 3. Fetch available courses to determine State A vs State B
        let fetched = await CortexClient.shared.fetchCourses()
        let lastCourseId = UserDefaults.standard.integer(forKey: "cortex.lastCourseId")
        courses = fetched.map { CourseOption(id: $0.id, title: $0.title) }

        // Pre-highlight last-selected course if it exists in the list
        if lastCourseId > 0, courses.contains(where: { $0.id == lastCourseId }) {
            selectedCourseId = lastCourseId
        } else {
            selectedCourseId = nil
        }

        isVisible = true

        // Wait for user selection (resolved via selectCourse / createCourse)
        return await withCheckedContinuation { continuation in
            self.pendingContinuation = continuation
        }
    }

    // MARK: - User Actions

    func selectCourse(_ id: Int) {
        sessionCourseId = id
        UserDefaults.standard.set(id, forKey: "cortex.lastCourseId")
        isVisible = false
        pendingContinuation?.resume(returning: id)
        pendingContinuation = nil
    }

    func createCourse() async {
        let name = newCourseName.trimmingCharacters(in: .whitespaces)
        guard !name.isEmpty else { return }
        let id = await CortexClient.shared.createCourse(title: name)
        newCourseName = ""
        selectCourse(id)
    }

    func dismiss() {
        isVisible = false
        pendingContinuation?.resume(returning: nil)
        pendingContinuation = nil
    }
}

// MARK: - CortexCourseTab View

/// Inline course-assignment tab that slides into the expanded notch panel.
/// Renders three states:
///   State A — no courses: "Name this course" heading + text field + Confirm button
///   State B — courses exist: "Send to…" heading + course rows + "New course…" option
///   State C — auto-assigned (confidence ≥ 0.65): tab not shown at all
struct CortexCourseTab: View {
    @ObservedObject var state = CortexCourseTabState.shared

    private var reduceMotion: Bool {
        NSWorkspace.shared.accessibilityDisplayShouldReduceMotion
    }

    var body: some View {
        Group {
            if state.isVisible {
                VStack(alignment: .leading, spacing: 0) {
                    if state.courses.isEmpty {
                        stateAView
                    } else {
                        stateBView
                    }
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 12)
                .background(Color.white.opacity(0.07))
                .clipShape(RoundedRectangle(cornerRadius: 10))
                .frame(minHeight: 120)
            }
        }
        .animation(reduceMotion ? nil : .easeInOut(duration: 0.2), value: state.isVisible)
    }

    // MARK: State A — No courses

    private var stateAView: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Name this course")
                .font(.system(size: 13, weight: .semibold))
                .foregroundColor(.white.opacity(0.90))

            TextField("e.g. CS 229: Machine Learning", text: $state.newCourseName)
                .font(.system(size: 11))
                .foregroundColor(.white)
                .textFieldStyle(.plain)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(Color.white.opacity(0.10))
                .clipShape(RoundedRectangle(cornerRadius: 6))
                .frame(height: 32)
                .onSubmit { Task { await state.createCourse() } }

            let isEmpty = state.newCourseName.trimmingCharacters(in: .whitespaces).isEmpty
            Button("Confirm Course") {
                Task { await state.createCourse() }
            }
            .font(.system(size: 13, weight: .semibold))
            .foregroundColor(.white)
            .frame(maxWidth: .infinity, minHeight: 32)
            .background(isEmpty ? cortexAccent.opacity(0.40) : cortexAccent)
            .clipShape(RoundedRectangle(cornerRadius: 6))
            .disabled(isEmpty)
        }
    }

    // MARK: State B — Courses exist

    private var stateBView: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Send to\u{2026}")
                .font(.system(size: 13, weight: .semibold))
                .foregroundColor(.white.opacity(0.90))

            // Show scroll when > 4 rows (4 rows × 40pt + 3 gaps × 8pt = 184pt max)
            ScrollView(.vertical, showsIndicators: false) {
                VStack(spacing: 8) {
                    ForEach(state.courses) { course in
                        courseRow(course)
                    }
                    newCourseRow
                }
            }
            .frame(maxHeight: CGFloat(4 * 40 + 3 * 8))
        }
    }

    private func courseRow(_ course: CortexCourseTabState.CourseOption) -> some View {
        let isSelected = state.selectedCourseId == course.id
        return Button {
            state.selectCourse(course.id)
        } label: {
            HStack {
                if isSelected {
                    Rectangle()
                        .fill(cortexAccent)
                        .frame(width: 2)
                        .frame(height: 40)
                }
                Text(course.title)
                    .font(.system(size: 13, weight: .regular))
                    .foregroundColor(.white.opacity(0.90))
                    .lineLimit(1)
                Spacer()
            }
            .padding(.horizontal, 12)
            .frame(height: 40)
            .background(isSelected ? Color.white.opacity(0.12) : Color.white.opacity(0.04))
            .clipShape(RoundedRectangle(cornerRadius: 6))
        }
        .buttonStyle(.plain)
    }

    private var newCourseRow: some View {
        VStack(spacing: 6) {
            // "New course…" tappable row
            Button {
                // Transition to creation mode: clear courses to show State A inline
                // We handle this by showing a text field below the row
            } label: {
                HStack(spacing: 6) {
                    Image(systemName: "plus.circle")
                        .font(.system(size: 12))
                        .foregroundColor(.white.opacity(0.55))
                    Text("New course\u{2026}")
                        .font(.system(size: 13, weight: .regular))
                        .foregroundColor(.white.opacity(0.55))
                    Spacer()
                }
                .padding(.horizontal, 12)
                .frame(height: 40)
                .background(Color.white.opacity(0.04))
                .clipShape(RoundedRectangle(cornerRadius: 6))
            }
            .buttonStyle(.plain)

            // Inline new course text field + submit
            HStack(spacing: 6) {
                TextField("New course\u{2026}", text: $state.newCourseName)
                    .font(.system(size: 11))
                    .foregroundColor(.white)
                    .textFieldStyle(.plain)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color.white.opacity(0.10))
                    .clipShape(RoundedRectangle(cornerRadius: 6))
                    .frame(height: 28)
                    .onSubmit { Task { await state.createCourse() } }

                if !state.newCourseName.trimmingCharacters(in: .whitespaces).isEmpty {
                    Button {
                        Task { await state.createCourse() }
                    } label: {
                        Text("\u{2192}")
                            .font(.system(size: 13, weight: .semibold))
                            .foregroundColor(.white)
                            .frame(width: 28, height: 28)
                            .background(cortexAccent)
                            .clipShape(RoundedRectangle(cornerRadius: 6))
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }
}
