import SwiftUI

/// Whoop-style dashboard rendered natively from on-device HealthKit data.
/// Works with the Aura instance paused — no network, no graph. Mirrors the
/// committed offline snapshot (`scripts/render_dashboard_snapshot.py`).
@MainActor
final class OfflineDashboardModel: ObservableObject {
    @Published var scores: [Scoring.DayScore] = []
    @Published var streaks: [(label: String, count: Int)] = []
    @Published var hypnogram: [SleepSegment] = []
    @Published var loading = false
    @Published var error: String?

    func load() async {
        loading = true
        error = nil
        do {
            let total = Scoring.displayDays + Scoring.baselineDays
            let summaries = try await HealthKitService.shared.dailySummaries(daysBack: total)
            scores = Scoring.buildScores(summaries)
            streaks = Self.streaks(from: summaries)
            hypnogram = (try? await HealthKitService.shared.lastNightHypnogram()) ?? []
        } catch {
            self.error = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        }
        loading = false
    }

    /// Consecutive days (newest backwards) meeting each goal. Counts only.
    private static func streaks(from days: [Scoring.DaySummary]) -> [(String, Int)] {
        func streak(_ pred: (Scoring.DaySummary) -> Bool) -> Int {
            var n = 0
            for d in days.reversed() { if pred(d) { n += 1 } else { break } }
            return n
        }
        return [
            ("Sleep ≥ 7.5h", streak { ($0.sleepHours ?? 0) >= 7.5 }),
            ("Steps ≥ 10k", streak { ($0.steps ?? 0) >= 10000 }),
            ("RHR < 60", streak { ($0.rhr ?? 999) < 60 }),
            ("HRV ≥ 38", streak { ($0.hrv ?? 0) >= 38 }),
        ].filter { $0.1 > 0 }
    }
}

struct OfflineDashboardView: View {
    @StateObject private var model = OfflineDashboardModel()

