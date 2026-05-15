import Foundation

/// Build-time / runtime configuration read from Info.plist.
///
/// **Production path (Auth0):** set `AUTH0_DOMAIN` + `AUTH0_CLIENT_ID` +
/// `AUTH0_AUDIENCE`. Login flow uses ASWebAuthenticationSession against Auth0
/// universal login, JWT is sent to the Aura GraphQL Data API.
///
/// **Dev-mode (bypass Auth0):** leave `AUTH0_DOMAIN` empty AND set
/// `DEV_AURA_GRAPHQL_URL` + `DEV_AURA_API_KEY`. The app skips the Auth0
/// dance entirely and sends `x-api-key` directly to the Aura GraphQL Data
/// API. Useful while you're setting up Auth0 — not for production builds.
enum AppConfig {
    static var auth0Domain: String {
        (Bundle.main.object(forInfoDictionaryKey: "AUTH0_DOMAIN") as? String) ?? ""
    }

    static var auth0ClientId: String {
        (Bundle.main.object(forInfoDictionaryKey: "AUTH0_CLIENT_ID") as? String) ?? ""
    }

    static var auth0Audience: String {
        (Bundle.main.object(forInfoDictionaryKey: "AUTH0_AUDIENCE") as? String) ?? ""
    }

    static var devAuraGraphQLURL: URL? {
        guard
            let raw = Bundle.main.object(forInfoDictionaryKey: "DEV_AURA_GRAPHQL_URL") as? String,
            !raw.isEmpty
        else { return nil }
        return URL(string: raw)
    }

    static var devAuraAPIKey: String? {
        let raw = (Bundle.main.object(forInfoDictionaryKey: "DEV_AURA_API_KEY") as? String) ?? ""
        return raw.isEmpty ? nil : raw
    }

    /// True when we have everything needed to short-circuit Auth0 for local testing.
    static var isDevMode: Bool {
        auth0Domain.isEmpty && devAuraGraphQLURL != nil && devAuraAPIKey != nil
    }

    static var neodashURL: URL? {
        guard
            let raw = Bundle.main.object(forInfoDictionaryKey: "NEODASH_URL") as? String,
            !raw.isEmpty
        else { return nil }
        return URL(string: raw)
    }

    /// The full Aura Console dashboard URL — opens in Safari (not WebView)
    /// so passkey 2FA flows work. GitHub's passkey login needs full WebAuthn
    /// which WKWebView only partially supports.
    static var auraDashboardURL: URL? {
        guard
            let raw = Bundle.main.object(forInfoDictionaryKey: "AURA_DASHBOARD_URL") as? String,
            !raw.isEmpty
        else { return nil }
        return URL(string: raw)
    }

    static var auraAgentURL: URL? {
        guard
            let raw = Bundle.main.object(forInfoDictionaryKey: "AURA_AGENT_URL") as? String,
            !raw.isEmpty
        else { return nil }
        return URL(string: raw)
    }

    static var auraAgentTokenURL: URL? {
        guard
            let raw = Bundle.main.object(forInfoDictionaryKey: "AURA_AGENT_TOKEN_URL") as? String,
            !raw.isEmpty
        else { return nil }
        return URL(string: raw)
    }

    static var auraAgentClientID: String? {
        let raw = (Bundle.main.object(forInfoDictionaryKey: "AURA_AGENT_CLIENT_ID") as? String) ?? ""
        return raw.isEmpty ? nil : raw
    }

    static var auraAgentClientSecret: String? {
        let raw = (Bundle.main.object(forInfoDictionaryKey: "AURA_AGENT_CLIENT_SECRET") as? String) ?? ""
        return raw.isEmpty ? nil : raw
    }

    static var isAgentConfigured: Bool {
        auraAgentURL != nil
            && auraAgentTokenURL != nil
            && auraAgentClientID != nil
            && auraAgentClientSecret != nil
    }
}
