import SwiftUI
import UIKit

/// Registers the daily background-sync task before the app finishes launching
/// (BGTaskScheduler requires registration at launch).
final class AppDelegate: NSObject, UIApplicationDelegate {
    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        DailySync.register()
        DailySync.schedule()
        return true
    }
}

@main
struct HealthGraphSyncApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var auth = AuthStore()
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(auth)
        }
        .onChange(of: scenePhase) { _, phase in
            if phase == .background { DailySync.schedule() }
        }
    }
}

struct RootView: View {
    @EnvironmentObject private var auth: AuthStore

    var body: some View {
        Group {
            if auth.idToken == nil {
                LoginView()
            } else if auth.connection == nil {
                ConnectView()
            } else {
                MainTabsView()
            }
        }
    }
}
