import SwiftUI

struct MainTabsView: View {
    @StateObject private var sync = SyncCoordinator()
    @State private var selection: Tab = .sync

    enum Tab: Hashable { case sync, dashboard, settings }

    var body: some View {
        TabView(selection: $selection) {
            SyncView()
                .environmentObject(sync)
                .tag(Tab.sync)
                .tabItem { Label("Sync", systemImage: "arrow.triangle.2.circlepath") }
            DashboardView()
                .tag(Tab.dashboard)
                .tabItem { Label("Dashboard", systemImage: "chart.bar.fill") }
            SettingsView()
                .tag(Tab.settings)
                .tabItem { Label("Settings", systemImage: "gearshape") }
        }
        .onChange(of: sync.shouldShowDashboard) { _, newValue in
            if newValue {
                // Small delay so the user sees the "Done" state in the Sync tab first
                Task {
                    try? await Task.sleep(nanoseconds: 800_000_000)
                    await MainActor.run {
                        selection = .dashboard
                        sync.shouldShowDashboard = false
                    }
                }
            }
        }
    }
}
