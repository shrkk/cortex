//
//  NotchContentView.swift
//  NotchDrop
//
//  Created by 秋星桥 on 2024/7/7.
//  Last Modified by 冷月 on 2025/5/5.
//

import ColorfulX
import SwiftUI
import UniformTypeIdentifiers

struct NotchContentView: View {
    @StateObject var vm: NotchViewModel
    @ObservedObject private var courseState = CortexCourseTabState.shared

    var body: some View {
        ZStack(alignment: .bottom) {
            // Main content — replaced by course picker when active
            ZStack {
                if courseState.isVisible {
                    CortexCourseTab()
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                        .transition(.opacity.combined(with: .scale(scale: 0.97)))
                } else {
                    switch vm.contentType {
                    case .normal:
                        HStack(spacing: vm.spacing) {
                            CortexPastePanel(vm: vm)
                            TrayView(vm: vm)
                        }
                        .transition(.scale(scale: 0.8).combined(with: .opacity))
                    case .menu:
                        NotchMenuView(vm: vm)
                            .transition(.scale(scale: 0.8).combined(with: .opacity))
                    case .settings:
                        NotchSettingsView(vm: vm)
                            .transition(.scale(scale: 0.8).combined(with: .opacity))
                    }
                }
            }
            .animation(.easeInOut(duration: 0.18), value: courseState.isVisible)
            .animation(vm.animation, value: vm.contentType)

            // Status pill — always visible
            CortexStatusView()
                .padding(.bottom, 8)
        }
        .onAppear {
            // ⌘V paste handler — fires when notch window is key window
            NSEvent.addLocalMonitorForEvents(matching: .keyDown) { event in
                if event.modifierFlags.contains(.command),
                   event.charactersIgnoringModifiers == "v" {
                    #if CORTEX_ENABLED
                    if CortexSettings.shared.enabled {
                        CortexIngest.handleClipboard()
                        return nil
                    }
                    #endif
                }
                return event
            }
        }
    }
}

// MARK: - Cortex Paste Panel

private struct CortexPastePanel: View {
    @StateObject var vm: NotchViewModel
    @State private var hover = false

    private let accent = Color(red: 0.788, green: 0.392, blue: 0.259) // #C96442 terracotta
    private let panelBg = Color(red: 0.122, green: 0.118, blue: 0.110) // #1F1E1B
    private let panelFg = Color(red: 0.949, green: 0.929, blue: 0.898) // #F2EDE3

    var body: some View {
        panelBg
            .overlay(
                VStack(spacing: 6) {
                    Image(systemName: "doc.on.clipboard")
                        .font(.system(size: 20, weight: .light))
                    Text("Paste")
                        .font(.system(.headline, design: .rounded))
                    Text("URL or image")
                        .font(.system(size: 10, weight: .regular, design: .rounded))
                        .opacity(0.55)
                }
                .foregroundStyle(hover ? accent : panelFg)
                .scaleEffect(hover ? 1.05 : 1)
                .animation(.spring(duration: 0.18), value: hover)
            )
            .clipShape(RoundedRectangle(cornerRadius: vm.cornerRadius))
            .aspectRatio(1, contentMode: .fit)
            .contentShape(Rectangle())
            .onHover { hover = $0 }
            .onTapGesture {
                #if CORTEX_ENABLED
                CortexIngest.handleClipboard()
                #endif
            }
            .onDrop(of: [.data], isTargeted: nil) { providers in
                #if CORTEX_ENABLED
                return CortexIngest.handleProviders(providers)
                #else
                return false
                #endif
            }
    }
}

#Preview {
    NotchContentView(vm: .init())
        .padding()
        .frame(width: 600, height: 150, alignment: .center)
        .background(.black)
        .preferredColorScheme(.dark)
}
