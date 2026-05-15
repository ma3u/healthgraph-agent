import Foundation

/// Calls the Aura Agent REST endpoint. OAuth2 client credentials grant —
/// the agent has its own client_id/secret separate from Auth0 (Auth0 is for
/// the user, Aura Agent creds are for the app talking to the agent).
///
/// Flow:
///   1. POST client_id/secret to `AURA_AGENT_TOKEN_URL` → access_token
///   2. POST `{ question }` to `AURA_AGENT_URL` with `Authorization: Bearer <token>`
///
/// Response shape is best-guess — Aura Agent REST is documented as
/// `{ answer: string, trace?: [...] }` but we fall back to decoding the
/// raw JSON body if the expected shape is missing.
actor AgentClient {
    static let shared = AgentClient()

    private let session: URLSession
    private var cachedToken: String?
    private var tokenExpiry: Date?

    private init() {
        let cfg = URLSessionConfiguration.default
        cfg.waitsForConnectivity = true
        cfg.timeoutIntervalForRequest = 60  // LLM answers can take >5s
        self.session = URLSession(configuration: cfg)
    }

    struct AgentError: LocalizedError {
        let message: String
        var errorDescription: String? { message }
    }

    /// Ask the agent a question. Returns the answer text.
    func ask(_ question: String) async throws -> String {
        guard
            let agentURL = AppConfig.auraAgentURL,
            let tokenURL = AppConfig.auraAgentTokenURL,
            let clientID = AppConfig.auraAgentClientID,
            let clientSecret = AppConfig.auraAgentClientSecret
        else {
            throw AgentError(message: "Aura Agent not configured. Set AURA_AGENT_* in .env.")
        }

        let token = try await accessToken(
            tokenURL: tokenURL, clientID: clientID, clientSecret: clientSecret
        )

        var req = URLRequest(url: agentURL)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        req.httpBody = try JSONEncoder().encode(["input": question])

        let (data, resp) = try await session.data(for: req)
        guard let http = resp as? HTTPURLResponse else {
            throw AgentError(message: "Invalid response from agent")
        }
        if !(200..<300).contains(http.statusCode) {
            let body = String(data: data, encoding: .utf8) ?? ""
            throw AgentError(message: "Agent HTTP \(http.statusCode): \(body)")
        }

        if let parsed = try? JSONDecoder().decode(InvokeAgentResponse.self, from: data) {
            let textBlocks = parsed.content?
                .filter { $0.type == "text" }
                .compactMap { $0.text }
                .joined(separator: "\n\n")
            if let textBlocks, !textBlocks.isEmpty {
                return textBlocks
            }
        }
        return String(data: data, encoding: .utf8) ?? "(empty response)"
    }

    /// Aura's OAuth token endpoint requires HTTP Basic Auth with
    /// `Authorization: Basic base64(client_id:client_secret)` and a
    /// minimal `grant_type=client_credentials` body — sending the creds in
    /// the body instead is rejected.
    private func accessToken(tokenURL: URL, clientID: String, clientSecret: String) async throws -> String {
        if let token = cachedToken, let exp = tokenExpiry, exp > Date().addingTimeInterval(30) {
            return token
        }

        var req = URLRequest(url: tokenURL)
        req.httpMethod = "POST"
        req.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        let basic = Data("\(clientID):\(clientSecret)".utf8).base64EncodedString()
        req.setValue("Basic \(basic)", forHTTPHeaderField: "Authorization")
        req.httpBody = "grant_type=client_credentials".data(using: .utf8)

        let (data, resp) = try await session.data(for: req)
        guard let http = resp as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            let bodyStr = String(data: data, encoding: .utf8) ?? ""
            throw AgentError(message: "Token endpoint rejected client credentials: \(bodyStr)")
        }

        let token = try JSONDecoder().decode(TokenResponse.self, from: data)
        cachedToken = token.accessToken
        tokenExpiry = Date().addingTimeInterval(TimeInterval(token.expiresIn ?? 3600))
        return token.accessToken
    }
}

private struct TokenResponse: Decodable {
    let accessToken: String
    let expiresIn: Int?

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case expiresIn = "expires_in"
    }
}

private struct InvokeAgentResponse: Decodable {
    let type: String?
    let role: String?
    let content: [InvokeAgentContent]?
}

private struct InvokeAgentContent: Decodable {
    let type: String
    let text: String?
}
