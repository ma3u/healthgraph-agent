import SwiftUI
import UIKit

struct SyncView: View {
    @EnvironmentObject private var auth: AuthStore
    @EnvironmentObject private var sync: SyncCoordinator

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Button {
                        guard let token = auth.idToken,
                              let endpoint = auth.connection?.graphqlURL else { return }
                        Task { await sync.loadPreview(token: token, endpoint: endpoint) }
                    } label: {
                        Label("Check what's missing", systemImage: "magnifyingglass")
                    }
                    .disabled(isBusy)

                    Button {
                        guard let token = auth.idToken,
                              let endpoint = auth.connection?.graphqlURL else { return }
                        Task { await sync.loadRescan(daysBack: 30, token: token, endpoint: endpoint) }
                    } label: {
                        Label("Rescan last 30 days (backfill)", systemImage: "arrow.counterclockwise")
                    }
                    .disabled(isBusy)
                } header: {
                    Text("Sync to your Aura")
                } footer: {
                    Text("*Check what's missing* uploads only data newer than Aura's latest day. " +
                         "*Rescan last 30 days* overwrites the last 30 days regardless — use after " +
                         "granting new HealthKit permissions so partial days get filled in.")
                        .foregroundStyle(.secondary)
                }

                if let latest = sync.auraLatestDay {
                    Section("Currently in Aura") {
                        LabeledContent("Latest day", value: latest)
                    }
                }

                if let delta = sync.delta {
                    Section {
                        LabeledContent("Date range",
                            value: "\(ISO8601DateFormatter.dateOnly.string(from: delta.since)) → \(ISO8601DateFormatter.dateOnly.string(from: delta.until))")
                        LabeledContent("Days", value: "\(delta.daysCovered)")
                        LabeledContent("Total samples", value: "\(delta.totalSamples)")
                        LabeledContent("Workouts", value: "\(delta.workoutCount)")
                    } header: {
                        Text("Will upload to Aura")
                    } footer: {
                        Text("Counts are totals across the full date range above, not per-day.")
                            .foregroundStyle(.secondary)
                    }

                    if delta.hasZeroSamples {
                        Section {
                            Text("If a type below shows 0, either it has no data in this date range, " +
                                 "or HealthKit didn't grant access (Apple hides this for privacy).")
                                .font(.footnote)
                                .foregroundStyle(.orange)
                            Text("To toggle permissions:\n" +
                                 "**Health app → Sharing tab (bottom) → tap *Apps & Services* under Sources → HealthGraph Sync**")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        } header: {
                            Text("Some types are empty")
                        }
                    }

                    if !delta.quantityCounts.isEmpty {
                        Section {
                            ForEach(delta.quantityCounts) { tc in
                                LabeledContent(tc.type, value: "\(tc.count)")
                                    .foregroundStyle(tc.count == 0 ? .secondary : .primary)
                            }
                        } header: {
                            Text("Samples by type — total across \(delta.daysCovered) days")
                        }
                    }
                    if !delta.categoryCounts.isEmpty {
                        Section {
                            ForEach(delta.categoryCounts) { tc in
                                LabeledContent(tc.type, value: "\(tc.count)")
                                    .foregroundStyle(tc.count == 0 ? .secondary : .primary)
                            }
                        } header: {
                            Text("Category samples — total across \(delta.daysCovered) days")
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
