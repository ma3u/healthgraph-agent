import SwiftUI
import WebKit

struct DashboardView: View {
    /// The full Whoop-style static dashboard on GitHub Pages — opened in Safari.
    /// NEODASH_URL is the snapshot dir (…/snapshot/); append dashboard.html to land
    /// on the full dashboard instead of the Recovery landing page.
    private var pagesURL: URL? {
        if let base = AppConfig.neodashURL {
            return base.appendingPathComponent("dashboard.html")
        }
        return AppConfig.auraDashboardURL
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                if AppConfig.isAgentConfigured {
                    AgentChatView()
                    Divider()
                }
                // Native, on-device Whoop-style dashboard — works while Aura is paused.
                OfflineDashboardView()
            }
            .navigationTitle("Today")
            .toolbar {
                if let url = pagesURL {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button {
                            UIApplication.shared.open(url)
                        } label: {
                            Label("Open snapshot (GitHub Pages)", systemImage: "safari")
                        }
                    }
                }
            }
        }
    }
}

struct WebView: UIViewRepresentable {
    let url: URL

    func makeUIView(context: Context) -> WKWebView {
        let view = WKWebView()
        view.load(URLRequest(url: url))
        return view
    }

    func updateUIView(_ view: WKWebView, context: Context) {}
}
