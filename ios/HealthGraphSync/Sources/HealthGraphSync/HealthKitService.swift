import Foundation
import HealthKit

/// Reads HealthKit samples and builds IngestPayload batches.
///
/// Strategy:
///  - Initial sync: walk from the earliest available date to now, batched by
///    month, sending one IngestPayload per month.
///  - Incremental sync: ask HKAnchoredObjectQuery for samples since the last
///    saved anchor, collect the set of dates touched, then for each touched
///    date issue a regular HKSampleQuery for the FULL day and POST that. This
///    keeps daily summaries on the backend coherent (see backend/README.md).
@MainActor
final class HealthKitService: ObservableObject {
    static let shared = HealthKitService()

    private let store = HKHealthStore()
    private let anchorPrefix = "hk.anchor."

    /// Is HealthKit available on this device (e.g. not on iPad without Health).
    var isAvailable: Bool { HKHealthStore.isHealthDataAvailable() }

    /// Request read access for all the types in HealthKitTypes. Safe to call
    /// repeatedly — iOS only prompts the user once per missing type.
    func requestAuthorization() async throws {
        guard isAvailable else { throw HKError(.errorHealthDataUnavailable) }
        try await store.requestAuthorization(toShare: [], read: HealthKitTypes.allReadTypes)
    }

    // MARK: - Initial sync

    /// Build payloads for the full history, one month at a time. Yields each
    /// payload as it's ready so the caller can POST incrementally.
    func initialSyncPayloads(progress: @escaping @Sendable (Double) -> Void) async throws -> AsyncStream<IngestPayload> {
        let now = Date()
        // Apple Watch's earliest plausible date. Anything before this is
        // either manually entered or out of scope.
        let oldest = Calendar.current.date(byAdding: .year, value: -10, to: now) ?? now

        var months: [(Date, Date)] = []
        var cursor = Calendar.current.dateInterval(of: .month, for: oldest)?.start ?? oldest
        while cursor < now {
            let next = Calendar.current.date(byAdding: .month, value: 1, to: cursor) ?? now
            months.append((cursor, min(next, now)))
            cursor = next
        }

        let person = await readPersonInfo()
        let total = Double(months.count)

        return AsyncStream { continuation in
            Task {
                for (i, range) in months.enumerated() {
                    do {
                        let payload = try await buildPayload(
                            start: range.0,
                            end: range.1,
                            person: i == 0 ? person : nil
                        )
                        if !payload.isEmpty {
                            continuation.yield(payload)
                        }
                    } catch {
                        // Surface partial progress; the caller will retry the month later.
                    }
                    await MainActor.run { progress(Double(i + 1) / total) }
                }
                continuation.finish()
            }
        }
    }

    // MARK: - Delta scan (preview)

    /// Per-type breakdown of HealthKit samples newer than `since`. Used by the
    /// confirmation dialog before kicking off an upload. No network calls.
    struct DeltaScan: Sendable {
        struct TypeCount: Identifiable, Sendable {
            let id = UUID()
            let type: String
            let count: Int
        }
        var since: Date
        var until: Date
        var quantityCounts: [TypeCount]
        var categoryCounts: [TypeCount]
        var workoutCount: Int
        var daysCovered: Int

        var totalSamples: Int {
            quantityCounts.reduce(0) { $0 + $1.count } +
            categoryCounts.reduce(0) { $0 + $1.count }
        }
    }

    func deltaScan(since: Date) async throws -> DeltaScan {
        try await requestAuthorization()
        let until = Date()

        var qCounts: [DeltaScan.TypeCount] = []
        for q in HealthKitTypes.quantities {
            guard let type = HKQuantityType.quantityType(forIdentifier: q.id) else { continue }
            let samples = try await fetchSamples(type: type, start: since, end: until)
            if !samples.isEmpty {
                qCounts.append(.init(type: q.display, count: samples.count))
            }
        }
        var cCounts: [DeltaScan.TypeCount] = []
        for c in HealthKitTypes.categories {
            guard let type = HKCategoryType.categoryType(forIdentifier: c.id) else { continue }
            let samples = try await fetchSamples(type: type, start: since, end: until)
            if !samples.isEmpty {
                cCounts.append(.init(type: c.display, count: samples.count))
            }
        }
        let workouts = try await fetchSamples(type: HKObjectType.workoutType(), start: since, end: until)

        let allDates = Set(
            (qCounts + cCounts).flatMap { _ in [] as [String] }
        )
        let cal = Calendar.current
        let days = max(1, cal.dateComponents([.day], from: since, to: until).day ?? 1)

        return DeltaScan(
            since: since,
            until: until,
            quantityCounts: qCounts.sorted { $0.count > $1.count },
            categoryCounts: cCounts.sorted { $0.count > $1.count },
            workoutCount: workouts.count,
            daysCovered: max(days, allDates.count)
        )
    }

