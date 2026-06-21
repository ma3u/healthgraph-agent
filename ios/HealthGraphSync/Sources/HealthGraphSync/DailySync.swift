import Foundation
import BackgroundTasks

/// Lets a non-Sendable BGTask cross into the completion `Task`. Its
/// `setTaskCompleted`/`expirationHandler` members are documented thread-safe.
private struct UncheckedBox<T>: @unchecked Sendable {
    let value: T
    init(_ value: T) { self.value = value }
}

/// Scheduled daily background sync: wake Aura, upload the HealthKit delta, done.
/// Runs as a BGProcessingTask (~07:00 local) so it can use the network and take
/// a little longer than an app-refresh task. Headless auth comes from AuthStore
/// (dev-mode synthesizes the x-api-key token from Info.plist).
enum DailySync {
    static let taskID = "io.healthgraph.sync.dailysync"

    /// Register the BG handler. Must be called before the app finishes launching.
    static func register() {
        BGTaskScheduler.shared.register(forTaskWithIdentifier: taskID, using: nil) { task in
            schedule()   // always queue the next day first
            // BGTask isn't Sendable, but setTaskCompleted/expirationHandler are
            // documented thread-safe — box it so the completion Task can use it.
            let box = UncheckedBox(task)
            let work = Task {
                let ok = await run()
                box.value.setTaskCompleted(success: ok)
            }
            task.expirationHandler = { work.cancel() }
        }
    }

    /// Queue the next run for ~07:00 local (after the GitHub Actions morning
    /// resume, so Aura is usually already up). The OS decides the exact time.
    static func schedule() {
        let req = BGProcessingTaskRequest(identifier: taskID)
        req.requiresNetworkConnectivity = true
        req.requiresExternalPower = false
        req.earliestBeginDate = nextMorning()
        try? BGTaskScheduler.shared.submit(req)
    }

    private static func nextMorning() -> Date {
        let cal = Calendar.current
        let now = Date()
        var comps = cal.dateComponents([.year, .month, .day], from: now)
        comps.hour = 7
        comps.minute = 0
        var target = cal.date(from: comps) ?? now.addingTimeInterval(3600)
        if target <= now { target = cal.date(byAdding: .day, value: 1, to: target) ?? target }
        return target
    }

    /// Ensure Aura is up, then upload the anchored HealthKit delta. Returns
    /// false only on a real failure (so the OS can retry).
    @MainActor @discardableResult
    static func run() async -> Bool {
        let auth = AuthStore()
        guard let token = auth.idToken, let endpoint = auth.connection?.graphqlURL else {
            return false   // not signed in / no connection configured
        }
        if AuraAdmin.isConfigured {
            _ = await AuraAdmin.ensureRunning()
        }
        do {
            guard let payload = try await HealthKitService.shared.incrementalSyncPayload() else {
                return true   // nothing new since the last anchor
            }
            try await upload(payload, token: token, endpoint: endpoint)
            return true
        } catch {
            return false
        }
    }

    @MainActor
    private static func upload(_ payload: IngestPayload, token: String, endpoint: URL) async throws {
        for day in AuraIngest.uniqueDays(in: payload) {
            let summary = AuraIngest.summary(from: payload, on: day)
            let _: String = try await GraphQLClient.shared.run(
                query: "mutation IngestDay($input: DailySummaryUpsertInput!) { ingestDay(input: $input) }",
                variables: ["input": AnyEncodable(value: summary)],
                token: token, endpoint: endpoint, decodeUnder: "ingestDay")
        }
        for w in AuraIngest.workoutInputs(from: payload) {
            let _: String = try await GraphQLClient.shared.run(
                query: "mutation IngestWorkout($input: WorkoutUpsertInput!) { ingestWorkout(input: $input) }",
                variables: ["input": AnyEncodable(value: w)],
                token: token, endpoint: endpoint, decodeUnder: "ingestWorkout")
        }
        for sl in AuraIngest.sleepInputs(from: payload) {
            let _: String = try await GraphQLClient.shared.run(
                query: "mutation IngestSleep($input: SleepUpsertInput!) { ingestSleep(input: $input) }",
                variables: ["input": AnyEncodable(value: sl)],
                token: token, endpoint: endpoint, decodeUnder: "ingestSleep")
        }
    }
}
