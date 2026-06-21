import SwiftUI
import WebKit

struct DashboardView: View {
    /// The full live dashboard (NeoDash / Aura Console) — opened in Safari.
    private var liveDashboardURL: URL? { AppConfig.auraDashboardURL ?? AppConfig.neodashURL }

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
                if let url = liveDashboardURL {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button {
                            UIApplication.shared.open(url)
                        } label: {
                            Label("Open full dashboard in Safari", systemImage: "safari")
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
