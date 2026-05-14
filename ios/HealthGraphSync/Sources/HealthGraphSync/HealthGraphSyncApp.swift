import SwiftUI

@main
struct HealthGraphSyncApp: App {
    @StateObject private var auth = AuthStore()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(auth)
        }
    }
}

struct RootView: View {
    @EnvironmentObject private var auth: AuthStore

    var body: some View {
        Group {
            if auth.token == nil {
                LoginView()
            } else {
                MainTabsView()
            }
        }
    }
}
