import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var auth: AuthStore

    var body: some View {
        NavigationStack {
            List {
                Section("Aura connection") {
                    LabeledContent("GraphQL endpoint",
                                   value: auth.connection?.graphqlURL.host ?? "—")
                    Button("Forget endpoint", role: .destructive) {
                        AuraConnection.clear()
                        auth.connection = nil
                    }
                }
                Section("Account") {
                    if let exp = auth.idTokenExpiresAt {
                        LabeledContent("Session expires",
                                       value: exp.formatted(date: .abbreviated, time: .shortened))
                    }
                    Button("Sign out", role: .destructive) { auth.logout() }
                }
                Section {
                    Text("HealthGraphSync v0.2 — Aura Agent Hackathon")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Settings")
        }
    }
}
