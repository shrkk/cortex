import AppKit
import SwiftUI

// MARK: - Design tokens

private let cortexAccent     = Color(red: 0.788, green: 0.392, blue: 0.259) // #C96442 terracotta
private let panelBg          = Color(red: 0.078, green: 0.071, blue: 0.059).opacity(0.94) // #14120F
private let panelFg          = Color(red: 0.949, green: 0.929, blue: 0.898) // #F2EDE3
private let panelFgMuted     = Color(red: 0.949, green: 0.929, blue: 0.898).opacity(0.50)
private let panelFgDim       = Color(red: 0.949, green: 0.929, blue: 0.898).opacity(0.45)
private let panelBorder      = Color.white.opacity(0.06)
private let panelRowHover    = Color.white.opacity(0.05)
private let panelRowSelected = Color(red: 0.788, green: 0.392, blue: 0.259).opacity(0.12) // accent 12%
private let panelInput       = Color.white.opacity(0.06)
private let panelInputBorder = Color.white.opacity(0.10)

// MARK: - CortexCourseTabState

@MainActor
final class CortexCourseTabState: ObservableObject {
    static let shared = CortexCourseTabState()

    @Published var isVisible = false
    @Published var courses: [CourseOption] = []
    @Published var newCourseName = ""
    @Published var selectedCourseId: Int? = nil

    var sessionCourseId: Int?

    struct CourseOption: Identifiable {
        let id: Int
        let title: String
        let concepts: Int
    }

    private var pendingContinuation: CheckedContinuation<Int?, Never>?

    private init() {}

    func resolve(hint: String) async -> Int? {
        // Always attempt semantic matching — sessionCourseId must NOT short-circuit
        // this, because a previous drop in the same session may have been a different
        // subject. Example: Math 207 drop sets sessionCourseId=1, then CSE 122 drop
        // should NOT inherit it without re-matching.
        if let match = await CortexClient.shared.matchCourse(hint: hint) {
            sessionCourseId = match
            return match
        }

        // No confident match — show picker with last-used course pre-selected.
        // sessionCourseId is used only to seed the picker default, not to skip it.
        let fetched = await CortexClient.shared.fetchCourses()
        let lastId  = sessionCourseId ?? UserDefaults.standard.integer(forKey: "cortex.lastCourseId")
        courses = fetched.map { CourseOption(id: $0.id, title: $0.title, concepts: 0) }
        selectedCourseId = (lastId > 0 && courses.contains { $0.id == lastId }) ? lastId : nil
        isVisible = true

        return await withCheckedContinuation { pendingContinuation = $0 }
    }

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

struct CortexCourseTab: View {
    @ObservedObject var state = CortexCourseTabState.shared

    private var reduceMotion: Bool {
        NSWorkspace.shared.accessibilityDisplayShouldReduceMotion
    }

    var body: some View {
        // Rendered inline — no card chrome. The notch itself is the background.
        VStack(alignment: .leading, spacing: 0) {
            eyebrow
            if state.courses.isEmpty {
                Spacer(minLength: 0)
                inputRow(placeholder: "e.g. CS 229")
            } else {
                courseList
                Divider().background(panelBorder)
                inputRow(placeholder: "new course\u{2026}")
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding(.horizontal, 16)
        .padding(.top, 6)
        .padding(.bottom, 36) // leave room for status pill
    }

    // MARK: Eyebrow

    private var eyebrow: some View {
        Text(state.courses.isEmpty ? "Name this course" : "Which course?")
            .font(.system(size: 10, weight: .medium))
            .textCase(.uppercase)
            .tracking(0.8)
            .foregroundStyle(panelFgDim)
            .padding(.bottom, 8)
    }

    // MARK: Course list (State B)

    private var courseList: some View {
        VStack(spacing: 0) {
            ForEach(state.courses.prefix(3)) { course in
                courseRow(course)
            }
        }
        .padding(.bottom, 6)
    }

    private func courseRow(_ course: CortexCourseTabState.CourseOption) -> some View {
        let selected = state.selectedCourseId == course.id
        return Button { state.selectCourse(course.id) } label: {
            HStack(spacing: 10) {
                Circle()
                    .fill(selected ? cortexAccent : panelFgMuted)
                    .frame(width: 5, height: 5)
                Text(course.title)
                    .font(.system(size: 13, design: .serif))
                    .fontWeight(.medium)
                    .foregroundStyle(panelFg)
                    .lineLimit(1)
                Spacer()
                if course.concepts > 0 {
                    Text("\(course.concepts)")
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundStyle(panelFgMuted)
                }
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 5)
            .background(selected ? panelRowSelected : Color.clear)
            .clipShape(RoundedRectangle(cornerRadius: 6))
        }
        .buttonStyle(.plain)
    }

    // MARK: Input row

    private func inputRow(placeholder: String) -> some View {
        HStack(spacing: 8) {
            TextField(placeholder, text: $state.newCourseName)
                .font(.system(size: 13))
                .foregroundStyle(panelFg)
                .textFieldStyle(.plain)
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(panelInput)
                .clipShape(RoundedRectangle(cornerRadius: 6))
                .overlay(RoundedRectangle(cornerRadius: 6).strokeBorder(panelInputBorder, lineWidth: 1))
                .onSubmit { Task { await state.createCourse() } }

            let empty = state.newCourseName.trimmingCharacters(in: .whitespaces).isEmpty
            Button("Confirm") { Task { await state.createCourse() } }
                .font(.system(size: 12.5, weight: .medium))
                .foregroundStyle(Color.white)
                .padding(.horizontal, 14)
                .padding(.vertical, 6)
                .background(empty ? cortexAccent.opacity(0.4) : cortexAccent)
                .clipShape(RoundedRectangle(cornerRadius: 6))
                .buttonStyle(.plain)
                .disabled(empty)
        }
        .padding(.top, state.courses.isEmpty ? 0 : 8)
    }
}
