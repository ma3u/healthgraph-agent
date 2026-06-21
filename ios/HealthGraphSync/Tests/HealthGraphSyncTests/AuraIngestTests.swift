import XCTest
@testable import HealthGraphSync

/// Tests for `AuraIngest` — the iPhone Sync aggregation layer that turns raw
/// HealthKit samples into per-day summaries (avg/sum/min/max/last), sleep
/// hours from asleep category samples, sleep sessions, and the unique-day set.
final class AuraIngestTests: XCTestCase {

    // Dates are built relative to local-noon so the `dateOnly` formatter
    // (which uses `.current` timezone) maps every sample to the same calendar
    // day regardless of the machine's timezone.
    private let dayKey = "2026-05-20"

    /// Local time on `dayKey` at the given hour/minute.
    private func at(_ hour: Int, _ minute: Int = 0) -> Date {
        var c = DateComponents()
        c.year = 2026; c.month = 5; c.day = 20
        c.hour = hour; c.minute = minute
        c.timeZone = .current
        return Calendar.current.date(from: c)!
    }

    /// Local time on the day after `dayKey`.
    private func nextDay(_ hour: Int, _ minute: Int = 0) -> Date {
        var c = DateComponents()
        c.year = 2026; c.month = 5; c.day = 21
        c.hour = hour; c.minute = minute
        c.timeZone = .current
        return Calendar.current.date(from: c)!
    }

    private func quantity(_ type: String, _ value: Double, at date: Date) -> QuantitySample {
        QuantitySample(type: type, rawType: nil, value: value, unit: nil,
                       startDate: date, endDate: date,
                       sourceName: "TestWatch", sourceVersion: nil,
                       device: nil, uuid: nil)
    }

    private func category(_ type: String, _ value: String,
                          from start: Date, to end: Date) -> CategorySample {
        CategorySample(type: type, rawType: nil, categoryValue: value, rawCategoryValue: nil,
                       startDate: start, endDate: end,
                       sourceName: "TestWatch", sourceVersion: nil,
                       device: nil, uuid: nil)
    }

    private func workout(_ activity: String, from start: Date, to end: Date,
                         uuid: String? = nil) -> WorkoutPayload {
        WorkoutPayload(activityType: activity, rawActivityType: nil,
                       durationSeconds: end.timeIntervalSince(start),
                       totalDistanceMeters: nil, totalEnergyKcal: nil,
                       startDate: start, endDate: end,
                       sourceName: "TestWatch", sourceVersion: nil,
                       device: nil, uuid: uuid)
    }

    // MARK: - summary: averages / sums / min / max / last

    func testSummaryAveragesHeartRate() {
        let payload = IngestPayload(
            person: nil,
            quantitySamples: [
                quantity("HeartRate", 60, at: at(8)),
                quantity("HeartRate", 80, at: at(12)),
                quantity("HeartRate", 100, at: at(16)),
            ],
            categorySamples: [],
            workouts: [])
        let s = AuraIngest.summary(from: payload, on: dayKey)
        // avg = 80, rounded to 1 decimal
        XCTAssertEqual(s.avgHeartRate!, 80.0, accuracy: 1e-9)
        XCTAssertEqual(s.minHeartRate!, 60.0, accuracy: 1e-9)
        XCTAssertEqual(s.maxHeartRate!, 100.0, accuracy: 1e-9)
    }

    func testSummaryAverageRoundsToOneDecimal() {
        let payload = IngestPayload(
            person: nil,
            quantitySamples: [
                quantity("HeartRate", 61, at: at(8)),
                quantity("HeartRate", 62, at: at(12)),
                quantity("HeartRate", 64, at: at(16)),
            ],
            categorySamples: [],
            workouts: [])
        let s = AuraIngest.summary(from: payload, on: dayKey)
        // avg = 62.333... -> rounded to 62.3
        XCTAssertEqual(s.avgHeartRate!, 62.3, accuracy: 1e-9)
    }

    func testSummarySumsSteps() {
        let payload = IngestPayload(
            person: nil,
            quantitySamples: [
                quantity("StepCount", 1000, at: at(8)),
                quantity("StepCount", 2500, at: at(12)),
                quantity("StepCount", 500, at: at(16)),
            ],
            categorySamples: [],
            workouts: [])
        let s = AuraIngest.summary(from: payload, on: dayKey)
        XCTAssertEqual(s.totalSteps!, 4000.0, accuracy: 1e-9)
    }

    func testSummaryDistanceConvertedToKm() {
        let payload = IngestPayload(
            person: nil,
            quantitySamples: [
                quantity("DistanceWalkingRunning", 3000, at: at(8)),
                quantity("DistanceWalkingRunning", 2000, at: at(12)),
            ],
            categorySamples: [],
            workouts: [])
        let s = AuraIngest.summary(from: payload, on: dayKey)
        // (3000 + 2000) / 1000 = 5.0 km
        XCTAssertEqual(s.totalDistanceKm!, 5.0, accuracy: 1e-9)
    }

