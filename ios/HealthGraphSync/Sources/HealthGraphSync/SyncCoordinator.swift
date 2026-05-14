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
        case done(daysWritten: Int, workouts: Int, sleepSessions: Int)
    }

    @Published var phase: Phase = .idle
    @Published var auraLatestDay: String?
    @Published var delta: HealthKitService.DeltaScan?
    @Published var lastDaysWritten = 0
    @Published var shouldShowDashboard = false

    private let healthKit = HealthKitService.shared

    func loadPreview(token: String, endpoint: URL) async {
        phase = .loadingPreview
        do {
            // Ask Aura for the most recent Day.date
            struct LatestDayResult: Decodable {
                let max: String?
            }
            // Aura GraphQL Library v6+ syntax: sort and limit are top-level args
            let query = """
            query LatestDay {
              days(sort: [{ date: DESC }], limit: 1) {
                date
              }
            }
            """
            struct Day: Decodable { let date: String }
            let days: [Day] = try await GraphQLClient.shared.run(
                query: query,
                token: token,
                endpoint: endpoint,
                decodeUnder: "days"
            )
            auraLatestDay = days.first?.date

            let since: Date = {
                if let isoString = auraLatestDay,
                   let date = ISO8601DateFormatter.dateOnly.date(from: isoString) {
                    return Calendar.current.startOfDay(for: date)
                }
                return Calendar.current.date(byAdding: .day, value: -30, to: Date()) ?? Date()
            }()
            let scan = try await healthKit.deltaScan(since: since)
            delta = scan
            phase = .awaitingConfirmation
        } catch {
            phase = .error((error as? LocalizedError)?.errorDescription ?? error.localizedDescription)
        }
    }

    func confirmUpload(token: String, endpoint: URL) async {
        guard let scan = delta else { return }
        phase = .uploading(progress: 0)
        do {
            let payload = try await healthKit.buildPayload(since: scan.since, until: scan.until)
            let days = AuraIngest.uniqueDays(in: payload)
            let workouts = AuraIngest.workoutInputs(from: payload)
            let sleeps = AuraIngest.sleepInputs(from: payload)

            let totalSteps = Double(days.count + workouts.count + sleeps.count)
            var stepsDone: Double = 0
            func tick() {
                stepsDone += 1
                phase = .uploading(progress: stepsDone / max(totalSteps, 1))
            }

            // Days
            for day in days {
                let summary = AuraIngest.summary(from: payload, on: day)
                _ = try await runIngestDay(summary, token: token, endpoint: endpoint)
                tick()
            }
            // Workouts
            for w in workouts {
                _ = try await runIngestWorkout(w, token: token, endpoint: endpoint)
                tick()
            }
            // Sleep sessions
            for sl in sleeps {
                _ = try await runIngestSleep(sl, token: token, endpoint: endpoint)
                tick()
            }

            lastDaysWritten = days.count
            phase = .done(daysWritten: days.count, workouts: workouts.count, sleepSessions: sleeps.count)
            shouldShowDashboard = true
        } catch {
            phase = .error((error as? LocalizedError)?.errorDescription ?? error.localizedDescription)
        }
    }

    func cancelPreview() {
        delta = nil
        auraLatestDay = nil
        phase = .idle
    }

    // MARK: - Mutation runners

    private func runIngestDay(_ input: AuraIngest.DailySummaryUpsertInput,
                              token: String, endpoint: URL) async throws -> String {
        let mutation = """
        mutation IngestDay($input: DailySummaryUpsertInput!) {
          ingestDay(input: $input)
        }
        """
        return try await GraphQLClient.shared.run(
            query: mutation,
            variables: ["input": AnyEncodable(value: input)],
            token: token,
            endpoint: endpoint,
            decodeUnder: "ingestDay"
        )
    }

    private func runIngestWorkout(_ input: AuraIngest.WorkoutUpsertInput,
                                  token: String, endpoint: URL) async throws -> String {
        let mutation = """
        mutation IngestWorkout($input: WorkoutUpsertInput!) {
          ingestWorkout(input: $input)
        }
        """
        return try await GraphQLClient.shared.run(
            query: mutation,
            variables: ["input": AnyEncodable(value: input)],
            token: token,
            endpoint: endpoint,
            decodeUnder: "ingestWorkout"
        )
    }

    private func runIngestSleep(_ input: AuraIngest.SleepUpsertInput,
                                token: String, endpoint: URL) async throws -> String {
        let mutation = """
        mutation IngestSleep($input: SleepUpsertInput!) {
          ingestSleep(input: $input)
        }
        """
        return try await GraphQLClient.shared.run(
            query: mutation,
            variables: ["input": AnyEncodable(value: input)],
            token: token,
            endpoint: endpoint,
            decodeUnder: "ingestSleep"
        )
    }
}

extension ISO8601DateFormatter {
    nonisolated(unsafe) static let dateOnly: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withFullDate, .withDashSeparatorInDate]
        return f
    }()
}
