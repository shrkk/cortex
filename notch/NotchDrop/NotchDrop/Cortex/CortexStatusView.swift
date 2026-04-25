import SwiftUI

struct CortexStatusView: View {
    @ObservedObject var client = CortexClient.shared

    private var reduceMotion: Bool {
        NSAccessibility.isReduceMotionEnabled
    }

    var body: some View {
        HStack(spacing: 4) {
            iconForStatus
            Text(stateLabel)
                .font(.system(size: 11, weight: .semibold))
                .foregroundColor(.white.opacity(0.90))
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(background)
        .overlay(
            Capsule()
                .strokeBorder(Color.white.opacity(successBorderOpacity), lineWidth: 0.5)
        )
        .clipShape(Capsule())
        .opacity(client.status == .idle ? 0 : 1)
        .animation(reduceMotion ? nil : exitAnimation, value: client.status == .idle)
        .animation(reduceMotion ? nil : entryAnimation, value: client.status != .idle)
        .accessibilityLabel("Cortex status: \(stateLabel)")
    }

    @ViewBuilder private var iconForStatus: some View {
        switch client.status {
        case .idle:
            EmptyView()
        case .sending:
            Image(systemName: "arrow.up.circle")
                .font(.system(size: 12))
                .foregroundColor(.white)
        case .success:
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 12))
                .foregroundColor(Color(nsColor: .systemGreen))
        case .error:
            Image(systemName: "exclamationmark.circle.fill")
                .font(.system(size: 12))
                .foregroundColor(.white)
        }
    }

    private var stateLabel: String {
        switch client.status {
        case .idle:
            return ""
        case .sending:
            return "Sending to Cortex…"
        case .success(let m):
            return m
        case .error:
            return "Upload failed — check settings"
        }
    }

    private var background: Color {
        switch client.status {
        case .idle:
            return .clear
        case .sending:
            // Cortex Indigo #6366F1 at 85% opacity
            return Color(red: 0.388, green: 0.400, blue: 0.945).opacity(0.85)
        case .success:
            // systemGreen at 15% opacity (border adds the definition)
            return Color(nsColor: .systemGreen).opacity(0.15)
        case .error:
            // systemRed at 85% opacity
            return Color(nsColor: .systemRed).opacity(0.85)
        }
    }

    private var successBorderOpacity: Double {
        if case .success = client.status { return 1.0 }
        return 0.0
    }

    // Entry: spring slide-down from top + fade-in
    private var entryAnimation: Animation {
        .spring(response: 0.3, dampingFraction: 0.7)
    }

    // Exit: ease-out fade
    private var exitAnimation: Animation {
        .easeOut(duration: 0.25)
    }
}