    /// Build a full IngestPayload for the date range covered by the delta scan.
    /// This is what gets POSTed to /ingest/healthkit when the user confirms.
    func buildPayload(since: Date, until: Date) async throws -> IngestPayload {
        try await buildPayload(start: since, end: until, person: await readPersonInfo())
    }

    // MARK: - Incremental sync

    /// Returns the set of YYYY-MM-DD dates that have changed since the saved
    /// anchor for each type, then builds a payload that re-sends the FULL day
    /// of samples for those dates.
    func incrementalSyncPayload() async throws -> IngestPayload? {
        var touchedDays = Set<String>()
        for q in HealthKitTypes.quantities {
            guard let type = HKQuantityType.quantityType(forIdentifier: q.id) else { continue }
            let dates = try await anchoredFetchDates(type: type, accountKey: "\(q.display)")
            touchedDays.formUnion(dates)
        }
        for c in HealthKitTypes.categories {
            guard let type = HKCategoryType.categoryType(forIdentifier: c.id) else { continue }
            let dates = try await anchoredFetchDates(type: type, accountKey: "\(c.display)")
            touchedDays.formUnion(dates)
        }
        let workoutDates = try await anchoredFetchDates(
            type: HKObjectType.workoutType(),
            accountKey: "Workout"
        )
        touchedDays.formUnion(workoutDates)

        guard !touchedDays.isEmpty else { return nil }

        let calendar = Calendar.current
        let isoDateOnly = ISO8601DateFormatter()
        isoDateOnly.formatOptions = [.withFullDate, .withDashSeparatorInDate]

        // Build a single payload covering all touched dates.
        var quantitySamples: [QuantitySample] = []
        var categorySamples: [CategorySample] = []
        var workouts: [WorkoutPayload] = []

        for day in touchedDays.sorted() {
            guard let date = isoDateOnly.date(from: day) else { continue }
            let dayStart = calendar.startOfDay(for: date)
            guard let dayEnd = calendar.date(byAdding: .day, value: 1, to: dayStart) else { continue }
            let partial = try await buildPayload(start: dayStart, end: dayEnd, person: nil)
            quantitySamples += partial.quantitySamples
            categorySamples += partial.categorySamples
            workouts += partial.workouts
        }

        return IngestPayload(
            person: nil,
            quantitySamples: quantitySamples,
            categorySamples: categorySamples,
            workouts: workouts
        )
    }

    // MARK: - Building payloads

    private func buildPayload(start: Date, end: Date, person: PersonInfo?) async throws -> IngestPayload {
        var quantitySamples: [QuantitySample] = []
        var categorySamples: [CategorySample] = []
        var workouts: [WorkoutPayload] = []

        for q in HealthKitTypes.quantities {
            guard let type = HKQuantityType.quantityType(forIdentifier: q.id) else { continue }
            let samples = try await fetchSamples(type: type, start: start, end: end)
            for s in samples {
                guard let qs = s as? HKQuantitySample else { continue }
                quantitySamples.append(QuantitySample(
                    type: q.display,
                    rawType: type.identifier,
                    value: qs.quantity.doubleValue(for: q.unit),
                    unit: q.unit.unitString,
                    startDate: qs.startDate,
                    endDate: qs.endDate,
                    sourceName: qs.sourceRevision.source.name,
                    sourceVersion: qs.sourceRevision.version,
                    device: qs.device?.name,
                    uuid: qs.uuid.uuidString
                ))
            }
        }

        for c in HealthKitTypes.categories {
            guard let type = HKCategoryType.categoryType(forIdentifier: c.id) else { continue }
            let samples = try await fetchSamples(type: type, start: start, end: end)
            for s in samples {
                guard let cs = s as? HKCategorySample else { continue }
                let cleaned: String
                switch c.id {
                case .sleepAnalysis: cleaned = HealthKitTypes.sleepAnalysisName(cs.value)
                case .appleStandHour: cleaned = HealthKitTypes.standHourName(cs.value)
                default: cleaned = "Unknown"
                }
                categorySamples.append(CategorySample(
                    type: c.display,
                    rawType: type.identifier,
                    categoryValue: cleaned,
                    rawCategoryValue: String(cs.value),
                    startDate: cs.startDate,
                    endDate: cs.endDate,
                    sourceName: cs.sourceRevision.source.name,
                    sourceVersion: cs.sourceRevision.version,
                    device: cs.device?.name,
                    uuid: cs.uuid.uuidString
                ))
            }
        }

        let workoutSamples = try await fetchSamples(
            type: HKObjectType.workoutType(),
            start: start,
            end: end
        )
        for s in workoutSamples {
            guard let w = s as? HKWorkout else { continue }
            workouts.append(WorkoutPayload(
                activityType: HealthKitTypes.workoutActivityName(w.workoutActivityType),
                rawActivityType: "HKWorkoutActivityType\(HealthKitTypes.workoutActivityName(w.workoutActivityType))",
                durationSeconds: w.duration,
                totalDistanceMeters: w.totalDistance?.doubleValue(for: .meter()),
                totalEnergyKcal: w.totalEnergyBurned?.doubleValue(for: .kilocalorie()),
                startDate: w.startDate,
                endDate: w.endDate,
                sourceName: w.sourceRevision.source.name,
                sourceVersion: w.sourceRevision.version,
                device: w.device?.name,
                uuid: w.uuid.uuidString
            ))
        }

        return IngestPayload(
            person: person,
            quantitySamples: quantitySamples,
            categorySamples: categorySamples,
            workouts: workouts
        )
    }

