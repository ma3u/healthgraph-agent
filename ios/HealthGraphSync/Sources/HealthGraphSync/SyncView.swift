import SwiftUI

struct SyncView: View {
    @EnvironmentObject private var auth: AuthStore
    @StateObject private var sync = SyncCoordinator()

    var body: some View {
        NavigationStack {
            List {
                Section("Sync to Aura") {
                    Button("Initial sync (full history)") {
                        guard let token = auth.token else { return }
                        Task { await sync.runInitial(token: token) }
                    }
                    Button("Incremental sync (since last)") {
                        guard let token = auth.token else { return }
                        Task { await sync.runIncremental(token: token) }
                    }
                }

                Section("Status") {
                    statusView
                }

                if let resp = sync.lastResponse {
                    Section("Last response") {
                        LabeledContent("Samples", value: "\(resp.acceptedSamples)")
                        LabeledContent("Workouts", value: "\(resp.acceptedWorkouts)")
                        LabeledContent("Days touched", value: "\(resp.daysAffected.count)")
                    }
                }
            }
            .navigationTitle("Sync")
        }
    }

    @ViewBuilder
    private var statusView: some View {
        switch sync.phase {
        case .idle:
            Text("Idle").foregroundStyle(.secondary)
        case .initial(let p):
            VStack(alignment: .leading, spacing: 8) {
                Text("Initial sync…")
                ProgressView(value: p)
            }
        case .incremental:
            HStack { ProgressView(); Text("Incremental sync…") }
        case .error(let msg):
            Text(msg).foregroundStyle(.red)
        case .done(let samples, let days):
            Text("Done — \(samples) samples across \(days) days").foregroundStyle(.green)
        }
    }
}