    func testSummaryRestingHeartRateUsesLastByStartDate() {
        let payload = IngestPayload(
            person: nil,
            quantitySamples: [
                quantity("RestingHeartRate", 58, at: at(6)),
                quantity("RestingHeartRate", 52, at: at(22)),   // latest
                quantity("RestingHeartRate", 55, at: at(14)),
            ],
            categorySamples: [],
            workouts: [])
        let s = AuraIngest.summary(from: payload, on: dayKey)
        XCTAssertEqual(s.restingHeartRate!, 52.0, accuracy: 1e-9)
    }

    func testSummaryNilWhenTypeAbsent() {
        let payload = IngestPayload(
            person: nil,
            quantitySamples: [quantity("HeartRate", 60, at: at(8))],
            categorySamples: [],
            workouts: [])
        let s = AuraIngest.summary(from: payload, on: dayKey)
        XCTAssertNil(s.totalSteps)
        XCTAssertNil(s.hrvMean)
        XCTAssertNil(s.vo2max)
        XCTAssertNil(s.bodyMassKg)
    }

    func testSummaryFiltersOutSamplesFromOtherDays() {
        let payload = IngestPayload(
            person: nil,
            quantitySamples: [
                quantity("StepCount", 1000, at: at(8)),
                quantity("StepCount", 9999, at: nextDay(8)),   // different day, ignored
            ],
            categorySamples: [],
            workouts: [])
        let s = AuraIngest.summary(from: payload, on: dayKey)
        XCTAssertEqual(s.totalSteps!, 1000.0, accuracy: 1e-9)
    }

    // MARK: - summary: workouts

    func testSummaryWorkoutCountAndMinutes() {
        let payload = IngestPayload(
            person: nil,
            quantitySamples: [],
            categorySamples: [],
            workouts: [
                workout("Running", from: at(7), to: at(8)),       // 60 min
                workout("Cycling", from: at(17), to: at(17, 30)), // 30 min
                workout("Walking", from: nextDay(9), to: nextDay(10)), // other day, ignored
            ])
        let s = AuraIngest.summary(from: payload, on: dayKey)
        XCTAssertEqual(s.workoutCount, 2)
        XCTAssertEqual(s.workoutMinutes!, 90.0, accuracy: 1e-9)
    }

    // MARK: - summary: sleep hours

    func testSummarySleepHoursFromAsleepCategorySamples() {
        // Asleep 23:00 -> next day 06:00 = 7 hours. The sample is keyed by its
        // start day, so it counts toward dayKey.
        let payload = IngestPayload(
            person: nil,
            quantitySamples: [],
            categorySamples: [
                category("SleepAnalysis", "AsleepCore", from: at(23), to: nextDay(2)),  // 3h
                category("SleepAnalysis", "AsleepDeep", from: nextDay(2), to: nextDay(4)), // starts next day, ignored for dayKey
                category("SleepAnalysis", "AsleepREM", from: at(22), to: at(23)),       // 1h
            ],
            workouts: [])
        let s = AuraIngest.summary(from: payload, on: dayKey)
        // On dayKey: AsleepCore 3h + AsleepREM 1h = 4.0h (AsleepDeep starts next day)
        XCTAssertNotNil(s.sleepHours)
        XCTAssertEqual(s.sleepHours!, 4.0, accuracy: 1e-6)
    }

    func testSummarySleepHoursNilWhenNoAsleepSamples() {
        let payload = IngestPayload(
            person: nil,
            quantitySamples: [],
            categorySamples: [
                category("SleepAnalysis", "InBed", from: at(23), to: nextDay(6)),
                category("SleepAnalysis", "Awake", from: at(22), to: at(23)),
            ],
            workouts: [])
        let s = AuraIngest.summary(from: payload, on: dayKey)
        XCTAssertNil(s.sleepHours)
    }

    func testSummarySleepHoursRoundedToOneDecimal() {
        // 2h 33min = 153 min = 2.55h -> rounds to 2.6
        let payload = IngestPayload(
            person: nil,
            quantitySamples: [],
            categorySamples: [
                category("SleepAnalysis", "AsleepUnspecified", from: at(1), to: at(3, 33)),
            ],
            workouts: [])
        let s = AuraIngest.summary(from: payload, on: dayKey)
        XCTAssertEqual(s.sleepHours!, 2.6, accuracy: 1e-6)
    }

    func testSummaryDayOfWeekAndWeekIso() {
        // 2026-05-20 is a Wednesday.
        let payload = IngestPayload(person: nil, quantitySamples: [],
                                    categorySamples: [], workouts: [])
        let s = AuraIngest.summary(from: payload, on: dayKey)
        XCTAssertEqual(s.dayOfWeek, "Wednesday")
        XCTAssertNotNil(s.weekIso)
        XCTAssertTrue(s.weekIso!.contains("-W"))
    }

    // MARK: - sleepInputs

