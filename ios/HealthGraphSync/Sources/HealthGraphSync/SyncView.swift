import SwiftUI

struct SyncView: View {
    @EnvironmentObject private var auth: AuthStore
    @EnvironmentObject private var sync: SyncCoordinator

    var body: some View {
        NavigationStack {
            List {
                Section("Sync to your Aura") {
                    Button {
                        guard let token = auth.idToken,
                              let endpoint = auth.connection?.graphqlURL else { return }
                        Task { await sync.loadPreview(token: token, endpoint: endpoint) }
                    } label: {
                        Label("Check what's missing", systemImage: "magnifyingglass")
                    }
                    .disabled(isBusy)
                }

                if let latest = sync.auraLatestDay {
                    Section("Currently in Aura") {
                        LabeledContent("Latest day", value: latest)
                    }
                }

                if let delta = sync.delta {
                    Section("Missing from Aura (will upload)") {
                        LabeledContent("From",
                                       value: ISO8601DateFormatter.dateOnly.string(from: delta.since))
                        LabeledContent("To",
                                       value: ISO8601DateFormatter.dateOnly.string(from: delta.until))
                        LabeledContent("Days", value: "\(delta.daysCovered)")
                        LabeledContent("Samples", value: "\(delta.totalSamples)")
                        LabeledContent("Workouts", value: "\(delta.workoutCount)")
                    }

                    if !delta.deniedTypes.isEmpty || delta.workoutAuthStatus == .sharingDenied {
                        Section {
                            Text("HealthKit denied permission for some types. Open **Settings → Privacy & Security → Health → HealthGraphSync** to grant them, then come back here and re-scan.")
                                .font(.footnote)
                                .foregroundStyle(.orange)
                            ForEach(delta.deniedTypes, id: \.self) { name in
                                Label(name, systemImage: "lock.fill").foregroundStyle(.secondary)
                            }
                            if delta.workoutAuthStatus == .sharingDenied {
                                Label("Workouts", systemImage: "lock.fill").foregroundStyle(.secondary)
                            }
                        } header: {
                            Text("Permission needed")
                        }
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
                                guard let token = auth.idToken,
                                      let endpoint = auth.connection?.graphqlURL else { return }
                                Task { await sync.confirmUpload(token: token, endpoint: endpoint) }
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

                Section("Status") { statusView }
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
            Text("Review and tap *Confirm & Upload*.")
                .foregroundStyle(.secondary)
        case .uploading(let p):
            VStack(alignment: .leading, spacing: 8) {
                Text("Uploading to Aura…")
                ProgressView(value: p)
            }
        case .error(let msg):
            Text(msg).foregroundStyle(.red)
        case .done(let days, let workouts, let sleep):
            Text("Done — \(days) days · \(workouts) workouts · \(sleep) sleep sessions. Opening Dashboard…")
                .foregroundStyle(.green)
        }
    }
}
