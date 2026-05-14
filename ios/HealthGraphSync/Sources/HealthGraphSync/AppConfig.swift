import Foundation

/// Build-time / runtime configuration. For a hackathon app we read these from
/// the bundle's Info.plist so they can be overridden per-build (debug vs release)
/// without touching code.
///
/// Keys you must set in Info.plist (see ios/project.yml):
///   API_BASE_URL   e.g. "https://healthgraph.example.com"
///   NEODASH_URL    e.g. "https://neodash.example.com/?dashboardName=Whoop"
enum AppConfig {
    static var apiBaseURL: URL {
        guard
            let raw = Bundle.main.object(forInfoDictionaryKey: "API_BASE_URL") as? String,
            let url = URL(string: raw)
        else {
            fatalError("API_BASE_URL missing or invalid in Info.plist")
        }
        return url
    }

    static var neodashURL: URL? {
        guard
            let raw = Bundle.main.object(forInfoDictionaryKey: "NEODASH_URL") as? String,
            !raw.isEmpty
        else { return nil }
        return URL(string: raw)
    }
}