    func testSleepInputsAggregatesPerDay() {
        let payload = IngestPayload(
            person: nil,
            quantitySamples: [],
            categorySamples: [
                category("SleepAnalysis", "InBed", from: at(23), to: nextDay(7)),       // 8h in bed
                category("SleepAnalysis", "AsleepCore", from: at(23, 30), to: nextDay(3)), // 3.5h
                category("SleepAnalysis", "AsleepREM", from: nextDay(3), to: nextDay(6)),  // 3h next day
            ],
            workouts: [])
        let inputs = AuraIngest.sleepInputs(from: payload)
        // Two days have asleep minutes: dayKey (3.5h core) and nextDay (3h rem)
        XCTAssertEqual(inputs.count, 2)
        let dayInput = inputs.first { $0.date == dayKey }
        XCTAssertNotNil(dayInput)
        XCTAssertEqual(dayInput!.asleepMinutes, 210.0, accuracy: 1e-6) // 3.5h = 210 min
        // in-bed sample (8h = 480 min) is keyed to dayKey too
        XCTAssertEqual(dayInput!.inBedMinutes!, 480.0, accuracy: 1e-6)
    }

    func testSleepInputsDropsDaysWithNoAsleep() {
        let payload = IngestPayload(
            person: nil,
            quantitySamples: [],
            categorySamples: [
                category("SleepAnalysis", "InBed", from: at(23), to: nextDay(7)),
                category("SleepAnalysis", "Awake", from: at(22), to: at(23)),
            ],
            workouts: [])
        let inputs = AuraIngest.sleepInputs(from: payload)
        XCTAssertTrue(inputs.isEmpty)
    }

    func testSleepInputsInBedNilWhenAbsent() {
        let payload = IngestPayload(
            person: nil,
            quantitySamples: [],
            categorySamples: [
                category("SleepAnalysis", "AsleepCore", from: at(1), to: at(5)),  // 4h, no InBed
            ],
            workouts: [])
        let inputs = AuraIngest.sleepInputs(from: payload)
        XCTAssertEqual(inputs.count, 1)
        XCTAssertEqual(inputs[0].asleepMinutes, 240.0, accuracy: 1e-6)
        XCTAssertNil(inputs[0].inBedMinutes)
    }

    func testSleepInputsIgnoresNonSleepCategories() {
        let payload = IngestPayload(
            person: nil,
            quantitySamples: [],
            categorySamples: [
                category("MindfulSession", "Asleep", from: at(1), to: at(2)),  // wrong type
            ],
            workouts: [])
        let inputs = AuraIngest.sleepInputs(from: payload)
        XCTAssertTrue(inputs.isEmpty)
    }

    // MARK: - uniqueDays

    func testUniqueDaysAcrossSampleKinds() {
        let payload = IngestPayload(
            person: nil,
            quantitySamples: [quantity("StepCount", 100, at: at(8))],          // dayKey
            categorySamples: [category("SleepAnalysis", "AsleepCore",
                                       from: nextDay(1), to: nextDay(3))],      // nextDay
            workouts: [workout("Running", from: at(7), to: at(8))])            // dayKey
        let days = AuraIngest.uniqueDays(in: payload)
        XCTAssertEqual(days, [dayKey, "2026-05-21"])  // sorted ascending, deduped
    }

    func testUniqueDaysEmptyPayload() {
        let payload = IngestPayload(person: nil, quantitySamples: [],
                                    categorySamples: [], workouts: [])
        XCTAssertTrue(AuraIngest.uniqueDays(in: payload).isEmpty)
    }

    func testUniqueDaysSortedAndDeduped() {
        let payload = IngestPayload(
            person: nil,
            quantitySamples: [
                quantity("StepCount", 1, at: nextDay(8)),
                quantity("HeartRate", 60, at: at(8)),
                quantity("HeartRate", 62, at: at(9)),  // same day duplicate
            ],
            categorySamples: [],
            workouts: [])
        let days = AuraIngest.uniqueDays(in: payload)
        XCTAssertEqual(days, [dayKey, "2026-05-21"])
    }

    // MARK: - workoutInputs

    func testWorkoutInputsMapFields() {
        let payload = IngestPayload(
            person: nil,
            quantitySamples: [],
            categorySamples: [],
            workouts: [workout("Running", from: at(7), to: at(8), uuid: "abc-123")])
        let inputs = AuraIngest.workoutInputs(from: payload)
        XCTAssertEqual(inputs.count, 1)
        XCTAssertEqual(inputs[0].uid, "abc-123")
        XCTAssertEqual(inputs[0].activityType, "Running")
        XCTAssertEqual(inputs[0].durationMin!, 60.0, accuracy: 1e-6)
    }

    func testWorkoutInputsSynthesizesUidWhenMissing() {
        let payload = IngestPayload(
            person: nil,
            quantitySamples: [],
            categorySamples: [],
            workouts: [workout("Cycling", from: at(7), to: at(8), uuid: nil)])
        let inputs = AuraIngest.workoutInputs(from: payload)
        XCTAssertEqual(inputs.count, 1)
        XCTAssertTrue(inputs[0].uid.hasPrefix("Cycling-"))
    }
}
