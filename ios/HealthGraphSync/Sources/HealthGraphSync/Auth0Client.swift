import AuthenticationServices
import CryptoKit
import Foundation
import SwiftUI

/// Auth0 OIDC authorization-code-with-PKCE via ASWebAuthenticationSession.
///
/// No Auth0 SDK dependency — we hit the standard `/authorize` and `/oauth/token`
/// endpoints directly. This means the user sees Auth0's universal login sheet
/// with whatever social connections you enabled on the tenant (Apple, Google,
/// GitHub, Microsoft).
///
/// Config (from Info.plist via AppConfig):
///   AUTH0_DOMAIN     "your-tenant.us.auth0.com"
///   AUTH0_CLIENT_ID  "..."
///   AUTH0_AUDIENCE   "https://healthgraph.io/aura"
///
/// Callback URL (registered in Auth0 + URL Types in Info.plist):
///   io.healthgraph.sync://callback
@MainActor
final class Auth0Client {
    static let shared = Auth0Client()

    private let callbackScheme = "io.healthgraph.sync"
    private let callbackURL = "io.healthgraph.sync://callback"

    /// Returns (idToken, accessToken). The id_token is what we send to the
    /// Aura GraphQL Data API as the Bearer JWT; access_token is for Auth0's
    /// /userinfo endpoint if we ever need it.
    func login() async throws -> (idToken: String, accessToken: String, expiresAt: Date) {
        guard !AppConfig.auth0Domain.isEmpty,
              !AppConfig.auth0ClientId.isEmpty
        else { throw Auth0Error.notConfigured }

        let verifier = Self.randomBase64URL(length: 64)
        let challenge = Self.codeChallenge(for: verifier)
        let state = Self.randomBase64URL(length: 32)

        var components = URLComponents()
        components.scheme = "https"
        components.host = AppConfig.auth0Domain
        components.path = "/authorize"
        components.queryItems = [
            URLQueryItem(name: "response_type", value: "code"),
            URLQueryItem(name: "client_id", value: AppConfig.auth0ClientId),
            URLQueryItem(name: "redirect_uri", value: callbackURL),
            URLQueryItem(name: "scope", value: "openid profile email"),
            URLQueryItem(name: "audience", value: AppConfig.auth0Audience),
            URLQueryItem(name: "state", value: state),
            URLQueryItem(name: "code_challenge", value: challenge),
            URLQueryItem(name: "code_challenge_method", value: "S256"),
        ]
        guard let authorizeURL = components.url else { throw Auth0Error.notConfigured }

        let callback = try await Self.runWebAuth(url: authorizeURL, callbackScheme: callbackScheme)

        // Parse the code/state out of the callback URL
        guard let cb = URLComponents(url: callback, resolvingAgainstBaseURL: false),
              let code = cb.queryItems?.first(where: { $0.name == "code" })?.value,
              let returnedState = cb.queryItems?.first(where: { $0.name == "state" })?.value,
              returnedState == state
        else { throw Auth0Error.invalidCallback }

        return try await exchange(code: code, verifier: verifier)
    }

    private func exchange(code: String, verifier: String) async throws -> (String, String, Date) {
        var req = URLRequest(url: URL(string: "https://\(AppConfig.auth0Domain)/oauth/token")!)
        req.httpMethod = "POST"
        req.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        let body = [
            "grant_type=authorization_code",
            "client_id=\(AppConfig.auth0ClientId)",
            "code=\(code)",
            "code_verifier=\(verifier)",
            "redirect_uri=\(callbackURL.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed)!)",
        ].joined(separator: "&")
        req.httpBody = body.data(using: .utf8)

        let (data, resp) = try await URLSession.shared.data(for: req)
        guard let http = resp as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw Auth0Error.tokenExchangeFailed(String(data: data, encoding: .utf8) ?? "")
        }

        struct TokenResponse: Decodable {
            let id_token: String
            let access_token: String
            let expires_in: Int
        }
        let token = try JSONDecoder().decode(TokenResponse.self, from: data)
        let expiresAt = Date().addingTimeInterval(TimeInterval(token.expires_in))
        return (token.id_token, token.access_token, expiresAt)
    }

    // MARK: - Helpers

    private static func runWebAuth(url: URL, callbackScheme: String) async throws -> URL {
        try await withCheckedThrowingContinuation { continuation in
            let session = ASWebAuthenticationSession(
                url: url,
                callbackURLScheme: callbackScheme
            ) { callbackURL, error in
                if let error {
                    continuation.resume(throwing: error)
                } else if let callbackURL {
                    continuation.resume(returning: callbackURL)
                } else {
                    continuation.resume(throwing: Auth0Error.invalidCallback)
                }
            }
            session.presentationContextProvider = WebAuthAnchor.shared
            session.prefersEphemeralWebBrowserSession = false
            if !session.start() {
                continuation.resume(throwing: Auth0Error.sessionFailed)
            }
        }
    }

    private static func randomBase64URL(length: Int) -> String {
        var bytes = [UInt8](repeating: 0, count: length)
        _ = SecRandomCopyBytes(kSecRandomDefault, length, &bytes)
        return Data(bytes).base64URLEncodedString()
    }

    private static func codeChallenge(for verifier: String) -> String {
        let data = Data(verifier.utf8)
        let hash = SHA256.hash(data: data)
        return Data(hash).base64URLEncodedString()
    }
}

enum Auth0Error: LocalizedError {
    case notConfigured
    case invalidCallback
    case sessionFailed
    case tokenExchangeFailed(String)

    var errorDescription: String? {
        switch self {
        case .notConfigured:
            return "Auth0 isn't configured. Set AUTH0_DOMAIN and AUTH0_CLIENT_ID in Info.plist."
        case .invalidCallback:
            return "Auth0 returned an invalid callback URL."
        case .sessionFailed:
            return "Couldn't open the sign-in sheet."
        case .tokenExchangeFailed(let body):
            return "Auth0 token exchange failed: \(body)"
        }
    }
}

private extension Data {
    func base64URLEncodedString() -> String {
        base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }
}

/// ASWebAuthenticationSession needs a window anchor; this hands it the app's
/// active window. Singleton because the API requires NSObject conformance.
private final class WebAuthAnchor: NSObject, ASWebAuthenticationPresentationContextProviding {
    static let shared = WebAuthAnchor()

    func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor {
        UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .flatMap { $0.windows }
            .first { $0.isKeyWindow } ?? ASPresentationAnchor()
    }
}
