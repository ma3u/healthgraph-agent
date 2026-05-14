import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var auth: AuthStore

    var body: some View {
        NavigationStack {
            List {
                Section("Account") {
                    LabeledContent("Signed in as", value: auth.email ?? "—")
                    Button("Sign out", role: .destructive) { auth.logout() }
                }
                Section("Server") {
                    LabeledContent("API", value: AppConfig.apiBaseURL.absoluteString)
                    LabeledContent("Dashboard", value: AppConfig.neodashURL?.absoluteString ?? "—")
                        .lineLimit(1)
                        .truncationMode(.middle)
                }
                Section {
                    Text("HealthGraphSync v0.1 — Aura Agent Hackathon")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Settings")
        }
    }
}
