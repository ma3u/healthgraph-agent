import SwiftUI

struct LoginView: View {
    @EnvironmentObject private var auth: AuthStore
    @State private var isSigningIn = false

    var body: some View {
        VStack(spacing: 32) {
            Spacer()

            Image("AppIcon-Preview")
                .resizable()
                .frame(width: 128, height: 128)
                .cornerRadius(28)
                .shadow(radius: 20, y: 10)

            VStack(spacing: 8) {
                Text("HealthGraph Sync")
                    .font(.largeTitle).bold()
                Text("Apple Health → your own Neo4j Aura")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }

            Spacer()

            VStack(spacing: 12) {
                Button {
                    Task {
                        isSigningIn = true
                        await auth.signIn()
                        isSigningIn = false
                    }
                } label: {
                    HStack {
                        if isSigningIn {
                            ProgressView().tint(.white)
                        } else {
                            Image(systemName: "lock.shield")
                        }
                        Text("Continue")
                            .fontWeight(.semibold)
                    }
                    .frame(maxWidth: .infinity, minHeight: 50)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .disabled(isSigningIn)

                Text("Sign in with **Apple**, **Google**, **GitHub**, or **Microsoft**.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }

            if let err = auth.lastError {
                Text(err)
                    .foregroundStyle(.red)
                    .font(.footnote)
                    .padding(.horizontal)
                    .multilineTextAlignment(.center)
            }

            Spacer()

            Text("Each user brings their own Aura instance.\nThis app never connects to a shared server.")
                .font(.caption2)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)
                .padding(.bottom, 12)
        }
        .padding()
    }
}
