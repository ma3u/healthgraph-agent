import Foundation

/// Aggregates HealthKit samples into the GraphQL mutation inputs the Aura
/// Data API accepts (the `*UpsertInput` types defined in
/// `cypher/graphql_schema.graphql`). This is the iOS-side equivalent of
/// `etl/transform.py` — kept deliberately minimal: one DailySummary per day,
/// one Workout per HK workout sample, one SleepSession per day with sleep.
enum AuraIngest {
    struct DailySummaryUpsertInput: Encodable {
        var date: String
        var dayOfWeek: String?
        var weekIso: String?

        var avgHeartRate: Double?
        var minHeartRate: Double?
        var maxHeartRate: Double?
        var restingHeartRate: Double?
        var hrvMean: Double?

        var totalSteps: Double?
        var totalDistanceKm: Double?
        var activeEnergyKcal: Double?
        var basalEnergyKcal: Double?
        var flightsClimbed: Double?
        var exerciseMinutes: Double?
        var standHours: Double?

        var avgBloodOxygen: Double?
        var avgRespiratoryRate: Double?
        var bodyMassKg: Double?
        var vo2max: Double?

        var sleepHours: Double?
        var workoutCount: Int?
        var workoutMinutes: Double?
        var description: String?
    }

    struct WorkoutUpsertInput: Encodable {
        var uid: String
        var activityType: String
        var startDate: String  // ISO 8601
        var endDate: String
        var durationMin: Double?
        var device: String?
        var sourceName: String?
    }

    struct SleepUpsertInput: Encodable {
        var date: String
        var asleepMinutes: Double
        var inBedMinutes: Double?
        var sourceName: String?
    }

    /// Compute everything we need from a single day's HealthKit samples.
    static func summary(from payload: IngestPayload, on day: String) -> DailySummaryUpsertInput {
        let dayKey = day
        let q = payload.quantitySamples.filter { iso(date: $0.startDate) == dayKey }
        let workoutsForDay = payload.workouts.filter { iso(date: $0.startDate) == dayKey }

        let cal = Calendar.current
        let dayDate = ISO8601DateFormatter.dateOnly.date(from: day) ?? Date()
        let weekday = cal.dateComponents([.weekday], from: dayDate).weekday ?? 1
        let dowNames = ["Sunday", "Monday", "Tuesday", "Wednesday",
                        "Thursday", "Friday", "Saturday"]
        let dayOfWeek = dowNames[(weekday - 1) % 7]

        let isoCal = cal.dateComponents([.yearForWeekOfYear, .weekOfYear], from: dayDate)
        let weekIso = String(format: "%04d-W%02d",
                             isoCal.yearForWeekOfYear ?? 0,
                             isoCal.weekOfYear ?? 0)

        func avg(_ type: String) -> Double? {
            let vals = q.filter { $0.type == type }.map { $0.value }
            guard !vals.isEmpty else { return nil }
            return vals.reduce(0, +) / Double(vals.count)
        }
        func sum(_ type: String) -> Double? {
            let vals = q.filter { $0.type == type }.map { $0.value }
            guard !vals.isEmpty else { return nil }
            return vals.reduce(0, +)
        }
        func minOf(_ type: String) -> Double? {
            let vals = q.filter { $0.type == type }.map { $0.value }
            return vals.min()
        }
        func maxOf(_ type: String) -> Double? {
            let vals = q.filter { $0.type == type }.map { $0.value }
            return vals.max()
        }
        func last(_ type: String) -> Double? {
            q.filter { $0.type == type }.sorted { $0.startDate < $1.startDate }.last?.value
        }

        var s = DailySummaryUpsertInput(
            date: dayKey,
            dayOfWeek: dayOfWeek,
            weekIso: weekIso
        )
        s.avgHeartRate = avg("HeartRate").map { round($0 * 10) / 10 }
        s.minHeartRate = minOf("HeartRate")
        s.maxHeartRate = maxOf("HeartRate")
        s.restingHeartRate = last("RestingHeartRate")
        s.hrvMean = avg("HeartRateVariabilitySDNN")
        s.totalSteps = sum("StepCount")
        s.totalDistanceKm = sum("DistanceWalkingRunning").map { $0 / 1000 }
        s.activeEnergyKcal = sum("ActiveEnergyBurned")
        s.basalEnergyKcal = sum("BasalEnergyBurned")
        s.flightsClimbed = sum("FlightsClimbed")
        s.exerciseMinutes = sum("AppleExerciseTime")
        s.avgBloodOxygen = avg("OxygenSaturation")
        s.avgRespiratoryRate = avg("RespiratoryRate")
        s.bodyMassKg = last("BodyMass")
        s.vo2max = last("VO2Max")
        s.workoutCount = workoutsForDay.count
        s.workoutMinutes = workoutsForDay.reduce(0) { $0 + $1.durationSeconds / 60 }

        // Sleep — sum minutes for asleep-* category samples on this day
        let asleepValues: Set<String> = ["Asleep", "AsleepCore", "AsleepDeep", "AsleepREM", "AsleepUnspecified"]
        let sleepMinutes = payload.categorySamples
            .filter { iso(date: $0.startDate) == dayKey && asleepValues.contains($0.categoryValue) }
            .reduce(0.0) { $0 + $1.endDate.timeIntervalSince($1.startDate) / 60.0 }
        if sleepMinutes > 0 {
            s.sleepHours = round(sleepMinutes / 60.0 * 10) / 10
        }
        return s
    }

