import XCTest
@testable import HealthGraphSync

/// Parity tests for `Scoring.swift` — verifies the on-device port matches the
/// formulas in `docs/SCORING.md` and the Python reference in
/// `scripts/render_dashboard_snapshot.py` (recovery_score / strain_score /
/// sleep_performance / recovery_zone / strain_band).
final class ScoringTests: XCTestCase {

    private let acc = 1e-9

    // MARK: - sleepPerformance

    func testSleepPerformanceNilWhenNoData() {
        XCTAssertNil(Scoring.sleepPerformance(nil))
    }

    func testSleepPerformanceBelowNeedAppliesAssumedEfficiency() {
        // duration = min(6 / 7.5, 1) * 100 = 80; * 0.92 = 73.6
        let p = Scoring.sleepPerformance(6.0)
        XCTAssertNotNil(p)
        XCTAssertEqual(p!, 73.6, accuracy: 1e-6)
    }

    func testSleepPerformanceCapsDurationAtNeed() {
        // 9h > need 7.5h -> duration clamps to 100; * 0.92 = 92
        let p = Scoring.sleepPerformance(9.0)
        XCTAssertNotNil(p)
        XCTAssertEqual(p!, 92.0, accuracy: 1e-6)
    }

    func testSleepPerformanceExactlyNeed() {
        // 7.5 / 7.5 = 1 -> 100 * 0.92 = 92
        XCTAssertEqual(Scoring.sleepPerformance(7.5)!, 92.0, accuracy: 1e-6)
    }

    func testSleepPerformanceCustomNeed() {
        // need = 8 -> duration = min(4/8,1)*100 = 50; * 0.92 = 46
        XCTAssertEqual(Scoring.sleepPerformance(4.0, need: 8.0)!, 46.0, accuracy: 1e-6)
    }

    // MARK: - recovery

    func testRecoveryNilWhenHrvMissing() {
        XCTAssertNil(Scoring.recovery(hrv: nil, rhr: 55, sleepPerf: 80,
                                      hrvMean: 50, hrvStd: 10,
                                      rhrMean: 55, rhrStd: 5))
    }

    func testRecoveryNilWhenRhrMissing() {
        XCTAssertNil(Scoring.recovery(hrv: 60, rhr: nil, sleepPerf: 80,
                                      hrvMean: 50, hrvStd: 10,
                                      rhrMean: 55, rhrStd: 5))
    }

    func testRecoveryAtBaselineIsFifty() {
        // hrv_z = 0, rhr_z = 0 -> hrvC = 50, rhrC = 50, sleepC = 50
        // 0.60*50 + 0.20*50 + 0.20*50 = 50
        let r = Scoring.recovery(hrv: 50, rhr: 55, sleepPerf: 50,
                                 hrvMean: 50, hrvStd: 10,
                                 rhrMean: 55, rhrStd: 5)
        XCTAssertEqual(r!, 50.0, accuracy: 1e-9)
    }

    func testRecoveryNominalCase() {
        // hrv 70, mean 50, std 10 -> hz = 2 -> hrvC = clamp(50+50)=100
        // rhr 50, mean 55, std 5 -> rz = -1 -> rhrC = clamp(50 - 25*(-1)) = 75
        // sleepPerf = 80
        // 0.60*100 + 0.20*75 + 0.20*80 = 60 + 15 + 16 = 91
        let r = Scoring.recovery(hrv: 70, rhr: 50, sleepPerf: 80,
                                 hrvMean: 50, hrvStd: 10,
                                 rhrMean: 55, rhrStd: 5)
        XCTAssertEqual(r!, 91.0, accuracy: 1e-9)
    }

    func testRecoveryClampsComponents() {
        // hrv far above baseline -> hrvC clamps to 100
        // rhr far above baseline -> rhrC clamps to 0
        // sleepPerf 0
        // 0.60*100 + 0.20*0 + 0.20*0 = 60
        let r = Scoring.recovery(hrv: 200, rhr: 200, sleepPerf: 0,
                                 hrvMean: 50, hrvStd: 10,
                                 rhrMean: 55, rhrStd: 5)
        XCTAssertEqual(r!, 60.0, accuracy: 1e-9)
    }

    func testRecoveryZeroStdTreatsZAsZero() {
        // std = 0 -> z = 0 -> both components 50
        // sleepPerf nil -> defaults to 50
        // result = 50
        let r = Scoring.recovery(hrv: 99, rhr: 99, sleepPerf: nil,
                                 hrvMean: 50, hrvStd: 0,
                                 rhrMean: 55, rhrStd: 0)
        XCTAssertEqual(r!, 50.0, accuracy: 1e-9)
    }

