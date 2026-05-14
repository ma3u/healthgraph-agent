import Foundation
import SwiftUI

@MainActor
final class SyncCoordinator: ObservableObject {
    enum Phase: Equatable {
        case idle
        case loadingPreview
        case awaitingConfirmation
        case uploading(progress: Double)
        case error(String)
        case done(samples: Int, days: Int)
    }

    @Published var phase: Phase = .idle
    @Published var auraPreview: SyncPreviewResponse?
    @Published var delta: HealthKitService.DeltaScan?
    @Published var lastResponse: IngestResponse?
    /// Signals MainTabsView to switch to the Dashboard tab once an upload
    /// finishes successfully.
    @Published var shouldShowDashboard = false

    private let healthKit = HealthKitService.shared

    /// Step 1: Fetch the latest day from Aura, scan HealthKit locally, and
    /// present a summary the user can confirm before any upload happens.
    func loadPreview(token: String) async {
        phase = .loadingPreview
        do {
            let preview = try await APIClient.shared.syncPreview(token: token)
            auraPreview = preview

            let since: Date = {
                if let isoString = preview.latestDayInAura,
                   let date = ISO8601DateFormatter.dateOnly.date(from: isoString) {
                    // Re-scan from the START of that day to catch late-arriving samples
                    return Calendar.current.startOfDay(for: date)
                }
                // No history in Aura yet — go back a default of 30 days for an
                // initial demo. (For a true initial sync the user can still
                // use the older "full history" path; this is the v1 default.)
                return Calendar.current.date(byAdding: .day, value: -30, to: Date()) ?? Date()
            }()

            let scan = try await healthKit.deltaScan(since: since)
            delta = scan
            phase = .awaitingConfirmation
        } catch {
            phase = .error((error as? APIError)?.userFacing ?? error.localizedDescription)
        }
    }

    /// Step 2: User tapped Confirm. Build the payload covering the delta
    /// range, POST it, and on success auto-switch to the Dashboard tab.
    func confirmUpload(token: String) async {
        guard let scan = delta else { return }
        phase = .uploading(progress: 0)
        do {
            let payload = try await healthKit.buildPayload(since: scan.since, until: scan.until)
            phase = .uploading(progress: 0.5)
            let resp = try await APIClient.shared.ingest(payload, token: token)
            lastResponse = resp
            phase = .done(samples: resp.acceptedSamples + resp.acceptedWorkouts, days: resp.daysAffected.count)
            shouldShowDashboard = true
        } catch {
            phase = .error((error as? APIError)?.userFacing ?? error.localizedDescription)
        }
    }

    func cancelPreview() {
        delta = nil
        auraPreview = nil
        phase = .idle
    }
}

extension ISO8601DateFormatter {
    /// Thread-safe per-call factory so Swift 6 strict concurrency is happy.
    /// ISO8601DateFormatter itself is not Sendable.
    static func dateOnlyFormatter() -> ISO8601DateFormatter {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withFullDate, .withDashSeparatorInDate]
        return f
    }

    nonisolated(unsafe) static let dateOnly: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withFullDate, .withDashSeparatorInDate]
        return f
    }()
}
