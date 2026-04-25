import AppKit
import UniformTypeIdentifiers

enum CortexIngest {
    // IMPORTANT: Check image UTIs BEFORE file-url. A browser image drop advertises
    // public.file-url to a temp path that may vanish before we read it.
    // Priority order: image → file-url → web-url → text
    static func handleProviders(_ providers: [NSItemProvider]) -> Bool {
        var handled = false
        for provider in providers {
            // Log available UTIs for debugging
            print("[CortexIngest] Available UTIs: \(provider.registeredTypeIdentifiers)")

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