    func testRecoveryDefaultsSleepComponentToFiftyWhenNil() {
        // hrv_z = 0, rhr_z = 0, sleepPerf nil -> 50 each -> 50
        let r = Scoring.recovery(hrv: 50, rhr: 55, sleepPerf: nil,
                                 hrvMean: 50, hrvStd: 10,
                                 rhrMean: 55, rhrStd: 5)
        XCTAssertEqual(r!, 50.0, accuracy: 1e-9)
    }

    // MARK: - strain

    func testStrainZeroWhenNoActivity() {
        // ae = 0, wm = 0 -> raw = 0/8 = 0 -> 21*(1-e^0) = 0
        XCTAssertEqual(Scoring.strain(activeKcal: 0, workoutMin: 0), 0.0, accuracy: 1e-12)
    }

    func testStrainNilInputsTreatedAsZero() {
        XCTAssertEqual(Scoring.strain(activeKcal: nil, workoutMin: nil), 0.0, accuracy: 1e-12)
    }

    func testStrainRestDayProxy() {
        // no workout: raw = ae / target = 440 / 8 = 55
        // 21 * (1 - exp(-55/220)) = 21 * (1 - exp(-0.25))
        let expected = 21.0 * (1.0 - exp(-(440.0 / 8.0) / 220.0))
        XCTAssertEqual(Scoring.strain(activeKcal: 440, workoutMin: 0), expected, accuracy: 1e-9)
    }

    func testStrainHardSessionMatchesFormula() {
        // 60 min, 480 kcal -> intensity = 480/60 = 8 = target
        // raw = 60 * (8/8)^1.92 = 60
        // 21 * (1 - exp(-60/220))
        let expected = 21.0 * (1.0 - exp(-60.0 / 220.0))
        let s = Scoring.strain(activeKcal: 480, workoutMin: 60)
        XCTAssertEqual(s, expected, accuracy: 1e-9)
    }

    func testStrainHardSessionScoresAboveEasyWalk() {
        // docs intent: the ^1.92 exponent makes a hard session score well above
        // a longer easy one. A high-intensity hour matches the closed-form
        // formula and beats a same-duration low-intensity hour.
        // intensity = 720/60 = 12; raw = 60 * (12/8)^1.92.
        let hard = Scoring.strain(activeKcal: 720, workoutMin: 60)
        let expected = 21.0 * (1.0 - exp(-(60.0 * pow(12.0 / 8.0, 1.92)) / 220.0))
        XCTAssertEqual(hard, expected, accuracy: 1e-9)

        let easyWalk = Scoring.strain(activeKcal: 240, workoutMin: 60) // 4 kcal/min
        XCTAssertGreaterThan(hard, easyWalk)
    }

    func testStrainIsMonotonicInLoad() {
        let light = Scoring.strain(activeKcal: 200, workoutMin: 60)
        let hard = Scoring.strain(activeKcal: 800, workoutMin: 60)
        XCTAssertGreaterThan(hard, light)
    }

    func testStrainNeverExceedsTwentyOne() {
        let s = Scoring.strain(activeKcal: 100000, workoutMin: 300)
        XCTAssertLessThanOrEqual(s, 21.0)
    }

    func testStrainCustomTargetAndScaling() {
        // wm = 30, ae = 300 -> intensity = 10; target = 10 -> raw = 30 * 1^1.92 = 30
        // 21 * (1 - exp(-30/100))
        let expected = 21.0 * (1.0 - exp(-30.0 / 100.0))
        let s = Scoring.strain(activeKcal: 300, workoutMin: 30, target: 10, scaling: 100)
        XCTAssertEqual(s, expected, accuracy: 1e-9)
    }

    // MARK: - recoveryZone

    func testRecoveryZoneGreen() {
        XCTAssertEqual(Scoring.recoveryZone(100), "GREEN")
        XCTAssertEqual(Scoring.recoveryZone(67), "GREEN")   // lower boundary inclusive
    }

    func testRecoveryZoneYellow() {
        XCTAssertEqual(Scoring.recoveryZone(66), "YELLOW")
        XCTAssertEqual(Scoring.recoveryZone(34), "YELLOW")  // lower boundary inclusive
    }

    func testRecoveryZoneRed() {
        XCTAssertEqual(Scoring.recoveryZone(33), "RED")
        XCTAssertEqual(Scoring.recoveryZone(0), "RED")
    }

    // MARK: - strainBand

    func testStrainBandLight() {
        XCTAssertEqual(Scoring.strainBand(0), "Light")
        XCTAssertEqual(Scoring.strainBand(8.999), "Light")
    }

    func testStrainBandModerate() {
        XCTAssertEqual(Scoring.strainBand(9), "Moderate")
        XCTAssertEqual(Scoring.strainBand(12.999), "Moderate")
    }

    func testStrainBandStrenuous() {
        XCTAssertEqual(Scoring.strainBand(13), "Strenuous")
        XCTAssertEqual(Scoring.strainBand(16.999), "Strenuous")
    }

