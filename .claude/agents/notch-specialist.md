---
name: notch-specialist
description: Swift/Xcode specialist for the Cortex Drop (NotchDrop fork) phase. Use this agent for all work inside notch/NotchDrop/ — implementing the Cortex module, wiring the drop handler, paste handler, and status pill, and verifying the six-row ingest test matrix.
---

You are working on **Cortex Drop** — a fork of Lakr233/NotchDrop (MIT) that adds passive ingestion to the macOS notch. All Cortex modifications live in `notch/NotchDrop/NotchDrop/Cortex/`. Touch existing NotchDrop files as little as possible.

## Repo location

```
notch/NotchDrop/NotchDrop/Cortex/
├── CortexClient.swift       # Networking — POSTs to /ingest
├── CortexIngest.swift       # NSItemProvider + NSPasteboard extraction
├── CortexSettings.swift     # UserDefaults-backed settings
└── CortexStatusView.swift   # SwiftUI status pill
```

The fork lives at `notch/NotchDrop/`. Clone it with:
```bash
cd notch && git clone https://github.com/Lakr233/NotchDrop.git
```

## First task on every session: discover filenames

Before editing anything, identify these four files by searching the project (do NOT guess filenames):
- `@main` app entry point
- Notch view (search for `NSPanel`, `NSWindow`, `WindowGroup`)
- Tray / drop zone view (search for `onDrop(of:`, `NSItemProvider`, `dropDestination`)
- Settings view (search for `Settings`, `Preferences`, `SettingsView`)

Report the exact filenames before making any edits.

## The four Cortex Swift files

### CortexClient.swift
```swift
import Foundation
import AppKit

enum CortexKind: String { case pdf, image, url, text }

@MainActor
final class CortexClient: ObservableObject {
    static let shared = CortexClient()

    @Published var status: CortexStatus = .idle
    private var resetTask: Task<Void, Never>?

    enum CortexStatus: Equatable {
        case idle
        case sending(progress: Double)
        case success(message: String)
        case error(String)
    }

    var endpoint: URL {
        let base = CortexSettings.shared.backendURL
        return URL(string: "\(base)/ingest")!
    }

    var courseId: Int { CortexSettings.shared.courseId }

    func sendFile(at url: URL) async {
        await setStatus(.sending(progress: 0.1))
        do {
            let data = try Data(contentsOf: url)
            let mime = mimeType(for: url)
            let kind: CortexKind = mime == "application/pdf" ? .pdf : .image
            try await uploadMultipart(data: data, filename: url.lastPathComponent, mime: mime, kind: kind)
            await setStatus(.success(message: "Sent \(url.lastPathComponent)"))
        } catch {
            await setStatus(.error(error.localizedDescription))
        }
    }

    func sendImage(_ image: NSImage) async {
        await setStatus(.sending(progress: 0.1))
        guard let tiff = image.tiffRepresentation,
              let rep = NSBitmapImageRep(data: tiff),
              let png = rep.representation(using: .png, properties: [:]) else {
            await setStatus(.error("Could not encode image"))
            return
        }
        do {
            try await uploadMultipart(data: png,
                                      filename: "pasted-\(UUID().uuidString).png",
                                      mime: "image/png",
                                      kind: .image)
            await setStatus(.success(message: "Sent image"))
        } catch {
            await setStatus(.error(error.localizedDescription))
        }
    }

    func sendURL(_ urlString: String) async {
        await setStatus(.sending(progress: 0.3))
        var req = URLRequest(url: endpoint)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let body: [String: Any] = ["course_id": courseId, "kind": "url", "url": urlString]
        req.httpBody = try? JSONSerialization.data(withJSONObject: body)
        do {
            _ = try await URLSession.shared.data(for: req)
            await setStatus(.success(message: "Sent link"))
        } catch {
            await setStatus(.error(error.localizedDescription))
        }
    }

    func sendText(_ text: String, title: String? = nil) async {
        await setStatus(.sending(progress: 0.3))
        var req = URLRequest(url: endpoint)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let body: [String: Any] = [
            "course_id": courseId,
            "kind": "text",
            "title": title ?? "Pasted text \(Date().ISO8601Format())",
            "text": text
        ]
        req.httpBody = try? JSONSerialization.data(withJSONObject: body)
        do {
            _ = try await URLSession.shared.data(for: req)
            await setStatus(.success(message: "Sent text"))
        } catch {
            await setStatus(.error(error.localizedDescription))
        }
    }

    private func uploadMultipart(data: Data, filename: String, mime: String, kind: CortexKind) async throws {
        let boundary = UUID().uuidString
        var req = URLRequest(url: endpoint)
        req.httpMethod = "POST"
        req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        var body = Data()
        func append(_ s: String) { body.append(s.data(using: .utf8)!) }
        append("--\(boundary)\r\nContent-Disposition: form-data; name=\"course_id\"\r\n\r\n\(courseId)\r\n")
        append("--\(boundary)\r\nContent-Disposition: form-data; name=\"kind\"\r\n\r\n\(kind.rawValue)\r\n")
        append("--\(boundary)\r\nContent-Disposition: form-data; name=\"file\"; filename=\"\(filename)\"\r\nContent-Type: \(mime)\r\n\r\n")
        body.append(data)
        append("\r\n--\(boundary)--\r\n")
        req.httpBody = body
        let (_, resp) = try await URLSession.shared.data(for: req)
        if let http = resp as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
            throw NSError(domain: "Cortex", code: http.statusCode)
        }
    }

    private func mimeType(for url: URL) -> String {
        switch url.pathExtension.lowercased() {
        case "pdf":  return "application/pdf"
        case "png":  return "image/png"
        case "jpg", "jpeg": return "image/jpeg"
        case "gif":  return "image/gif"
        case "heic": return "image/heic"
        case "txt", "md": return "text/plain"
        default:     return "application/octet-stream"
        }
    }

    private func setStatus(_ s: CortexStatus) async {
        await MainActor.run {
            self.status = s
            self.resetTask?.cancel()
            if case .success = s {
                self.resetTask = Task { [weak self] in
                    try? await Task.sleep(nanoseconds: 2_000_000_000)
                    if !Task.isCancelled { self?.status = .idle }
                }
            } else if case .error = s {
                self.resetTask = Task { [weak self] in
                    try? await Task.sleep(nanoseconds: 4_000_000_000)
                    if !Task.isCancelled { self?.status = .idle }
                }
            }
        }
    }
}
```

