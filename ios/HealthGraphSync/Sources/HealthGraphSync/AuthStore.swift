import Foundation
import SwiftUI

/// Holds the Auth0 id_token (the JWT we send to Aura). Persists in Keychain
/// so the user doesn't sign in every launch. Tracks the chosen Aura
/// connection so the RootView knows which screen to show.
@MainActor
final class AuthStore: ObservableObject {
    @Published private(set) var idToken: String?
    @Published private(set) var idTokenExpiresAt: Date?
    @Published var connection: AuraConnection?
    @Published var lastError: String?

    private let tokenAccount = "auth.token"
    private let expiryAccount = "auth.token_expiry"

    init() {
        // Dev mode: synthesise a fake session from Info.plist DEV_AURA_* keys
        // so we can run the sync flow without an Auth0 tenant.
        if AppConfig.isDevMode, let url = AppConfig.devAuraGraphQLURL,
           let key = AppConfig.devAuraAPIKey {
            self.idToken = "dev:" + key  // sentinel prefix so GraphQLClient knows to send x-api-key
            self.idTokenExpiresAt = .distantFuture
            self.connection = AuraConnection(graphqlURL: url)
            return
        }
        self.idToken = Keychain.get(tokenAccount)
        if let raw = Keychain.get(expiryAccount), let secs = TimeInterval(raw) {
            self.idTokenExpiresAt = Date(timeIntervalSince1970: secs)
        }
        self.connection = AuraConnection.current
        // Drop expired tokens so the UI shows the login screen instead of a
        // failing API call.
        if let exp = idTokenExpiresAt, exp < Date().addingTimeInterval(60) {
            logout()
        }
    }

    func signIn() async {
        lastError = nil
        do {
            let (idToken, _, expiresAt) = try await Auth0Client.shared.login()
            Keychain.set(idToken, for: tokenAccount)
            Keychain.set("\(expiresAt.timeIntervalSince1970)", for: expiryAccount)
            self.idToken = idToken
            self.idTokenExpiresAt = expiresAt
        } catch {
            lastError = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        }
    }

    func logout() {
        Keychain.delete(tokenAccount)
        Keychain.delete(expiryAccount)
        AuraConnection.clear()
        idToken = nil
        idTokenExpiresAt = nil
        connection = nil
    }

    func setConnection(_ connection: AuraConnection) {
        AuraConnection.save(url: connection.graphqlURL)
        self.connection = connection
    }
}
