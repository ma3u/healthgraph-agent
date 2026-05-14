import Foundation

/// Tiny URLSession-based GraphQL client. Talks directly to the user's Aura
/// GraphQL Data API endpoint (no backend in the middle). Auth = the Auth0
/// id_token, sent as `Authorization: Bearer ...`.
final class GraphQLClient: @unchecked Sendable {
    static let shared = GraphQLClient()

    private let session: URLSession
    private let encoder: JSONEncoder

    private init() {
        let cfg = URLSessionConfiguration.default
        cfg.waitsForConnectivity = true
        cfg.timeoutIntervalForRequest = 30
        self.session = URLSession(configuration: cfg)

        let enc = JSONEncoder()
        enc.dateEncodingStrategy = .iso8601
        self.encoder = enc
    }

    struct GraphQLError: LocalizedError {
        let message: String
        var errorDescription: String? { message }
    }

    /// Run a query/mutation. `T` decodes the `data.<operation>` value.
    func run<T: Decodable>(
        query: String,
        variables: [String: AnyEncodable] = [:],
        token: String,
        endpoint: URL,
        decodeUnder key: String
    ) async throws -> T {
        var req = URLRequest(url: endpoint)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        let payload = GraphQLRequest(query: query, variables: variables)
        req.httpBody = try encoder.encode(payload)

        let (data, resp) = try await session.data(for: req)

        guard let http = resp as? HTTPURLResponse else {
            throw GraphQLError(message: "Invalid response from \(endpoint.host ?? "?")")
        }
        if http.statusCode == 401 {
            throw GraphQLError(message: "Aura rejected your sign-in — JWT not accepted (check JWKS provider).")
        }
        if !(200..<300).contains(http.statusCode) {
            let body = String(data: data, encoding: .utf8) ?? ""
            throw GraphQLError(message: "HTTP \(http.statusCode): \(body)")
        }

        // GraphQL responses always look like { "data": {...}, "errors": [...] }
        let env = try JSONDecoder().decode(GraphQLEnvelope.self, from: data)
        if let err = env.errors?.first {
            throw GraphQLError(message: err.message)
        }
        guard let dataDict = env.data, let value = dataDict[key] else {
            throw GraphQLError(message: "GraphQL response missing data.\(key)")
        }
        let valueData = try JSONEncoder().encode(value)
        return try JSONDecoder().decode(T.self, from: valueData)
    }
}

private struct GraphQLRequest: Encodable {
    let query: String
    let variables: [String: AnyEncodable]
}

private struct GraphQLEnvelope: Decodable {
    let data: [String: AnyDecodable]?
    let errors: [GraphQLErrorMessage]?
}

private struct GraphQLErrorMessage: Decodable { let message: String }

/// Type-erased Encodable so we can pass mixed variable types in one dict.
struct AnyEncodable: Encodable {
    let value: Encodable

    func encode(to encoder: Encoder) throws {
        try value.encode(to: encoder)
    }
}

/// Type-erased Decodable for parsing variable response shapes.
private struct AnyDecodable: Decodable, Encodable {
    let value: Any

    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if let v = try? c.decode(Bool.self) { value = v }
        else if let v = try? c.decode(Int.self) { value = v }
        else if let v = try? c.decode(Double.self) { value = v }
        else if let v = try? c.decode(String.self) { value = v }
        else if let v = try? c.decode([AnyDecodable].self) { value = v.map { $0.value } }
        else if let v = try? c.decode([String: AnyDecodable].self) {
            value = v.mapValues { $0.value }
        } else if c.decodeNil() { value = NSNull() }
        else { value = NSNull() }
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        switch value {
        case let v as Bool: try c.encode(v)
        case let v as Int: try c.encode(v)
        case let v as Double: try c.encode(v)
        case let v as String: try c.encode(v)
        case let v as [Any]: try c.encode(v.map { AnyDecodable(from: $0) })
        case let v as [String: Any]: try c.encode(v.mapValues { AnyDecodable(from: $0) })
        default: try c.encodeNil()
        }
    }

    init(from any: Any) { self.value = any }
}