### CortexSettings.swift
```swift
import Foundation
import Combine

final class CortexSettings: ObservableObject {
    static let shared = CortexSettings()

    @Published var enabled: Bool {
        didSet { UserDefaults.standard.set(enabled, forKey: "cortex.enabled") }
    }
    @Published var backendURL: String {
        didSet { UserDefaults.standard.set(backendURL, forKey: "cortex.backendURL") }
    }
    @Published var courseId: Int {
        didSet { UserDefaults.standard.set(courseId, forKey: "cortex.courseId") }
    }

    private init() {
        self.enabled = UserDefaults.standard.object(forKey: "cortex.enabled") as? Bool ?? true
        self.backendURL = UserDefaults.standard.string(forKey: "cortex.backendURL") ?? "http://localhost:8000"
        self.courseId = UserDefaults.standard.object(forKey: "cortex.courseId") as? Int ?? 1
    }
}
```

### CortexIngest.swift
```swift
import AppKit
import UniformTypeIdentifiers

enum CortexIngest {
    // IMPORTANT: Check image UTIs BEFORE file-url. A browser image drop advertises
    // public.file-url to a temp path that may vanish before we read it.
    // Priority order: image → file-url → web-url → text
    static func handleProviders(_ providers: [NSItemProvider]) -> Bool {
        var handled = false
        for provider in providers {
            // 1) Image data — covers Safari (public.tiff), Chrome (public.png),
            //    and images dragged from browsers that aren't file-backed.
            //    Check BEFORE file-url to avoid the vanishing-temp-file trap.
            if provider.hasItemConformingToTypeIdentifier(UTType.image.identifier) {
                provider.loadDataRepresentation(forTypeIdentifier: UTType.image.identifier) { data, _ in
                    if let data = data, let img = NSImage(data: data) {
                        Task { await CortexClient.shared.sendImage(img) }
                    }
                }
                handled = true
                continue
            }
            // 2) File URL — covers PDFs and image files dragged from Finder
            if provider.canLoadObject(ofClass: URL.self) {
                _ = provider.loadObject(ofClass: URL.self) { url, _ in
                    guard let url = url else { return }
                    if url.isFileURL {
                        Task { await CortexClient.shared.sendFile(at: url) }
                    } else {
                        Task { await CortexClient.shared.sendURL(url.absoluteString) }
                    }
                }
                handled = true
                continue
            }
            // 3) Plain text
            if provider.canLoadObject(ofClass: NSString.self) {
                _ = provider.loadObject(ofClass: NSString.self) { obj, _ in
                    if let s = obj as? String, !s.isEmpty {
                        Task { await CortexClient.shared.sendText(s) }
                    }
                }
                handled = true
                continue
            }
        }
        return handled
    }

    /// Handle a paste from the clipboard (triggered by ⌘V on the notch view).
    /// Priority: image → URL → string
    static func handleClipboard() {
        let pb = NSPasteboard.general

        // Image takes priority (covers Safari TIFF, Chrome PNG, Preview crops)
        if let image = NSImage(pasteboard: pb) {
            Task { await CortexClient.shared.sendImage(image) }
            return
        }
        // URL
        if let urls = pb.readObjects(forClasses: [NSURL.self], options: nil) as? [URL], let url = urls.first {
            if url.isFileURL {
                Task { await CortexClient.shared.sendFile(at: url) }
            } else {
                Task { await CortexClient.shared.sendURL(url.absoluteString) }
            }
            return
        }
        // String — could be a URL-as-string or plain text
        if let s = pb.string(forType: .string), !s.isEmpty {
            if let url = URL(string: s), url.scheme?.hasPrefix("http") == true {
                Task { await CortexClient.shared.sendURL(s) }
            } else {
                Task { await CortexClient.shared.sendText(s) }
            }
            return
        }
        // Debug: log available types if nothing matched
        print("[CortexIngest] Paste produced nothing. Available types: \(pb.types ?? [])")
    }
}
```

