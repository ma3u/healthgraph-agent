import Foundation
import SwiftUI

@MainActor
final class AuthStore: ObservableObject {
    @Published private(set) var token: String?
    @Published private(set) var email: String?
    @Published var lastError: String?

    private let tokenAccount = "auth.token"
    private let emailAccount = "auth.email"

    init() {
        self.token = Keychain.get(tokenAccount)
        self.email = Keychain.get(emailAccount)
    }

    func login(email: String, password: String) async {
        lastError = nil
        do {
            let token = try await APIClient.shared.login(email: email, password: password)
            Keychain.set(token, for: tokenAccount)
            Keychain.set(email, for: emailAccount)
            self.token = token
            self.email = email
        } catch {
            lastError = (error as? APIError)?.userFacing ?? error.localizedDescription
        }
    }

    func logout() {
        Keychain.delete(tokenAccount)
        Keychain.delete(emailAccount)
        token = nil
        email = nil
    }
}
