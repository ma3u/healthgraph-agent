import Foundation
import SwiftUI

@MainActor
final class SyncCoordinator: ObservableObject {
    enum Phase: Equatable {
        case idle
        case initial(progress: Double)
        case incremental
        case error(String)
        case done(samples: Int, days: Int)
    }

    @Published var phase: Phase = .idle
    @Published var lastResponse: IngestResponse?

    private let healthKit = HealthKitService.shared

    func runInitial(token: String) async {
        phase = .initial(progress: 0)
        do {
            try await healthKit.requestAuthorization()
            var totalSamples = 0
            var totalDays = Set<String>()
            let stream = try await healthKit.initialSyncPayloads { p in
                Task { @MainActor in self.phase = .initial(progress: p) }
            }
            for await payload in stream {
                let resp = try await APIClient.shared.ingest(payload, token: token)
                totalSamples += resp.acceptedSamples + resp.acceptedWorkouts
                totalDays.formUnion(resp.daysAffected)
                lastResponse = resp
            }
            phase = .done(samples: totalSamples, days: totalDays.count)
        } catch {
            phase = .error((error as? APIError)?.userFacing ?? error.localizedDescription)
        }
    }

    func runIncremental(token: String) async {
        phase = .incremental
        do {
            try await healthKit.requestAuthorization()
            guard let payload = try await healthKit.incrementalSyncPayload() else {
                phase = .done(samples: 0, days: 0)
                return
            }
            let resp = try await APIClient.shared.ingest(payload, token: token)
            lastResponse = resp
            phase = .done(samples: resp.acceptedSamples + resp.acceptedWorkouts, days: resp.daysAffected.count)
        } catch {
            phase = .error((error as? APIError)?.userFacing ?? error.localizedDescription)
        }
    }
}
