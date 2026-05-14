import SwiftUI
import UIKit

/// Shown after Auth0 sign-in if no Aura GraphQL endpoint is configured.
/// User pastes (or clicks "Paste from clipboard") their personal Aura
/// GraphQL Data API URL from console.neo4j.io.
struct ConnectView: View {
    @EnvironmentObject private var auth: AuthStore
    @State private var endpointText = ""
    @State private var clipboardCandidate: String?
    @State private var isValidating = false
    @State private var validationError: String?

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Text("Connect your Aura instance")
                        .font(.title2).bold()
                    Text(
                        "Open Aura Console → GraphQL Data APIs → your API → " +
                        "copy the endpoint URL. It looks like " +
                        "`https://<id>.<region>.data.neo4j.io/graphql`."
                    )
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                }

                Section("Endpoint URL") {
                    TextField("https://….data.neo4j.io/graphql", text: $endpointText)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .keyboardType(.URL)
                        .textContentType(.URL)

                    if let candidate = clipboardCandidate {
                        Button {
                            endpointText = candidate
                            clipboardCandidate = nil
                        } label: {
                            Label("Paste from clipboard", systemImage: "doc.on.clipboard")
                        }
                    }
                }

                if let err = validationError {
                    Section { Text(err).foregroundStyle(.red) }
                }

                Section {
                    Button {
                        Task { await validateAndSave() }
                    } label: {
                        if isValidating {
                            HStack { ProgressView(); Text("Checking…") }
                        } else {
                            Text("Connect")
                        }
                    }
                    .disabled(endpointText.isEmpty || isValidating)
                }

                Section {
                    Button("Sign out", role: .destructive) { auth.logout() }
                }
            }
            .navigationTitle("Aura")
            .task { checkClipboard() }
        }
    }

    private func checkClipboard() {
        if UIPasteboard.general.hasURLs,
           let url = UIPasteboard.general.url,
           url.host?.contains("data.neo4j.io") == true {
            clipboardCandidate = url.absoluteString
        } else if UIPasteboard.general.hasStrings,
                  let s = UIPasteboard.general.string,
                  s.contains("data.neo4j.io") {
            clipboardCandidate = s.trimmingCharacters(in: .whitespacesAndNewlines)
        }
    }

    private func validateAndSave() async {
        validationError = nil
        isValidating = true
        defer { isValidating = false }

        guard let url = URL(string: endpointText.trimmingCharacters(in: .whitespacesAndNewlines)),
              url.scheme == "https",
              url.host?.contains("data.neo4j.io") == true
        else {
            validationError = "That doesn't look like an Aura GraphQL endpoint."
            return
        }
        guard let token = auth.idToken else {
            validationError = "Sign in again — your session expired."
            return
        }

        // Probe: a trivial query to confirm the endpoint + JWT work
        do {
            struct ProbeResult: Decodable { let __typename: String? }
            // __typename is always valid against the root Query type.
            _ = try await GraphQLClient.shared.run(
                query: "{ __typename }",
                variables: [:],
                token: token,
                endpoint: url,
                decodeUnder: "__typename"
            ) as String
            auth.setConnection(AuraConnection(graphqlURL: url))
        } catch {
            validationError = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        }
    }
}
