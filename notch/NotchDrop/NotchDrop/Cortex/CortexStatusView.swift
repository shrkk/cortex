import SwiftUI

// MARK: - Design tokens (dark notch palette)

private let pillBg     = Color(red: 0.122, green: 0.118, blue: 0.110).opacity(0.92) // #1F1E1B
private let pillFg     = Color(red: 0.980, green: 0.969, blue: 0.949)               // #FAF7F2
private let dotIdle    = Color(red: 0.604, green: 0.576, blue: 0.533)               // #9A9388
private let dotSend    = Color(red: 0.757, green: 0.541, blue: 0.247)               // #C18A3F amber
private let dotSent    = Color(red: 0.420, green: 0.557, blue: 0.353)               // #6B8E5A moss
private let dotError   = Color(red: 0.710, green: 0.376, blue: 0.290)               // #B5604A terracotta-red
private let menuPanelBg    = Color(red: 0.078, green: 0.071, blue: 0.059).opacity(0.94) // #14120F
private let menuPanelFg    = Color(red: 0.949, green: 0.929, blue: 0.898)               // #F2EDE3
private let menuPanelFgDim = Color(red: 0.949, green: 0.929, blue: 0.898).opacity(0.45)
private let menuPanelFgMuted = Color(red: 0.949, green: 0.929, blue: 0.898).opacity(0.50)
private let menuPanelBorder = Color.white.opacity(0.06)
private let menuPanelRowHover = Color.white.opacity(0.04)
private let cortexAccentColor = Color(red: 0.788, green: 0.392, blue: 0.259) // #C96442

// MARK: - CortexStatusView

/// Renders a VStack: expanded panel on top, status pill below.
/// The pill is tappable to toggle the panel.
struct CortexStatusView: View {
    @ObservedObject var client = CortexClient.shared
    @State private var pulsing = false

    private var reduceMotion: Bool {
        NSWorkspace.shared.accessibilityDisplayShouldReduceMotion
    }

    var body: some View {
        VStack(spacing: 0) {
            // Expanded panel sits above the pill
            if client.menuExpanded {
                CortexMenuPanel()
                    .transition(
                        reduceMotion
                            ? .opacity
                            : .opacity.combined(with: .move(edge: .bottom))
                    )
            }

            // Status pill
            pill
        }
        .animation(reduceMotion ? nil : .easeInOut(duration: 0.2), value: client.menuExpanded)
    }

    // MARK: - Pill

    private var pill: some View {
        Button(action: { client.menuExpanded.toggle() }) {
            HStack(spacing: 8) {
                dot
                Text(label)
                    .font(.system(size: 11.5, design: .monospaced))
                    .foregroundStyle(pillFg)
            }
            .padding(.leading, 10)
            .padding(.trailing, 12)
            .padding(.vertical, 5)
            .background(pillBg)
            .clipShape(Capsule())
            .shadow(color: .black.opacity(0.20), radius: 1, x: 0, y: 1)
            .shadow(color: .black.opacity(0.18), radius: 12, x: 0, y: 8)
        }
        .buttonStyle(.plain)
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
            .onChange(of: isSending) { sending in pulsing = sending }
            .onAppear { pulsing = isSending }
    }

    private var isSending: Bool {
        if case .sending = client.status { return true }
        return false
    }

    private var dotColor: Color {
        switch client.status {
        case .idle:    return dotIdle
        case .sending: return dotSend
        case .success: return dotSent
        case .error:   return dotError
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

// MARK: - CortexMenuPanel

private struct CortexMenuPanel: View {
    @ObservedObject var client = CortexClient.shared

    var body: some View {
        VStack(spacing: 0) {
            // Active send header (only if currently sending)
            if case .sending = client.status {
                sendingHeader
                Divider().background(menuPanelBorder)
            }

            // Recent drops list
            recentSection

            Divider().background(menuPanelBorder)

            // Footer
            footer
        }
        .frame(width: 340)
        .background(menuPanelBg)
        .clipShape(
            .rect(
                topLeadingRadius: 0,
                bottomLeadingRadius: 18,
                bottomTrailingRadius: 18,
                topTrailingRadius: 0
            )
        )
        .overlay(
            RoundedRectangle(cornerRadius: 18)
                .strokeBorder(menuPanelBorder, lineWidth: 1)
        )
        .shadow(color: .black.opacity(0.28), radius: 16, x: 0, y: 12)
    }

    // MARK: Sending header

    private var sendingHeader: some View {
        HStack(spacing: 10) {
            Circle()
                .fill(dotSend)
                .frame(width: 8, height: 8)
            Text("Reading 1 source")
                .font(.system(size: 12.5, weight: .medium))
                .foregroundStyle(menuPanelFg)
            Spacer()
            Text("about a minute")
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(menuPanelFgMuted)
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 12)
    }

    // MARK: Recent drops

    private var recentSection: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("Recent drops")
                .font(.system(size: 10.5, weight: .medium))
                .textCase(.uppercase)
                .tracking(0.8)
                .foregroundStyle(menuPanelFgDim)
                .padding(.horizontal, 12)
                .padding(.top, 8)
                .padding(.bottom, 4)

            if client.recentDrops.isEmpty {
                Text("No recent drops.")
                    .font(.system(size: 12, design: .serif))
                    .foregroundStyle(menuPanelFgMuted)
                    .padding(.horizontal, 12)
                    .padding(.bottom, 10)
                    .frame(maxWidth: .infinity, alignment: .leading)
            } else {
                ForEach(client.recentDrops) { drop in
                    DropRow(drop: drop)
                }
            }
        }
        .padding(.horizontal, 8)
        .padding(.bottom, 2)
    }

    // MARK: Footer

    private var footer: some View {
        HStack {
            Spacer()
            Button("Open Cortex \u{2192}") {
                NSWorkspace.shared.open(URL(string: "http://localhost:3000")!)
                client.menuExpanded = false
            }
            .font(.system(size: 11.5))
            .foregroundStyle(cortexAccentColor)
            .buttonStyle(.plain)
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 10)
    }
}

// MARK: - DropRow

private struct DropRow: View {
    let drop: RecentDrop
    @State private var hovered = false

    var body: some View {
        HStack(spacing: 12) {
            // Type badge
            ZStack {
                RoundedRectangle(cornerRadius: 3)
                    .strokeBorder(Color.white.opacity(0.12), lineWidth: 1)
                Text(drop.typeBadge)
                    .font(.system(size: 8, design: .monospaced))
                    .foregroundStyle(menuPanelFgDim)
            }
            .frame(width: 22, height: 28)

            // Title + meta
            VStack(alignment: .leading, spacing: 1) {
                Text(drop.title)
                    .font(.system(size: 13.5, design: .serif))
                    .foregroundStyle(menuPanelFg)
                    .lineLimit(1)
                    .truncationMode(.tail)

                HStack(spacing: 4) {
                    Text(drop.courseName)
                    if drop.conceptCount > 0 {
                        Text("\u{B7} \(drop.conceptCount) concepts")
                    }
                    Text("\u{B7} \(drop.timeAgo)")
                }
                .font(.system(size: 11))
                .foregroundStyle(menuPanelFgMuted)
            }

            Spacer(minLength: 0)

            // State dot (always "done" / moss green for items in the recent list)
            Circle()
                .fill(dotSent)
                .frame(width: 6, height: 6)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(hovered ? menuPanelRowHover : Color.clear)
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .onHover { hovered = $0 }
    }
}