    func testStrainBandAllOut() {
        XCTAssertEqual(Scoring.strainBand(17), "All-out")
        XCTAssertEqual(Scoring.strainBand(21), "All-out")
    }

    // MARK: - buildScores

    private func day(_ offsetDays: Int, hrv: Double?, rhr: Double?,
                     sleepHours: Double?, activeKcal: Double?, workoutMin: Double?) -> Scoring.DaySummary {
        let base = Date(timeIntervalSince1970: 1_700_000_000)
        let date = base.addingTimeInterval(Double(offsetDays) * 86_400)
        return Scoring.DaySummary(date: date, hrv: hrv, rhr: rhr,
                                  sleepHours: sleepHours, steps: nil,
                                  activeKcal: activeKcal, workoutMin: workoutMin)
    }

    func testBuildScoresEmptyInput() {
        XCTAssertTrue(Scoring.buildScores([]).isEmpty)
    }

    func testBuildScoresFirstDayHasZeroBaseline() {
        // First day: window is empty -> mean/std = 0 -> z forced to 0 -> components 50
        // sleep 6h -> sleepPerf 73.6; recovery = 0.60*50 + 0.20*50 + 0.20*73.6 = 64.72
        let days = [day(0, hrv: 60, rhr: 55, sleepHours: 6, activeKcal: 480, workoutMin: 60)]
        let scores = Scoring.buildScores(days)
        XCTAssertEqual(scores.count, 1)
        let s = scores[0]
        XCTAssertNotNil(s.recovery)
        XCTAssertEqual(s.recovery!, 0.60 * 50 + 0.20 * 50 + 0.20 * 73.6, accuracy: 1e-6)
        XCTAssertEqual(s.sleep!, 73.6, accuracy: 1e-6)
        // strain matches the standalone function
        XCTAssertEqual(s.strain, Scoring.strain(activeKcal: 480, workoutMin: 60), accuracy: 1e-9)
    }

    func testBuildScoresUsesTrailingBaselineExcludingCurrentDay() {
        // Build 3 baseline days at hrv 50 (std 0), then a 4th day hrv 50.
        // Baseline for day index 3 = days 0..2 -> mean 50, std 0 -> z = 0 -> hrvC 50.
        var days: [Scoring.DaySummary] = []
        for i in 0..<3 {
            days.append(day(i, hrv: 50, rhr: 55, sleepHours: 7.5, activeKcal: 0, workoutMin: 0))
        }
        days.append(day(3, hrv: 50, rhr: 55, sleepHours: 7.5, activeKcal: 0, workoutMin: 0))
        let scores = Scoring.buildScores(days)
        XCTAssertEqual(scores.count, 4)
        // sleepPerf(7.5) = 92; recovery = 0.6*50 + 0.2*50 + 0.2*92 = 58.4
        XCTAssertEqual(scores[3].recovery!, 0.60 * 50 + 0.20 * 50 + 0.20 * 92.0, accuracy: 1e-6)
    }

    func testBuildScoresElevatedHrvRaisesRecovery() {
        // baseline days hrv 50, then a day with hrv well above baseline.
        var days: [Scoring.DaySummary] = []
        for i in 0..<5 {
            // vary hrv slightly so std > 0
            let hrv = 50.0 + Double(i % 2)
            days.append(day(i, hrv: hrv, rhr: 55, sleepHours: 7.5, activeKcal: 0, workoutMin: 0))
        }
        days.append(day(5, hrv: 80, rhr: 55, sleepHours: 7.5, activeKcal: 0, workoutMin: 0))
        let scores = Scoring.buildScores(days)
        // The elevated-HRV day should score higher recovery than a baseline-level day.
        XCTAssertNotNil(scores[5].recovery)
        XCTAssertGreaterThan(scores[5].recovery!, 58.0)
    }

    func testBuildScoresRecoveryNilWhenMissingHrvOrRhr() {
        let days = [day(0, hrv: nil, rhr: 55, sleepHours: 7.5, activeKcal: 0, workoutMin: 0)]
        let scores = Scoring.buildScores(days)
        XCTAssertNil(scores[0].recovery)
        // strain and sleep still computed
        XCTAssertEqual(scores[0].sleep!, 92.0, accuracy: 1e-6)
    }

    func testBuildScoresPreservesDateAndOrder() {
        let days = [
            day(0, hrv: 50, rhr: 55, sleepHours: 7, activeKcal: 100, workoutMin: 0),
            day(1, hrv: 52, rhr: 54, sleepHours: 8, activeKcal: 200, workoutMin: 0),
        ]
        let scores = Scoring.buildScores(days)
        XCTAssertEqual(scores.count, 2)
        XCTAssertEqual(scores[0].date, days[0].date)
        XCTAssertEqual(scores[1].date, days[1].date)
    }
}
