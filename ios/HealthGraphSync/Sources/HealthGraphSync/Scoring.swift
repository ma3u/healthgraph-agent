import Foundation

/// On-device port of `docs/SCORING.md` (mirrors `scripts/render_dashboard_snapshot.py`).
/// Recovery 0–100, Strain 0–21, Sleep 0–100 — computed from daily aggregates,
/// fully offline (no Aura, no graph). NoopApp/noop was used only as a benchmark
/// (issue #13); no noop code is reused.
enum Scoring {
    /// One day's raw aggregates (the fields `AuraIngest.summary` produces).
    struct DaySummary {
        let date: Date
        var hrv: Double?
        var rhr: Double?
        var sleepHours: Double?
        var steps: Double?
        var activeKcal: Double?
        var workoutMin: Double?
        var vo2max: Double? = nil   // mL/kg/min (raw — longevity headline metric)
    }

    struct DayScore: Identifiable {
        let id = UUID()
        let date: Date
        let recovery: Double?   // 0–100
        let strain: Double      // 0–21
        let sleep: Double?      // 0–100
        let vo2max: Double?     // mL/kg/min (raw)
        let hrv: Double?        // ms (raw)
        let rhr: Double?        // bpm (raw)
    }

    static let displayDays = 30
    static let baselineDays = 30

    private static func clamp(_ x: Double, _ lo: Double = 0, _ hi: Double = 100) -> Double {
        max(lo, min(hi, x))
    }

    static func sleepPerformance(_ sleepHours: Double?, need: Double = 7.5) -> Double? {
        guard let h = sleepHours else { return nil }
        let duration = min(h / need, 1.0) * 100
        return clamp(duration * 0.92)   // assumed efficiency when no in-bed data
    }

    static func recovery(hrv: Double?, rhr: Double?, sleepPerf: Double?,
                         hrvMean: Double, hrvStd: Double,
                         rhrMean: Double, rhrStd: Double) -> Double? {
        guard let hrv, let rhr else { return nil }
        let hz = hrvStd > 0 ? (hrv - hrvMean) / hrvStd : 0
        let rz = rhrStd > 0 ? (rhr - rhrMean) / rhrStd : 0
        let hrvC = clamp(50 + 25 * hz)
        let rhrC = clamp(50 - 25 * rz)
        let sleepC = sleepPerf ?? 50
        return clamp(0.60 * hrvC + 0.20 * rhrC + 0.20 * sleepC)
    }

    static func strain(activeKcal: Double?, workoutMin: Double?,
                       target: Double = 8, scaling: Double = 220) -> Double {
        let ae = activeKcal ?? 0
        let wm = workoutMin ?? 0
        let raw: Double
        if wm > 0 {
            let intensity = ae / max(wm, 1)
            raw = wm * pow(intensity / target, 1.92)
        } else {
            raw = ae / target   // light-activity day proxy
        }
        return 21.0 * (1.0 - exp(-raw / scaling))
    }

    static func recoveryZone(_ r: Double) -> String {
        if r >= 67 { return "GREEN" }
        if r >= 34 { return "YELLOW" }
        return "RED"
    }

    static func strainBand(_ s: Double) -> String {
        switch s {
        case ..<9: return "Light"
        case ..<13: return "Moderate"
        case ..<17: return "Strenuous"
        default: return "All-out"
        }
    }

    /// `days` ascending by date → per-day scores using a trailing 30-day baseline
    /// (excludes the current day) for the HRV/RHR z-scores.
    static func buildScores(_ days: [DaySummary]) -> [DayScore] {
        var out: [DayScore] = []
        for (i, d) in days.enumerated() {
            let window = Array(days[max(0, i - baselineDays)..<i])
            let (hMean, hStd) = meanStd(window.compactMap { $0.hrv })
            let (rMean, rStd) = meanStd(window.compactMap { $0.rhr })
            let sp = sleepPerformance(d.sleepHours)
            out.append(DayScore(
                date: d.date,
                recovery: recovery(hrv: d.hrv, rhr: d.rhr, sleepPerf: sp,
                                   hrvMean: hMean, hrvStd: hStd,
                                   rhrMean: rMean, rhrStd: rStd),
                strain: strain(activeKcal: d.activeKcal, workoutMin: d.workoutMin),
                sleep: sp,
                vo2max: d.vo2max,
                hrv: d.hrv,
                rhr: d.rhr))
        }
        return out
    }

    private static func meanStd(_ xs: [Double]) -> (Double, Double) {
        guard !xs.isEmpty else { return (0, 0) }
        let mu = xs.reduce(0, +) / Double(xs.count)
        let variance = xs.reduce(0) { $0 + ($1 - mu) * ($1 - mu) } / Double(xs.count)
        return (mu, variance.squareRoot())
    }
}
