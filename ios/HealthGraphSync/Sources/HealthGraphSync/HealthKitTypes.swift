import Foundation
import HealthKit

/// Single source of truth for the HealthKit identifiers the app reads, and the
/// cleaned names that match etl/transform.py's HEART_RATE_TYPES / STEP_TYPES /
/// etc. Keep this list in sync with transform.py — if you add a type here, also
/// add it to the right *_TYPES set there so daily summaries pick it up.
enum HealthKitTypes {
    // Quantity types we read.
    static let quantities: [(id: HKQuantityTypeIdentifier, display: String, unit: HKUnit)] = [
        (.heartRate, "HeartRate", .count().unitDivided(by: .minute())),
        (.restingHeartRate, "RestingHeartRate", .count().unitDivided(by: .minute())),
        (.heartRateVariabilitySDNN, "HeartRateVariabilitySDNN", .secondUnit(with: .milli)),
        (.stepCount, "StepCount", .count()),
        (.distanceWalkingRunning, "DistanceWalkingRunning", .meter()),
        (.activeEnergyBurned, "ActiveEnergyBurned", .kilocalorie()),
        (.basalEnergyBurned, "BasalEnergyBurned", .kilocalorie()),
        (.flightsClimbed, "FlightsClimbed", .count()),
        (.oxygenSaturation, "OxygenSaturation", .percent()),
        (.respiratoryRate, "RespiratoryRate", .count().unitDivided(by: .minute())),
        (.bodyMass, "BodyMass", .gramUnit(with: .kilo)),
        (.vo2Max, "VO2Max", HKUnit(from: "ml/kg*min")),
        (.appleExerciseTime, "AppleExerciseTime", .minute()),
    ]

    /// Category types we read.
    static let categories: [(id: HKCategoryTypeIdentifier, display: String)] = [
        (.sleepAnalysis, "SleepAnalysis"),
        (.appleStandHour, "AppleStandHour"),
    ]

    /// All HK types the app requests authorization for, including HKWorkoutType.
    static var allReadTypes: Set<HKObjectType> {
        var types: Set<HKObjectType> = []
        for q in quantities {
            if let t = HKQuantityType.quantityType(forIdentifier: q.id) { types.insert(t) }
        }
        for c in categories {
            if let t = HKCategoryType.categoryType(forIdentifier: c.id) { types.insert(t) }
        }
        types.insert(HKObjectType.workoutType())
        if let dob = HKObjectType.characteristicType(forIdentifier: .dateOfBirth) { types.insert(dob) }
        if let sex = HKObjectType.characteristicType(forIdentifier: .biologicalSex) { types.insert(sex) }
        return types
    }

    /// Map an HKCategoryValueSleepAnalysis raw value to the cleaned string the
    /// etl/ pipeline expects (matches parse_health_xml.clean_category_value).
    static func sleepAnalysisName(_ raw: Int) -> String {
        switch raw {
        case HKCategoryValueSleepAnalysis.inBed.rawValue: return "InBed"
        case HKCategoryValueSleepAnalysis.asleepUnspecified.rawValue: return "AsleepUnspecified"
        case HKCategoryValueSleepAnalysis.awake.rawValue: return "Awake"
        case HKCategoryValueSleepAnalysis.asleepCore.rawValue: return "AsleepCore"
        case HKCategoryValueSleepAnalysis.asleepDeep.rawValue: return "AsleepDeep"
        case HKCategoryValueSleepAnalysis.asleepREM.rawValue: return "AsleepREM"
        default: return "Unknown"
        }
    }

    /// Map an HKCategoryValueAppleStandHour to a cleaned name.
    static func standHourName(_ raw: Int) -> String {
        switch raw {
        case HKCategoryValueAppleStandHour.stood.rawValue: return "Stood"
        case HKCategoryValueAppleStandHour.idle.rawValue: return "Idle"
        default: return "Unknown"
        }
    }

    /// Cleaned name for HKWorkoutActivityType — matches parse_health_xml.clean_type.
    static func workoutActivityName(_ type: HKWorkoutActivityType) -> String {
        // The raw enum name (e.g. .running) is the cleanest path; the iOS
        // export XML uses HKWorkoutActivityTypeRunning, so we just produce the
        // suffix.
        switch type {
        case .running: return "Running"
        case .walking: return "Walking"
        case .cycling: return "Cycling"
        case .swimming: return "Swimming"
        case .hiking: return "Hiking"
        case .yoga: return "Yoga"
        case .functionalStrengthTraining: return "FunctionalStrengthTraining"
        case .traditionalStrengthTraining: return "TraditionalStrengthTraining"
        case .highIntensityIntervalTraining: return "HighIntensityIntervalTraining"
        case .rowing: return "Rowing"
        case .elliptical: return "Elliptical"
        case .stairClimbing: return "StairClimbing"
        case .pilates: return "Pilates"
        case .mixedCardio: return "MixedCardio"
        case .coreTraining: return "CoreTraining"
        case .other: return "Other"
        @unknown default: return "Other"
        }
    }
}
