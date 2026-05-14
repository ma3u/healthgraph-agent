import SwiftUI
import WebKit

struct DashboardView: View {
    var body: some View {
        NavigationStack {
            Group {
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
