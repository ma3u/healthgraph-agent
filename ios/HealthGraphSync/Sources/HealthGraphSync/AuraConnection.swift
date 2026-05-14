import Foundation

/// The user's chosen Aura GraphQL Data API endpoint. Persisted in Keychain so
/// it survives app reinstalls of the same identity, but the user can wipe it
/// from the Settings screen.
struct AuraConnection: Codable, Equatable {
    var graphqlURL: URL

    static let keychainAccount = "aura.graphql_url"

    static var current: AuraConnection? {
        guard let raw = Keychain.get(keychainAccount),
              let url = URL(string: raw),
              url.scheme == "https",
              url.host?.contains(".data.neo4j.io") == true
        else { return nil }
        return AuraConnection(graphqlURL: url)
    }

    static func save(url: URL) {
        Keychain.set(url.absoluteString, for: keychainAccount)
    }

    static func clear() {
        Keychain.delete(keychainAccount)
    }
}
