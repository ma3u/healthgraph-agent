import SwiftUI
import WebKit

struct DashboardView: View {
    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                if AppConfig.isAgentConfigured {
                    AgentChatView()
                    Divider()
                }
                if let url = AppConfig.neodashURL {
                    WebView(url: url)
                        .ignoresSafeArea(edges: .bottom)
                } else {
                    ContentUnavailableView(
                        "No dashboard URL configured",
                        systemImage: "chart.bar.xaxis",
                        description: Text("Set NEODASH_URL in Info.plist to embed your dashboard here.")
                    )
                }
            }
            .navigationTitle("Dashboard")
            .toolbar {
                if let auraURL = AppConfig.auraDashboardURL {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button {
                            UIApplication.shared.open(auraURL)
                        } label: {
                            Label("Open Whoop dashboard in Safari", systemImage: "safari")
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
