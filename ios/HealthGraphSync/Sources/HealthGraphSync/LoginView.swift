import SwiftUI

struct LoginView: View {
    @EnvironmentObject private var auth: AuthStore
    @State private var email = ""
    @State private var password = ""
    @State private var isSubmitting = false

    var body: some View {
        NavigationStack {
            Form {
                Section("Sign in to your sync backend") {
                    TextField("Email", text: $email)
                        .keyboardType(.emailAddress)
                        .textContentType(.username)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    SecureField("Password", text: $password)
                        .textContentType(.password)
                }
                if let err = auth.lastError {
                    Section { Text(err).foregroundStyle(.red) }
                }
                Section {
                    Button {
                        Task {
                            isSubmitting = true
                            await auth.login(email: email, password: password)
                            isSubmitting = false
                        }
                    } label: {
                        if isSubmitting {
                            ProgressView()
                        } else {
                            Text("Sign in")
                        }
                    }
                    .disabled(email.isEmpty || password.isEmpty || isSubmitting)
                }
                Section("Server") {
                    Text(AppConfig.apiBaseURL.absoluteString)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .navigationTitle("HealthGraph Sync")
        }
    }
}
