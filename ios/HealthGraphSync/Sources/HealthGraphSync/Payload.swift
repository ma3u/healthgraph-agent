import Foundation

/// Matches backend/models.py IngestPayload. Field names use camelCase here and
/// are converted to snake_case by APIClient's encoder.
struct IngestPayload: Codable {
    var person: PersonInfo?
    var quantitySamples: [QuantitySample]
    var categorySamples: [CategorySample]
    var workouts: [WorkoutPayload]
    var dateRangeStart: Date?
    var dateRangeEnd: Date?
    var clientAnchor: String?
}

struct PersonInfo: Codable {
    var dateOfBirth: String?
    var biologicalSex: String?
    var bloodType: String?
}

struct QuantitySample: Codable {
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

struct CategorySample: Codable {
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

struct WorkoutPayload: Codable {
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

struct IngestResponse: Codable {
    var acceptedSamples: Int
    var acceptedWorkouts: Int
    var daysAffected: [String]
    var serverAnchor: String
}
