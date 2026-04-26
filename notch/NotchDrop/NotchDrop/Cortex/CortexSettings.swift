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
        // Migrate localhost → 127.0.0.1: sandbox blocks DNS, so localhost never resolves
        let stored = UserDefaults.standard.string(forKey: "cortex.backendURL") ?? "http://127.0.0.1:8000"
        self.backendURL = stored.replacingOccurrences(of: "localhost", with: "127.0.0.1")
        self.courseId = UserDefaults.standard.object(forKey: "cortex.courseId") as? Int ?? 1
    }
}