    private func fetchSamples(type: HKSampleType, start: Date, end: Date) async throws -> [HKSample] {
        let predicate = HKQuery.predicateForSamples(withStart: start, end: end, options: .strictStartDate)
        let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: true)
        return try await withCheckedThrowingContinuation { continuation in
            let query = HKSampleQuery(
                sampleType: type,
                predicate: predicate,
                limit: HKObjectQueryNoLimit,
                sortDescriptors: [sortDescriptor]
            ) { _, samples, error in
                if let error { continuation.resume(throwing: error); return }
                continuation.resume(returning: samples ?? [])
            }
            store.execute(query)
        }
    }

    /// HKAnchoredObjectQuery — returns the YYYY-MM-DD dates of any samples
    /// (new, modified, or deleted) since the saved anchor for `accountKey`.
    private func anchoredFetchDates(type: HKSampleType, accountKey: String) async throws -> [String] {
        let key = anchorPrefix + accountKey
        let anchor: HKQueryAnchor? = {
            guard let data = UserDefaults.standard.data(forKey: key) else { return nil }
            return try? NSKeyedUnarchiver.unarchivedObject(ofClass: HKQueryAnchor.self, from: data)
        }()

        let result: (HKQueryAnchor?, [HKSample], [HKDeletedObject]) =
            try await withCheckedThrowingContinuation { continuation in
            let query = HKAnchoredObjectQuery(
                type: type,
                predicate: nil,
                anchor: anchor,
                limit: HKObjectQueryNoLimit
            ) { _, samples, deleted, newAnchor, error in
                if let error { continuation.resume(throwing: error); return }
                continuation.resume(returning: (newAnchor, samples ?? [], deleted ?? []))
            }
            store.execute(query)
        }

        if let newAnchor = result.0,
           let data = try? NSKeyedArchiver.archivedData(withRootObject: newAnchor, requiringSecureCoding: true)
        {
            UserDefaults.standard.set(data, forKey: key)
        }

        let isoDateOnly = ISO8601DateFormatter()
        isoDateOnly.formatOptions = [.withFullDate, .withDashSeparatorInDate]
        isoDateOnly.timeZone = .current

        var dates = Set<String>()
        for s in result.1 { dates.insert(isoDateOnly.string(from: s.startDate)) }
        // For deletions we don't know the original date; the simplest correct
        // behaviour is to skip — the deletion can't be reflected in Aura
        // without storing per-sample nodes. This is a known v1 limitation.
        return Array(dates)
    }

    // MARK: - Person info

    private func readPersonInfo() async -> PersonInfo? {
        var info = PersonInfo()
        if let dobComps = try? store.dateOfBirthComponents(),
           let date = Calendar.current.date(from: dobComps) {
            let formatter = DateFormatter()
            formatter.dateFormat = "yyyy-MM-dd"
            info.dateOfBirth = formatter.string(from: date)
        }
        if let sex = try? store.biologicalSex() {
            switch sex.biologicalSex {
            case .male: info.biologicalSex = "Male"
            case .female: info.biologicalSex = "Female"
            case .other: info.biologicalSex = "Other"
            case .notSet: info.biologicalSex = nil
            @unknown default: info.biologicalSex = nil
            }
        }
        return info.dateOfBirth == nil && info.biologicalSex == nil ? nil : info
    }
}

private extension IngestPayload {
    var isEmpty: Bool {
        quantitySamples.isEmpty && categorySamples.isEmpty && workouts.isEmpty
    }
}
