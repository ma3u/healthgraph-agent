import Foundation

/// Build-time / runtime configuration. For a hackathon app we read these from
/// the bundle's Info.plist so they can be overridden per-build (debug vs release)
/// without touching code.
///
/// Keys you must set in Info.plist (see ios/project.yml):
///   API_BASE_URL   e.g. "https://healthgraph.example.com"
///   NEODASH_URL    e.g. "https://neodash.example.com/?dashboardName=Whoop"
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

    static var neodashURL: URL? {
        guard
            let raw = Bundle.main.object(forInfoDictionaryKey: "NEODASH_URL") as? String,
            !raw.isEmpty
        else { return nil }
        return URL(string: raw)
    }
}
