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

    var body: some View {
        ZStack(alignment: .bottom) {
            // Original NotchDrop content — unchanged
            ZStack {
                switch vm.contentType {
                case .normal:
                    HStack(spacing: vm.spacing) {
                        ShareView(vm: vm, type: .airdrop)
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
            .animation(vm.animation, value: vm.contentType)

            // Cortex overlay — course tab + status pill
            VStack(spacing: 4) {
                CortexCourseTab()
                CortexStatusView()
            }
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

#Preview {
    NotchContentView(vm: .init())
        .padding()
        .frame(width: 600, height: 150, alignment: .center)
        .background(.black)
        .preferredColorScheme(.dark)
}
