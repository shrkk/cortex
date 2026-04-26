import SwiftUI

struct CortexStatusView: View {
    @ObservedObject var client = CortexClient.shared
    @State private var pulsing = false

    // Design tokens — dark pill palette (per Cortex Design System)
    private static let pillBg   = Color(red: 0.122, green: 0.118, blue: 0.110) // #1F1E1B
    private static let pillFg   = Color(red: 0.980, green: 0.969, blue: 0.949) // #FAF7F2
    private static let dotIdle  = Color(red: 0.604, green: 0.576, blue: 0.533) // #9A9388
    private static let dotSend  = Color(red: 0.757, green: 0.541, blue: 0.247) // #C18A3F amber
    private static let dotSent  = Color(red: 0.420, green: 0.557, blue: 0.353) // #6B8E5A moss
    private static let dotError = Color(red: 0.710, green: 0.376, blue: 0.290) // #B5604A terracotta

    private var reduceMotion: Bool {
        NSWorkspace.shared.accessibilityDisplayShouldReduceMotion
    }

    var body: some View {
        HStack(spacing: 8) {
            dot
            Text(label)
                .font(.system(size: 11.5, design: .monospaced))
                .foregroundStyle(Self.pillFg)
        }
        .padding(.leading, 10)
        .padding(.trailing, 12)
        .padding(.vertical, 5)
        .background(Self.pillBg.opacity(0.92))
        .clipShape(Capsule())
        .shadow(color: .black.opacity(0.20), radius: 1, x: 0, y: 1)
        .shadow(color: .black.opacity(0.18), radius: 12, x: 0, y: 8)
        .accessibilityLabel("Cortex status: \(label)")
    }

    @ViewBuilder private var dot: some View {
        Circle()
            .fill(dotColor)
            .frame(width: 8, height: 8)
            .opacity(isSending && !reduceMotion ? (pulsing ? 0.45 : 1.0) : 1.0)
            .animation(
                isSending && !reduceMotion
                    ? .easeInOut(duration: 0.8).repeatForever(autoreverses: true)
                    : .linear(duration: 0),
                value: pulsing
            )
            .onChange(of: isSending) { _, sending in pulsing = sending }
            .onAppear { pulsing = isSending }
    }

    private var isSending: Bool {
        if case .sending = client.status { return true }
        return false
    }

    private var dotColor: Color {
        switch client.status {
        case .idle:    return Self.dotIdle
        case .sending: return Self.dotSend
        case .success: return Self.dotSent
        case .error:   return Self.dotError
        }
    }

    private var label: String {
        switch client.status {
        case .idle:           return "Cortex"
        case .sending:        return "Sending to Cortex\u{2026}"
        case .success(let m): return m
        case .error:          return "Error \u{2014} retry"
        }
    }
}