### CortexStatusView.swift
```swift
import SwiftUI

struct CortexStatusView: View {
    @ObservedObject var client = CortexClient.shared

    var body: some View {
        HStack(spacing: 6) {
            iconForStatus
            Text(label).font(.system(size: 11)).foregroundColor(.white.opacity(0.85))
        }
        .padding(.horizontal, 8).padding(.vertical, 4)
        .background(background)
        .clipShape(Capsule())
        .opacity(client.status == .idle ? 0 : 1)
        .animation(.easeInOut(duration: 0.2), value: client.status)
    }

    @ViewBuilder private var iconForStatus: some View {
        switch client.status {
        case .idle: EmptyView()
        case .sending: ProgressView().controlSize(.small).tint(.white)
        case .success: Image(systemName: "checkmark.circle.fill").foregroundColor(.green)
        case .error:   Image(systemName: "exclamationmark.triangle.fill").foregroundColor(.orange)
        }
    }

    private var label: String {
        switch client.status {
        case .idle: return ""
        case .sending: return "Sending to Cortex…"
        case .success(let m): return m
        case .error(let m):   return m
        }
    }

    private var background: Color {
        switch client.status {
        case .success: return .black.opacity(0.6)
        case .error:   return .red.opacity(0.6)
        default:       return .black.opacity(0.5)
        }
    }
}
```

## The one surgical edit in existing NotchDrop code

Extract the existing drop logic into `originalHandleDrop(_:)`, then replace the `.onDrop` modifier:

```swift
.onDrop(of: [.fileURL, .url, .image, .text, .plainText], isTargeted: $isTargeted) { providers in
    if CortexSettings.shared.enabled {
        let handled = CortexIngest.handleProviders(providers)
        if handled { return true }
    }
    return originalHandleDrop(providers)
}
```

## Settings section to add

In the existing settings view, add:
```swift
Section("Cortex") {
    Toggle("Send drops to Cortex", isOn: $cortexSettings.enabled)
    TextField("Backend URL", text: $cortexSettings.backendURL)
    Stepper("Active course ID: \(cortexSettings.courseId)", value: $cortexSettings.courseId, in: 1...999)
}
```
Inject `@StateObject var cortexSettings = CortexSettings.shared` at the top of the view.

## ⌘V paste handler

Add to the notch's main view. If the notch isn't a key window, use a global monitor gated on the notch's open state:
```swift
.onAppear {
    NSEvent.addLocalMonitorForEvents(matching: .keyDown) { event in
        if event.modifierFlags.contains(.command) && event.charactersIgnoringModifiers == "v" {
            if CortexSettings.shared.enabled {
                CortexIngest.handleClipboard()
                return nil
            }
        }
        return event
    }
}
```

**Accessibility permission required** for global monitors on macOS 14/15. Check at startup:
```swift
let trusted = AXIsProcessTrustedWithOptions([kAXTrustedCheckOptionPrompt: true] as CFDictionary)
```
Add a README setup step for this.

## Status pill placement

```swift
ZStack(alignment: .bottom) {
    existingNotchContent
    CortexStatusView()
        .padding(.bottom, 8)
}
```

## Six-row acceptance test matrix

All six must produce a `sources` row with correct `source_type` and non-empty `raw_text`:

| Action | Expected source_type |
|--------|---------------------|
| Drag paper.pdf from Finder into notch | `pdf` |
| Drag browser tab URL into notch | `url` |
| Drag image from browser into notch | `image` |
| Copy image (Preview → ⌘C), hover notch, ⌘V | `image` |
| Copy paragraph of text (⌘C), hover notch, ⌘V | `text` |
| Copy URL string (⌘C), hover notch, ⌘V | `url` |

**Do not declare Phase 1 done until all six rows pass.**

## Known pitfalls (from research)

- **UTI ordering bug**: Images dragged from browsers advertise `public.file-url` first pointing to a temp file. Always check image UTIs (`public.image`, `public.png`, `public.tiff`) BEFORE file-url. The CortexIngest.swift above already does this.
- **Safari vs Chrome**: Safari copies images as `public.tiff`, Chrome as `public.png`. Both are covered by `UTType.image.identifier`.
- **NSEvent global monitor + focus**: Global monitors only fire when no other app consumes the event. Paste only works when the notch window is the key window or the event reaches the global monitor. Test with the notch actively visible.
- **Accessibility permission**: macOS 14/15 silently registers but never fires global keyboard monitors without Accessibility permission. Add `AXIsProcessTrustedWithOptions` check.
- **Log UTI types** when a drop or paste produces nothing: `print("[CortexIngest] Available UTIs: \(provider.registeredTypeIdentifiers)")`
- **License**: Keep the original `LICENSE` file in the fork. Add `NOTICE.md` crediting Lakr Aream and NotchDrop.
