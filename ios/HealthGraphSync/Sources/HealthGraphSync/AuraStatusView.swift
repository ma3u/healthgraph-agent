import SwiftUI

/// Live Aura instance status + a "Start" button + a connection latency check.
/// The instance is paused most of the time to save money, so the GraphQL Data
/// API is unreachable until it's resumed — this card makes that visible and
/// one-tap fixable. Uses AuraAdmin (AURA_CLIENT_*/AURA_INSTANCEID from Info.plist).
@MainActor
final class AuraStatusModel: ObservableObject {
    enum Status: Equatable { case unknown, checking, running, paused(String), waking, error(String) }

    @Published var status: Status = .unknown
    @Published var latencyMs: Int?
    @Published var pinging = false

    var configured: Bool { AuraAdmin.isConfigured }

    func refresh() async {
        guard configured else { status = .error("admin creds not set"); return }
        status = .checking
        switch await AuraAdmin.currentStatus() {
        case "running": status = .running
        case .some(let s): status = .paused(s)
        case .none: status = .error("status check failed")
        }
    }

    func start() async {
        status = .waking
        let ok = await AuraAdmin.ensureRunning(timeout: 540)
        status = ok ? .running : .error("didn’t finish in time — try again")
    }

    /// Round-trip a trivial GraphQL query to measure live reachability/latency.
    func ping(endpoint: URL?, token: String?) async {
        guard let endpoint, let token else { latencyMs = nil; return }
        pinging = true
        defer { pinging = false }
        let started = Date()
        do {
            let _: String = try await GraphQLClient.shared.run(
                query: "query Ping { __typename }",
                token: token, endpoint: endpoint, decodeUnder: "__typename")
            latencyMs = Int(Date().timeIntervalSince(started) * 1000)
        } catch {
            latencyMs = nil
        }
    }
}

struct AuraStatusCard: View {
    var endpoint: URL?
    var token: String?
    @StateObject private var model = AuraStatusModel()

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                Circle().fill(dotColor).frame(width: 10, height: 10)
                Text(label).font(.subheadline).fontWeight(.semibold)
                Spacer()
                if model.pinging {
                    ProgressView().controlSize(.small)
                } else if let ms = model.latencyMs {
                    Text("\(ms) ms").font(.caption).monospacedDigit()
                        .foregroundStyle(ms < 1500 ? .green : .orange)
                }
            }
            HStack(spacing: 10) {
                if showStart {
                    Button {
                        Task { await model.start(); await model.ping(endpoint: endpoint, token: token) }
                    } label: {
                        Label("Start Aura", systemImage: "play.circle.fill")
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(model.status == .waking)
                }
                Button {
                    Task { await model.refresh(); await model.ping(endpoint: endpoint, token: token) }
                } label: {
                    Label("Check connection", systemImage: "arrow.clockwise")
                }
                .buttonStyle(.bordered)
                .disabled(model.status == .checking || model.pinging)
            }
            .font(.callout)
            if case .waking = model.status {
                Text("Resuming an 8 GB instance can take a few minutes.")
                    .font(.caption2).foregroundStyle(.secondary)
            }
        }
        .task { await model.refresh(); await model.ping(endpoint: endpoint, token: token) }
    }

    private var showStart: Bool {
        guard AuraAdmin.isConfigured else { return false }
        switch model.status {
        case .paused, .error, .unknown: return true
        default: return false
        }
    }

    private var dotColor: Color {
        switch model.status {
        case .running: return .green
        case .paused, .waking: return .orange
        case .checking, .unknown: return .gray
        case .error: return .red
        }
    }

    private var label: String {
        switch model.status {
        case .unknown: return "Aura instance"
        case .checking: return "Checking…"
        case .running: return "Running"
        case .paused(let s): return "Paused (\(s))"
        case .waking: return "Starting…"
        case .error(let e): return "Unavailable — \(e)"
        }
    }
}
