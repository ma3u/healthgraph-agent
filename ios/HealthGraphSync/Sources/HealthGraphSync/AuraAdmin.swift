import Foundation

/// Headless Aura instance management (resume) for the daily background sync.
/// Uses AURA_CLIENT_ID / AURA_CLIENT_SECRET / AURA_INSTANCEID from Info.plist —
/// the same bring-your-own-Aura, creds-in-the-app pattern as AURA_AGENT_*.
/// Mirrors `scripts/aura_lifecycle.py wake`.
enum AuraAdmin {
    private static let apiRoot = "https://api.neo4j.io/v1"
    private static let tokenURL = URL(string: "https://api.neo4j.io/oauth/token")!

    static var isConfigured: Bool {
        AppConfig.auraClientID != nil && AppConfig.auraClientSecret != nil && AppConfig.auraInstanceID != nil
    }

    /// Resume the instance if it's paused and poll until running (best effort).
    /// Returns true once running, false on timeout/error. Safe when already up.
    static func ensureRunning(timeout: TimeInterval = 90) async -> Bool {
        guard let id = AppConfig.auraInstanceID else { return false }
        do {
            let token = try await fetchToken()
            if (try await status(id: id, token: token)) == "running" { return true }
            _ = try? await post(path: "/instances/\(id)/resume", token: token)
            let deadline = Date().addingTimeInterval(timeout)
            while Date() < deadline {
                try await Task.sleep(nanoseconds: 5_000_000_000)
                if (try? await status(id: id, token: token)) == "running" { return true }
            }
            return false
        } catch {
            return false
        }
    }

    /// Current instance status string (e.g. "running", "paused"), or nil on error.
    static func currentStatus() async -> String? {
        guard let id = AppConfig.auraInstanceID else { return nil }
        do {
            return try await status(id: id, token: try await fetchToken())
        } catch {
            return nil
        }
    }

    private static func fetchToken() async throws -> String {
        guard let cid = AppConfig.auraClientID, let sec = AppConfig.auraClientSecret else {
            throw URLError(.userAuthenticationRequired)
        }
        var req = URLRequest(url: tokenURL)
        req.httpMethod = "POST"
        let creds = Data("\(cid):\(sec)".utf8).base64EncodedString()
        req.setValue("Basic \(creds)", forHTTPHeaderField: "Authorization")
        req.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        req.httpBody = Data("grant_type=client_credentials".utf8)
        let (data, _) = try await URLSession.shared.data(for: req)
        struct TokenResponse: Decodable { let access_token: String }
        return try JSONDecoder().decode(TokenResponse.self, from: data).access_token
    }

    private static func status(id: String, token: String) async throws -> String {
        let (data, _) = try await get(path: "/instances/\(id)", token: token)
        struct Wrap: Decodable { struct D: Decodable { let status: String }; let data: D }
        return try JSONDecoder().decode(Wrap.self, from: data).data.status
    }

    private static func get(path: String, token: String) async throws -> (Data, URLResponse) {
        var req = URLRequest(url: URL(string: apiRoot + path)!)
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        return try await URLSession.shared.data(for: req)
    }

    @discardableResult
    private static func post(path: String, token: String) async throws -> (Data, URLResponse) {
        var req = URLRequest(url: URL(string: apiRoot + path)!)
        req.httpMethod = "POST"
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        return try await URLSession.shared.data(for: req)
    }
}