    static func workoutInputs(from payload: IngestPayload) -> [WorkoutUpsertInput] {
        let isoF = ISO8601DateFormatter()
        return payload.workouts.map { w in
            WorkoutUpsertInput(
                uid: w.uuid ?? "\(w.activityType)-\(isoF.string(from: w.startDate))",
                activityType: w.activityType,
                startDate: isoF.string(from: w.startDate),
                endDate: isoF.string(from: w.endDate),
                durationMin: w.durationSeconds / 60.0,
                device: w.device,
                sourceName: w.sourceName
            )
        }
    }

    static func sleepInputs(from payload: IngestPayload) -> [SleepUpsertInput] {
        let asleep: Set<String> = ["Asleep", "AsleepCore", "AsleepDeep", "AsleepREM", "AsleepUnspecified"]
        let inBed: Set<String> = ["InBed"]
        var byDay: [String: (asleepMin: Double, inBedMin: Double, source: String)] = [:]
        for c in payload.categorySamples where c.type == "SleepAnalysis" {
            let day = iso(date: c.startDate)
            let mins = c.endDate.timeIntervalSince(c.startDate) / 60.0
            var entry = byDay[day] ?? (0, 0, c.sourceName)
            if asleep.contains(c.categoryValue) { entry.asleepMin += mins }
            if inBed.contains(c.categoryValue) { entry.inBedMin += mins }
            byDay[day] = entry
        }
        return byDay
            .filter { $0.value.asleepMin > 0 }
            .map { (day, v) in
                SleepUpsertInput(
                    date: day,
                    asleepMinutes: round(v.asleepMin * 10) / 10,
                    inBedMinutes: v.inBedMin > 0 ? round(v.inBedMin * 10) / 10 : nil,
                    sourceName: v.source
                )
            }
    }

    static func uniqueDays(in payload: IngestPayload) -> [String] {
        var seen = Set<String>()
        for s in payload.quantitySamples { seen.insert(iso(date: s.startDate)) }
        for c in payload.categorySamples { seen.insert(iso(date: c.startDate)) }
        for w in payload.workouts { seen.insert(iso(date: w.startDate)) }
        return seen.sorted()
    }

    private static func iso(date: Date) -> String {
        ISO8601DateFormatter.dateOnly.string(from: date)
    }
}

// MARK: - Lightweight transport types

/// Re-defined here so the file is self-contained after deleting Payload.swift.
/// Pure data carriers populated by HealthKitService; never sent over the wire.
struct IngestPayload {
    var person: PersonInfo?
    var quantitySamples: [QuantitySample]
    var categorySamples: [CategorySample]
    var workouts: [WorkoutPayload]
}

struct PersonInfo: Codable {
    var dateOfBirth: String?
    var biologicalSex: String?
    var bloodType: String?
}

struct QuantitySample {
    var type: String
    var rawType: String?
    var value: Double
    var unit: String?
    var startDate: Date
    var endDate: Date
    var sourceName: String
    var sourceVersion: String?
    var device: String?
    var uuid: String?
}

struct CategorySample {
    var type: String
    var rawType: String?
    var categoryValue: String
    var rawCategoryValue: String?
    var startDate: Date
    var endDate: Date
    var sourceName: String
    var sourceVersion: String?
    var device: String?
    var uuid: String?
}

struct WorkoutPayload {
    var activityType: String
    var rawActivityType: String?
    var durationSeconds: Double
    var totalDistanceMeters: Double?
    var totalEnergyKcal: Double?
    var startDate: Date
    var endDate: Date
    var sourceName: String
    var sourceVersion: String?
    var device: String?
    var uuid: String?
}
