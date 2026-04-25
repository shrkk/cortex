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

    func sendFile(at url: URL) async {
        await setStatus(.sending(progress: 0.1))
        do {
            let hint = url.lastPathComponent
            let courseId = await CortexCourseTabState.shared.sessionCourseId
                ?? (await CortexCourseTabState.shared.resolve(hint: hint))
                ?? 1
            let data = try Data(contentsOf: url)
            let mime = mimeType(for: url)
            let kind: CortexKind = mime == "application/pdf" ? .pdf : .image
            try await uploadMultipart(data: data, filename: url.lastPathComponent, mime: mime, kind: kind, courseId: courseId)
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
            let hint = "pasted-image"
            let courseId = await CortexCourseTabState.shared.sessionCourseId
                ?? (await CortexCourseTabState.shared.resolve(hint: hint))
                ?? 1
            let filename = "pasted-\(UUID().uuidString).png"
            try await uploadMultipart(data: png,
                                      filename: filename,
                                      mime: "image/png",
                                      kind: .image,
                                      courseId: courseId)
            await setStatus(.success(message: "Sent image"))
        } catch {
            await setStatus(.error(error.localizedDescription))
        }
    }

    func sendURL(_ urlString: String) async {
        await setStatus(.sending(progress: 0.3))
        let hint = urlString.components(separatedBy: "/").last ?? urlString
        let courseId = await CortexCourseTabState.shared.sessionCourseId
            ?? (await CortexCourseTabState.shared.resolve(hint: hint))
            ?? 1
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
        let hint = String(text.prefix(200))
        let courseId = await CortexCourseTabState.shared.sessionCourseId
            ?? (await CortexCourseTabState.shared.resolve(hint: hint))
            ?? 1
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

    // MARK: - Course Resolution API

    /// Pre-flight course match — calls GET /courses/match?hint=...
    func matchCourse(hint: String) async -> Int? {
        let encoded = hint.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? ""
        guard let url = URL(string: "\(CortexSettings.shared.backendURL)/courses/match?hint=\(encoded)") else { return nil }
        guard let (data, _) = try? await URLSession.shared.data(from: url) else { return nil }
        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let courseId = json["course_id"] as? Int else { return nil }
        return courseId
    }

    /// Fetch all courses — calls GET /courses
    func fetchCourses() async -> [(id: Int, title: String)] {
        guard let url = URL(string: "\(CortexSettings.shared.backendURL)/courses") else { return [] }
        guard let (data, _) = try? await URLSession.shared.data(from: url) else { return [] }
        guard let arr = try? JSONSerialization.jsonObject(with: data) as? [[String: Any]] else { return [] }
        return arr.compactMap { d in
            guard let id = d["id"] as? Int, let title = d["title"] as? String else { return nil }
            return (id: id, title: title)
        }
    }

    /// Create a new course — calls POST /courses
    func createCourse(title: String) async -> Int {
        var req = URLRequest(url: URL(string: "\(CortexSettings.shared.backendURL)/courses")!)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try? JSONSerialization.data(withJSONObject: ["title": title, "user_id": 1])
        guard let (data, _) = try? await URLSession.shared.data(for: req),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let id = json["id"] as? Int else { return 1 }
        return id
    }

    // MARK: - Private Helpers

    private func uploadMultipart(data: Data, filename: String, mime: String, kind: CortexKind, courseId: Int) async throws {
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
