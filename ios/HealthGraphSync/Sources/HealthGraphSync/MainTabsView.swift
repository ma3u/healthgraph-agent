import SwiftUI

struct MainTabsView: View {
    var body: some View {
        TabView {
            SyncView()
                .tabItem { Label("Sync", systemImage: "arrow.triangle.2.circlepath") }
            DashboardView()
                .tabItem { Label("Dashboard", systemImage: "chart.bar.fill") }
            SettingsView()
                .tabItem { Label("Settings", systemImage: "gearshape") }
        }
    }
}
