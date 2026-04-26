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
        if let id = sessionCourseId { return id }

        if let match = await CortexClient.shared.matchCourse(hint: hint) {
            sessionCourseId = match
            return match
        }

        let fetched = await CortexClient.shared.fetchCourses()
        let lastId  = UserDefaults.standard.integer(forKey: "cortex.lastCourseId")
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
        Group {
            if state.isVisible {
                VStack(alignment: .leading, spacing: 0) {
                    header
                    if state.courses.isEmpty {
                        inputRow(placeholder: "e.g. CS 229", topPadding: 12)
                    } else {
                        courseList
                        Divider().background(panelBorder).padding(.top, 4)
                        newCourseSection
                    }
                }
                .background(panelBg)
                .clipShape(
                    .rect(topLeadingRadius: 0, bottomLeadingRadius: 18,
                          bottomTrailingRadius: 18, topTrailingRadius: 0)
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 18)
                        .strokeBorder(panelBorder, lineWidth: 1)
                )
                .shadow(color: .black.opacity(0.28), radius: 16, x: 0, y: 12)
            }
        }
        .animation(reduceMotion ? nil : .easeInOut(duration: 0.2), value: state.isVisible)
    }

    // MARK: Header

    private var header: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(state.courses.isEmpty ? "Name this course" : "Which course?")
                .font(.system(size: 10.5, weight: .medium))
                .textCase(.uppercase)
                .tracking(0.8)
                .foregroundStyle(panelFgDim)

            Text(state.courses.isEmpty
                 ? "Cortex starts with one course. Give it a name."
                 : "Couldn\u{2019}t place this drop with confidence. Pick a course.")
                .font(.system(size: 14, design: .serif))
                .foregroundStyle(panelFg)
                .lineSpacing(2)
        }
        .padding(.horizontal, 18)
        .padding(.top, 14)
        .padding(.bottom, 8)
    }

    // MARK: Course list (State B)

    private var courseList: some View {
        VStack(spacing: 0) {
            ForEach(state.courses) { course in
                courseRow(course)
            }
        }
        .padding(.horizontal, 8)
        .padding(.bottom, 6)
    }

    private func courseRow(_ course: CortexCourseTabState.CourseOption) -> some View {
        let selected = state.selectedCourseId == course.id
        return Button { state.selectCourse(course.id) } label: {
            HStack(spacing: 10) {
                Circle()
                    .fill(selected ? cortexAccent : panelFgMuted)
                    .frame(width: 6, height: 6)
                Text(course.title)
                    .font(.system(size: 13.5, design: .serif))
                    .fontWeight(.medium)
                    .foregroundStyle(panelFg)
                    .lineLimit(1)
                Spacer()
                if course.concepts > 0 {
                    Text("\(course.concepts)")
                        .font(.system(size: 11, design: .monospaced))
                        .foregroundStyle(panelFgMuted)
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .background(selected ? panelRowSelected : Color.clear)
            .clipShape(RoundedRectangle(cornerRadius: 8))
        }
        .buttonStyle(.plain)
    }

    // MARK: New course / input (State A bottom + State B footer)

    private var newCourseSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            if !state.courses.isEmpty {
                Text("New course\u{2026}")
                    .font(.system(size: 10.5, weight: .medium))
                    .textCase(.uppercase)
                    .tracking(0.8)
                    .foregroundStyle(panelFgDim)
                    .padding(.horizontal, 4)
            }
            inputRow(placeholder: "course name\u{2026}", topPadding: 0)
        }
        .padding(.horizontal, 14)
        .padding(.top, 8)
        .padding(.bottom, 12)
    }

    private func inputRow(placeholder: String, topPadding: CGFloat) -> some View {
        HStack(spacing: 8) {
            TextField(placeholder, text: $state.newCourseName)
                .font(.system(size: 13))
                .foregroundStyle(panelFg)
                .textFieldStyle(.plain)
                .padding(.horizontal, 10)
                .padding(.vertical, 7)
                .background(panelInput)
                .clipShape(RoundedRectangle(cornerRadius: 6))
                .overlay(
                    RoundedRectangle(cornerRadius: 6)
                        .strokeBorder(panelInputBorder, lineWidth: 1)
                )
                .onSubmit { Task { await state.createCourse() } }

            let empty = state.newCourseName.trimmingCharacters(in: .whitespaces).isEmpty
            Button("Confirm") { Task { await state.createCourse() } }
                .font(.system(size: 12.5, weight: .medium))
                .foregroundStyle(Color.white)
                .padding(.horizontal, 14)
                .padding(.vertical, 7)
                .background(empty ? cortexAccent.opacity(0.4) : cortexAccent)
                .clipShape(RoundedRectangle(cornerRadius: 6))
                .buttonStyle(.plain)
                .disabled(empty)
        }
        .padding(.top, topPadding)
        .padding(.horizontal, state.courses.isEmpty ? 14 : 0)
        .padding(.bottom, state.courses.isEmpty ? 12 : 0)
    }
}