    var body: some View {
        Group {
            if model.loading && model.scores.isEmpty {
                ProgressView("Reading HealthKit…").frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if let err = model.error {
                ContentUnavailableView("Couldn’t load HealthKit",
                                       systemImage: "exclamationmark.triangle", description: Text(err))
            } else if !model.scores.isEmpty {
                ScrollView {
                    VStack(spacing: 16) {
                        cards()
                        if !model.hypnogram.isEmpty { hypnogramCard }
                        if !model.streaks.isEmpty { streaksGrid }
                        Text("On-device · works while Aura is paused" + latestDataNote)
                            .font(.caption2).foregroundStyle(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .padding()
                }
            } else {
                ContentUnavailableView("No recent HealthKit data",
                                       systemImage: "heart.text.square",
                                       description: Text("Grant Health access and make sure recent data exists."))
            }
        }
        .task { await model.load() }
        .refreshable { await model.load() }
    }

    /// Each card shows the most recent day that actually has that metric — so an
    /// empty "today" (no HRV/sleep recorded yet this morning) still shows real
    /// numbers from the latest day that has them.
    private func cards() -> some View {
        let recDay = model.scores.last { $0.recovery != nil }
        let slpDay = model.scores.last { $0.sleep != nil }
        let strDay = model.scores.last { $0.strain > 0 } ?? model.scores.last
        let vo2Day = model.scores.last { $0.vo2max != nil }
        let rec = model.scores.suffix(Scoring.displayDays).map { $0.recovery }
        let str = model.scores.suffix(Scoring.displayDays).map { Optional($0.strain) }
        let slp = model.scores.suffix(Scoring.displayDays).map { $0.sleep }
        let vo2 = model.scores.suffix(Scoring.displayDays).map { $0.vo2max }
        let vo2vals = vo2.compactMap { $0 }
        let vo2lo = (vo2vals.min() ?? 0) - 1
        let vo2hi = (vo2vals.max() ?? 60) + 1
        let hrvDay = model.scores.last { $0.hrv != nil }
        let rhrDay = model.scores.last { $0.rhr != nil }
        let hrvS = model.scores.suffix(Scoring.displayDays).map { $0.hrv }
        let rhrS = model.scores.suffix(Scoring.displayDays).map { $0.rhr }
        let hrvVals = hrvS.compactMap { $0 }
        let rhrVals = rhrS.compactMap { $0 }
        return VStack(spacing: 12) {
            metric("Recovery",
                   recDay?.recovery.map { "\(Int($0.rounded()))" } ?? "—", "%",
                   recDay?.recovery.map { Scoring.recoveryZone($0) } ?? "No recent data",
                   recDay?.recovery.map { zoneColor(Scoring.recoveryZone($0)) } ?? .secondary,
                   rec, 100, asOf: recDay?.recovery != nil ? recDay?.date : nil)
            metric("Strain",
                   strDay.map { String(format: "%.1f", $0.strain) } ?? "—", "/21",
                   strDay.map { Scoring.strainBand($0.strain) } ?? "No recent data",
                   .blue, str, 21, asOf: strDay?.date)
            metric("Sleep",
                   slpDay?.sleep.map { "\(Int($0.rounded()))" } ?? "—", "%",
                   slpDay != nil ? "Performance" : "No recent data",
                   .purple, slp, 100, asOf: slpDay?.date)
            // VO₂max — the #1 longevity predictor (raw mL/kg/min, min-max scaled trend).
            metric("VO₂ Max",
                   vo2Day?.vo2max.map { String(format: "%.1f", $0) } ?? "—", " ml/kg·min",
                   vo2Day != nil ? "Cardio fitness" : "No recent data",
                   .teal, vo2, vo2hi, vmin: vo2lo, asOf: vo2Day?.date)
            metric("HRV",
                   hrvDay?.hrv.map { String(format: "%.0f", $0) } ?? "—", " ms",
                   hrvDay != nil ? "Higher is better" : "No recent data",
                   .mint, hrvS, (hrvVals.max() ?? 80) + 5,
                   vmin: max((hrvVals.min() ?? 0) - 5, 0), asOf: hrvDay?.date)
            metric("Resting HR",
                   rhrDay?.rhr.map { String(format: "%.0f", $0) } ?? "—", " bpm",
                   rhrDay != nil ? "Lower is better" : "No recent data",
                   .pink, rhrS, (rhrVals.max() ?? 70) + 3,
                   vmin: max((rhrVals.min() ?? 40) - 3, 0), asOf: rhrDay?.date)
        }
    }

    private var latestDataNote: String {
        let d = model.scores.last(where: { $0.recovery != nil })?.date
            ?? model.scores.last(where: { $0.sleep != nil })?.date
            ?? model.scores.last?.date
        guard let d else { return "" }
        return " · latest data " + d.formatted(date: .abbreviated, time: .omitted)
    }

    private func metric(_ title: String, _ value: String, _ unit: String,
                        _ sub: String, _ color: Color, _ series: [Double?], _ vmax: Double,
                        vmin: Double = 0, asOf: Date? = nil) -> some View {
        VStack(spacing: 6) {
            Text(title.uppercased()).font(.caption2).tracking(1.5).foregroundStyle(.secondary)
            HStack(alignment: .firstTextBaseline, spacing: 2) {
                Text(value).font(.system(size: 46, weight: .thin))
                Text(unit).font(.callout).foregroundStyle(.secondary)
            }
            .foregroundStyle(color)
            .monospacedDigit()
            Text(sub).font(.caption).fontWeight(.semibold).foregroundStyle(color)
            Sparkline(values: series, vmin: vmin, vmax: vmax, color: color).frame(height: 34)
            if let asOf, !Calendar.current.isDateInToday(asOf) {
                Text("as of " + asOf.formatted(.dateTime.month().day()))
                    .font(.caption2).foregroundStyle(.tertiary)
            }
        }
        .frame(maxWidth: .infinity)
        .padding()
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 18))
    }

    private var hypnogramCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("LAST NIGHT").font(.caption2).tracking(1.5).foregroundStyle(.secondary)
            HypnogramView(segments: model.hypnogram)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 18))
    }

    private var streaksGrid: some View {
        LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 2), spacing: 8) {
            ForEach(model.streaks, id: \.label) { s in
                VStack(spacing: 2) {
                    Text("\(s.count)").font(.title2).bold()
                    Text(s.label).font(.caption2).foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 10)
                .background(.quaternary.opacity(0.4), in: RoundedRectangle(cornerRadius: 12))
            }
        }
    }

    private func zoneColor(_ zone: String) -> Color {
        switch zone {
        case "GREEN": return .green
        case "YELLOW": return .orange
        case "RED": return .red
        default: return .secondary
        }
    }
}

/// Minimal inline line chart for a series of optional values (nil = gap).
struct Sparkline: View {
    let values: [Double?]
    var vmin: Double = 0
    let vmax: Double
    let color: Color

    var body: some View {
        GeometryReader { geo in
            let pts = points(in: geo.size)
            Path { p in
                guard let first = pts.first else { return }
                p.move(to: first)
                for pt in pts.dropFirst() { p.addLine(to: pt) }
            }
            .stroke(color, style: StrokeStyle(lineWidth: 2, lineCap: .round, lineJoin: .round))
            .opacity(0.85)
        }
    }

    private func points(in size: CGSize) -> [CGPoint] {
        let n = max(values.count - 1, 1)
        let span = max(vmax - vmin, 0.0001)
        var out: [CGPoint] = []
        for (i, v) in values.enumerated() {
            guard let v else { continue }
            let x = size.width * CGFloat(i) / CGFloat(n)
            let clamped = min(max(v, vmin), vmax)
            let y = size.height * (1 - CGFloat((clamped - vmin) / span))
            out.append(CGPoint(x: x, y: y))
        }
        return out
    }
}
