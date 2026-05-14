import Foundation

enum APIError: LocalizedError {
    case invalidResponse
    case http(Int, String)
    case decoding(String)

    var userFacing: String {
        switch self {
        case .invalidResponse: return "Server returned an unexpected response."
        case .http(401, _): return "Email or password is wrong."
        case .http(let code, let body): return "Server error \(code): \(body)"
        case .decoding(let msg): return "Could not parse server response: \(msg)"
        }
    }

    var errorDescription: String? { userFacing }
}

/// Tiny URLSession-based client. Single shared instance because everything in
/// the app is single-user and we only ever talk to one backend.
///
/// `@unchecked Sendable` is fine here: all stored properties are `let`, and
/// URLSession / JSONDecoder / JSONEncoder are safe for concurrent use from
/// multiple tasks in the way we use them.
final class APIClient: @unchecked Sendable {
    static let shared = APIClient()

    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    private init() {
        let cfg = URLSessionConfiguration.default
        cfg.waitsForConnectivity = true
        cfg.timeoutIntervalForRequest = 30
        cfg.timeoutIntervalForResource = 300
        self.session = URLSession(configuration: cfg)

        self.decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        decoder.keyDecodingStrategy = .convertFromSnakeCase

        self.encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.keyEncodingStrategy = .convertToSnakeCase
    }

    private func url(_ path: String) -> URL {
        AppConfig.apiBaseURL.appendingPathComponent(path)
    }

    /// OAuth2 password flow — backend expects form-encoded body.
    func login(email: String, password: String) async throws -> String {
        var req = URLRequest(url: url("auth/login"))
        req.httpMethod = "POST"
        req.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")

        let bodyParts = [
            "username=\(email.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? email)",
            "password=\(password.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? password)",
        ]
        req.httpBody = bodyParts.joined(separator: "&").data(using: .utf8)

        let (data, resp) = try await session.data(for: req)
        try Self.requireOK(resp, data)

        struct LoginResponse: Decodable {
            let accessToken: String
            let tokenType: String
            let expiresAt: Date
        }
        do {
            return try decoder.decode(LoginResponse.self, from: data).accessToken
        } catch {
            throw APIError.decoding(String(describing: error))
        }
    }

    func syncPreview(token: String) async throws -> SyncPreviewResponse {
        var req = URLRequest(url: url("sync/preview"))
        req.httpMethod = "GET"
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        let (data, resp) = try await session.data(for: req)
        try Self.requireOK(resp, data)
        do {
            return try decoder.decode(SyncPreviewResponse.self, from: data)
        } catch {
            throw APIError.decoding(String(describing: error))
        }
    }

    func ingest(_ payload: IngestPayload, token: String) async throws -> IngestResponse {
        var req = URLRequest(url: url("ingest/healthkit"))
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        req.httpBody = try encoder.encode(payload)

        let (data, resp) = try await session.data(for: req)
        try Self.requireOK(resp, data)
        do {
            return try decoder.decode(IngestResponse.self, from: data)
        } catch {
            throw APIError.decoding(String(describing: error))
        }
    }

    private static func requireOK(_ resp: URLResponse, _ data: Data) throws {
        guard let http = resp as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200..<300).contains(http.statusCode) else {
            let body = String(data: data, encoding: .utf8) ?? ""
            throw APIError.http(http.statusCode, body)
        }
    }
}
