import SwiftUI

/// One sleep-stage segment of a night (from HealthKit SleepAnalysis samples).
struct SleepSegment: Identifiable {
    let id = UUID()
    let stage: SleepStage
    let start: Date
    let end: Date
    var minutes: Double { end.timeIntervalSince(start) / 60 }
}

enum SleepStage: String, CaseIterable, Hashable {
    case deep, core, rem, awake, asleep   // `asleep` = unspecified (pre-watchOS-9 data)

    var label: String {
        switch self {
        case .deep: return "Deep"
        case .core: return "Core"
        case .rem: return "REM"
        case .awake: return "Awake"
        case .asleep: return "Asleep"
        }
    }

    var color: Color {
        switch self {
        case .deep: return .indigo
        case .core: return .blue
        case .rem: return .cyan
        case .awake: return .orange
        case .asleep: return .teal
        }
    }

    /// Vertical lane: deep at the bottom, awake at the top (Whoop/noop convention).
    var lane: Int {
        switch self {
        case .deep: return 0
        case .core, .asleep: return 1
        case .rem: return 2
        case .awake: return 3
        }
    }
}

/// Whoop/noop-style hypnogram: stage bands across one night + a per-stage legend.
struct HypnogramView: View {
    let segments: [SleepSegment]
    private let lanes = 4

    var body: some View {
        if segments.count < 2 {
            Text("No staged sleep for last night")
                .font(.caption).foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .center)
        } else {
            VStack(alignment: .leading, spacing: 8) {
                chart.frame(height: 92)
                legend
            }
        }
    }

    private var bounds: (start: Date, end: Date) {
        (segments.map(\.start).min() ?? Date(), segments.map(\.end).max() ?? Date())
    }

    private var chart: some View {
        GeometryReader { geo in
            let (s, e) = bounds
            let total = max(e.timeIntervalSince(s), 1)
            let laneH = geo.size.height / CGFloat(lanes)
            ZStack(alignment: .topLeading) {
                ForEach(segments) { seg in
                    let x = geo.size.width * CGFloat(seg.start.timeIntervalSince(s) / total)
                    let w = max(geo.size.width * CGFloat(seg.end.timeIntervalSince(seg.start) / total), 1)
                    let y = laneH * CGFloat(lanes - 1 - seg.stage.lane) + laneH * 0.1
                    RoundedRectangle(cornerRadius: 2)
                        .fill(seg.stage.color)
                        .frame(width: w, height: laneH * 0.8)
                        .offset(x: x, y: y)
                }
            }
        }
    }

    private var legend: some View {
        let byStage = Dictionary(grouping: segments, by: \.stage).mapValues { $0.reduce(0) { $0 + $1.minutes } }
        return HStack(spacing: 12) {
            ForEach(SleepStage.allCases, id: \.self) { st in
                if let m = byStage[st], m > 0 {
                    HStack(spacing: 4) {
                        Circle().fill(st.color).frame(width: 7, height: 7)
                        Text("\(st.label) \(Int(m.rounded()))m").font(.caption2).foregroundStyle(.secondary)
                    }
                }
            }
        }
    }
}
