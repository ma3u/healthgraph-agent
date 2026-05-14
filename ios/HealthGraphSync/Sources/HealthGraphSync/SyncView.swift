import SwiftUI

struct SyncView: View {
    @EnvironmentObject private var auth: AuthStore
    @EnvironmentObject private var sync: SyncCoordinator

    var body: some View {
        NavigationStack {
            List {
                Section("Sync to Aura") {
                    Button {
                        guard let token = auth.token else { return }
                        Task { await sync.loadPreview(token: token) }
                    } label: {
                        Label("Check what's missing", systemImage: "magnifyingglass")
                    }
                    .disabled(isBusy)
                }

                if let preview = sync.auraPreview {
                    Section("Currently in Aura") {
                        LabeledContent("Latest day", value: preview.latestDayInAura ?? "—")
                        LabeledContent("Total days", value: "\(preview.totalDaysInAura)")
                        LabeledContent("Total workouts", value: "\(preview.totalWorkoutsInAura)")
                    }
                }

                if let delta = sync.delta {
                    Section("Missing from Aura (will upload)") {
                        LabeledContent("From",
                                       value: ISO8601DateFormatter.dateOnly.string(from: delta.since))
                        LabeledContent("To",
                                       value: ISO8601DateFormatter.dateOnly.string(from: delta.until))
                        LabeledContent("Days", value: "\(delta.daysCovered)")
                        LabeledContent("Samples (all types)", value: "\(delta.totalSamples)")
                        LabeledContent("Workouts", value: "\(delta.workoutCount)")
                    }

                    if !delta.quantityCounts.isEmpty {
                        Section("Quantity samples") {
                            ForEach(delta.quantityCounts) { tc in
                                LabeledContent(tc.type, value: "\(tc.count)")
                            }
                        }
                    }
                    if !delta.categoryCounts.isEmpty {
                        Section("Category samples") {
                            ForEach(delta.categoryCounts) { tc in
                                LabeledContent(tc.type, value: "\(tc.count)")
                            }
                        }
                    }

                    if sync.phase == .awaitingConfirmation {
                        Section {
                            Button {
                                guard let token = auth.token else { return }
                                Task { await sync.confirmUpload(token: token) }
                            } label: {
                                Label("Confirm & Upload", systemImage: "icloud.and.arrow.up.fill")
                                    .frame(maxWidth: .infinity)
                            }
                            .buttonStyle(.borderedProminent)

                            Button("Cancel", role: .cancel) {
                                sync.cancelPreview()
                            }
                        }
                    }
                }

                Section("Status") {
                    statusView
                }

                if let resp = sync.lastResponse {
                    Section("Last upload") {
                        LabeledContent("Samples", value: "\(resp.acceptedSamples)")
                        LabeledContent("Workouts", value: "\(resp.acceptedWorkouts)")
                        LabeledContent("Days touched", value: "\(resp.daysAffected.count)")
                    }
                }
            }
            .navigationTitle("Sync")
        }
    }

    private var isBusy: Bool {
        switch sync.phase {
        case .loadingPreview, .uploading: return true
        default: return false
        }
    }

    @ViewBuilder
    private var statusView: some View {
        switch sync.phase {
        case .idle:
            Text("Tap *Check what's missing* to scan your HealthKit data.")
                .foregroundStyle(.secondary)
        case .loadingPreview:
            HStack { ProgressView(); Text("Loading preview…") }
        case .awaitingConfirmation:
            Text("Review the summary above and tap *Confirm & Upload* to send.")
                .foregroundStyle(.secondary)
        case .uploading(let p):
            VStack(alignment: .leading, spacing: 8) {
                Text("Uploading…")
                ProgressView(value: p)
            }
        case .error(let msg):
            Text(msg).foregroundStyle(.red)
        case .done(let samples, let days):
            Text("Done — \(samples) samples across \(days) days. Switching to Dashboard…")
                .foregroundStyle(.green)
        }
    }
}
