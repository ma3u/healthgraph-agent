"""
generate_test_data.py — Generate realistic synthetic Apple Health export.xml

Produces 12 months of data by default with:
  - Seasonal patterns (winter less active, summer more)
  - Weekly training cycles (hard/easy/rest days)
  - Realistic cross-metric correlations (poor sleep → higher resting HR)
  - Weekend vs weekday sleep differences
  - Body composition trends
  - Proper Apple device strings
  - Multiple workout types with realistic distributions
  - VO2Max, respiratory rate, blood oxygen readings
  - 4 persona profiles: default, athlete, sedentary, biohacker

Usage:
    python generate_test_data.py                          # 12 months
    python generate_test_data.py --days 90 -o test.xml    # 90 days
    python generate_test_data.py --persona athlete        # Athletic profile
    python generate_test_data.py --persona biohacker      # Optimization-focused
"""

import math
import random
import argparse
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Apple device strings (realistic format)
# ---------------------------------------------------------------------------

APPLE_WATCH_DEVICE = (
    '<<HKDevice: 0x0>, name:Apple Watch, manufacturer:Apple Inc., '
    'model:Watch, hardware:Watch6,2, software:10.4>'
)
IPHONE_DEVICE = (
    '<<HKDevice: 0x0>, name:iPhone, manufacturer:Apple Inc., '
    'model:iPhone, hardware:iPhone15,3, software:17.4>'
)

# ---------------------------------------------------------------------------
# Workout definitions
# ---------------------------------------------------------------------------

WORKOUT_PROFILES = {
    "Running": {
        "hk_type": "HKWorkoutActivityTypeRunning",
        "duration_mean": 35, "duration_std": 10,
        "hr_mean": 155, "hr_std": 12,
        "kcal_per_min": 11.0, "km_per_min": 0.14,
    },
    "Walking": {
        "hk_type": "HKWorkoutActivityTypeWalking",
        "duration_mean": 40, "duration_std": 15,
        "hr_mean": 110, "hr_std": 10,
        "kcal_per_min": 5.0, "km_per_min": 0.08,
    },
    "TraditionalStrengthTraining": {
        "hk_type": "HKWorkoutActivityTypeTraditionalStrengthTraining",
        "duration_mean": 50, "duration_std": 12,
        "hr_mean": 130, "hr_std": 15,
        "kcal_per_min": 7.5, "km_per_min": 0.0,
    },
    "Yoga": {
        "hk_type": "HKWorkoutActivityTypeYoga",
        "duration_mean": 30, "duration_std": 10,
        "hr_mean": 90, "hr_std": 8,
        "kcal_per_min": 3.5, "km_per_min": 0.0,
    },
    "Cycling": {
        "hk_type": "HKWorkoutActivityTypeCycling",
        "duration_mean": 45, "duration_std": 15,
        "hr_mean": 145, "hr_std": 12,
        "kcal_per_min": 9.0, "km_per_min": 0.35,
    },
    "HIIT": {
        "hk_type": "HKWorkoutActivityTypeHighIntensityIntervalTraining",
        "duration_mean": 25, "duration_std": 8,
        "hr_mean": 160, "hr_std": 10,
        "kcal_per_min": 12.0, "km_per_min": 0.0,
    },
    "Swimming": {
        "hk_type": "HKWorkoutActivityTypeSwimming",
        "duration_mean": 35, "duration_std": 10,
        "hr_mean": 140, "hr_std": 12,
        "kcal_per_min": 8.5, "km_per_min": 0.03,
    },
}

# ---------------------------------------------------------------------------
# Persona profiles
# ---------------------------------------------------------------------------

PERSONAS = {
    "default": {
        "name": "Default",
        "resting_hr_base": 64, "hrv_base": 42,
        "steps_base": 8000, "sleep_base": 7.2,
        "body_mass_start": 78.0, "body_mass_trend": -0.005,
        "vo2max_base": 38.0, "vo2max_trend": 0.003,
        "workout_probability": 0.55,
        "workout_types": ["Running", "Walking", "TraditionalStrengthTraining", "Yoga"],
        "dob": "1985-06-15", "sex": "HKBiologicalSexMale",
    },
    "athlete": {
        "name": "Athlete",
        "resting_hr_base": 52, "hrv_base": 65,
        "steps_base": 12000, "sleep_base": 7.8,
        "body_mass_start": 72.0, "body_mass_trend": -0.002,
        "vo2max_base": 48.0, "vo2max_trend": 0.005,
        "workout_probability": 0.80,
        "workout_types": ["Running", "Cycling", "TraditionalStrengthTraining", "HIIT", "Swimming"],
        "dob": "1990-03-22", "sex": "HKBiologicalSexFemale",
    },
    "sedentary": {
        "name": "Sedentary",
        "resting_hr_base": 74, "hrv_base": 28,
        "steps_base": 4500, "sleep_base": 6.5,
        "body_mass_start": 92.0, "body_mass_trend": 0.008,
        "vo2max_base": 30.0, "vo2max_trend": -0.002,
        "workout_probability": 0.20,
        "workout_types": ["Walking", "Yoga"],
        "dob": "1978-11-03", "sex": "HKBiologicalSexMale",
    },
    "biohacker": {
        "name": "Biohacker",
        "resting_hr_base": 58, "hrv_base": 55,
        "steps_base": 10000, "sleep_base": 7.5,
        "body_mass_start": 75.0, "body_mass_trend": -0.008,
        "vo2max_base": 42.0, "vo2max_trend": 0.008,
        "workout_probability": 0.65,
        "workout_types": ["Running", "TraditionalStrengthTraining", "HIIT", "Yoga", "Cycling"],
        "dob": "1988-01-20", "sex": "HKBiologicalSexMale",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def seasonal_modifier(day: date) -> float:
    """Activity multiplier 0.85–1.15 based on season. Peak in July."""
    doy = day.timetuple().tm_yday
    return 1.0 + 0.15 * math.sin(2 * math.pi * (doy - 80) / 365)


def weekly_training_load(day: date) -> str:
    """Mon=moderate, Tue=hard, Wed=easy, Thu=hard, Fri=moderate, Sat=hard, Sun=rest."""
    return {0: "moderate", 1: "hard", 2: "easy", 3: "hard",
            4: "moderate", 5: "hard", 6: "rest"}[day.weekday()]


def fmt_ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S +0100")


def fmt_date(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate(days: int = 365, output: str = "data/export.xml",
             persona: str = "default", seed: Optional[int] = None):
    if seed is not None:
        random.seed(seed)

    p = PERSONAS[persona]
    Path(output).parent.mkdir(parents=True, exist_ok=True)

    end_date = date.today() - timedelta(days=1)
    start_date = end_date - timedelta(days=days - 1)

    print(f"Generating {days} days of synthetic data ({fmt_date(start_date)} → {fmt_date(end_date)})")
    print(f"Persona: {p['name']} (RHR ~{p['resting_hr_base']}, HRV ~{p['hrv_base']}, "
          f"~{p['steps_base']:,} steps/day)")

    # State for cross-day correlations
    prev_sleep_quality = 0.5
    prev_workout_intensity = 0.0
    body_mass = p["body_mass_start"]
    vo2max = p["vo2max_base"]
    fitness_level = 1.0
    record_count = 0
    workout_count = 0

    with open(output, "w") as f:
        # --- Header ---
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<!DOCTYPE HealthData [\n')
        f.write('<!-- HealthKit Export Version: 13 -->\n')
        f.write(']>\n')
        f.write('<HealthData locale="en_DE">\n')
        f.write(f' <ExportDate value="{fmt_ts(datetime.now())}"/>\n')
        f.write(
            f' <Me HKCharacteristicTypeIdentifierDateOfBirth="{p["dob"]}"'
            f' HKCharacteristicTypeIdentifierBiologicalSex="{p["sex"]}"'
            f' HKCharacteristicTypeIdentifierBloodType="HKBloodTypeAPositive"'
            f' HKCharacteristicTypeIdentifierFitzpatrickSkinType='
            f'"HKFitzpatrickSkinTypeII"/>\n'
        )

        def write_rec(rec_type, source, unit, start, end, value, device=APPLE_WATCH_DEVICE):
            nonlocal record_count
            f.write(
                f' <Record type="{rec_type}" sourceName="{source}" '
                f'sourceVersion="17.4" device="{device}" '
                f'unit="{unit}" creationDate="{fmt_ts(end)}" '
                f'startDate="{fmt_ts(start)}" endDate="{fmt_ts(end)}" '
                f'value="{value}"/>\n'
            )
            record_count += 1

        # --- Day loop ---
        for day_offset in range(days):
            current_date = start_date + timedelta(days=day_offset)
            current = datetime.combine(current_date, datetime.min.time())
            is_weekend = current_date.weekday() >= 5
            season = seasonal_modifier(current_date)
            training_day = weekly_training_load(current_date)

            # Cross-metric correlations
            sleep_effect = (prev_sleep_quality - 0.5) * 2
            recovery_penalty = prev_workout_intensity * 0.3

            if day_offset > 0 and day_offset % 7 == 0:
                fitness_level += 0.002 * random.uniform(0.5, 1.5)

            # === Resting heart rate ===
            rhr = p["resting_hr_base"] - sleep_effect * 3 + recovery_penalty * 4 - fitness_level * 1.5
            rhr += random.gauss(0, 2)
            rhr = clamp(rhr, 40, 100)
            ts = current.replace(hour=7, minute=random.randint(0, 30))
            write_rec("HKQuantityTypeIdentifierRestingHeartRate",
                       "Apple Watch", "count/min", ts, ts + timedelta(hours=1), f"{rhr:.0f}")

            # === HRV ===
            hrv = p["hrv_base"] + sleep_effect * 8 - recovery_penalty * 10 + fitness_level * 3
            hrv += random.gauss(0, 6)
            hrv = clamp(hrv, 8, 150)
            for _ in range(random.randint(1, 4)):
                ts = current.replace(hour=random.choice([6, 7, 14, 22]),
                                     minute=random.randint(0, 59))
                sample = clamp(hrv + random.gauss(0, 4), 8, 150)
                write_rec("HKQuantityTypeIdentifierHeartRateVariabilitySDNN",
                           "Apple Watch", "ms", ts, ts + timedelta(seconds=60), f"{sample:.1f}")

            # === Heart rate samples (throughout the day) ===
            workout_hr_window = None
            for hour in range(6, 23):
                for _ in range(random.randint(3, 8)):
                    ts = current.replace(hour=hour, minute=random.randint(0, 59))
                    if workout_hr_window and workout_hr_window[0] <= hour <= workout_hr_window[1]:
                        hr = random.gauss(workout_hr_window[2], 10)
                    elif hour < 8 or hour > 21:
                        hr = random.gauss(rhr + 5, 4)
                    else:
                        hr = random.gauss(rhr + 12, 6)
                    write_rec("HKQuantityTypeIdentifierHeartRate",
                               "Apple Watch", "count/min",
                               ts, ts + timedelta(seconds=5), f"{clamp(hr, 40, 210):.0f}")

            # === Steps ===
            base_steps = p["steps_base"] * season
            if training_day == "rest":
                base_steps *= 0.6
            elif training_day == "hard":
                base_steps *= 1.2
            total_steps = 0
            for hour in range(7, 22):
                if random.random() < 0.75:
                    chunk = max(50, random.gauss(base_steps / 12, base_steps / 30))
                    total_steps += chunk
                    ts = current.replace(hour=hour, minute=random.randint(0, 59))
                    write_rec("HKQuantityTypeIdentifierStepCount",
                               "iPhone", "count",
                               ts, ts + timedelta(minutes=random.randint(10, 45)),
                               f"{int(chunk)}", device=IPHONE_DEVICE)

            # === Distance ===
            dist_km = total_steps * 0.00072
            write_rec("HKQuantityTypeIdentifierDistanceWalkingRunning",
                       "iPhone", "km",
                       current.replace(hour=0), current.replace(hour=22),
                       f"{dist_km:.3f}", device=IPHONE_DEVICE)

            # === Flights climbed ===
            flights = random.randint(2, 18) if random.random() < 0.8 else 0
            if flights:
                write_rec("HKQuantityTypeIdentifierFlightsClimbed",
                           "iPhone", "count",
                           current.replace(hour=8), current.replace(hour=20),
                           str(flights), device=IPHONE_DEVICE)

            # === Active + basal energy ===
            active_kcal = max(80, random.gauss(
                300 * season + (200 if training_day in ("hard", "moderate") else 0), 50))
            write_rec("HKQuantityTypeIdentifierActiveEnergyBurned",
                       "Apple Watch", "kcal",
                       current.replace(hour=0), current.replace(hour=23, minute=59),
                       f"{active_kcal:.1f}")

            basal_kcal = random.gauss(1650 + body_mass * 5, 30)
            write_rec("HKQuantityTypeIdentifierBasalEnergyBurned",
                       "Apple Watch", "kcal",
                       current.replace(hour=0), current.replace(hour=23, minute=59),
                       f"{basal_kcal:.1f}")

            # === Workout ===
            should_workout = (training_day != "rest"
                              and random.random() < p["workout_probability"] * season)
            workout_intensity = 0.0
            exercise_min = random.randint(0, 15)

            if should_workout:
                wo_name = random.choice(p["workout_types"])
                wo = WORKOUT_PROFILES[wo_name]
                intensity = {"easy": 0.7, "moderate": 1.0, "hard": 1.3}.get(training_day, 1.0)

                dur = clamp(random.gauss(wo["duration_mean"] * intensity, wo["duration_std"]),
                            10, 120)
                energy = dur * wo["kcal_per_min"] * random.uniform(0.85, 1.15)
                dist = dur * wo["km_per_min"] * random.uniform(0.9, 1.1)
                wo_hour = random.choice([6, 7, 8, 17, 18])
                wo_start = current.replace(hour=wo_hour, minute=random.randint(0, 30))
                wo_end = wo_start + timedelta(minutes=dur)

                workout_hr_window = (wo_hour, wo_hour + int(dur / 60) + 1,
                                     wo["hr_mean"] * intensity)

                avg_hr = wo["hr_mean"] * intensity
                f.write(
                    f' <Workout workoutActivityType="{wo["hk_type"]}" '
                    f'duration="{dur:.1f}" durationUnit="min" '
                    f'totalDistance="{dist:.2f}" totalDistanceUnit="km" '
                    f'totalEnergyBurned="{energy:.0f}" totalEnergyBurnedUnit="kcal" '
                    f'sourceName="Apple Watch" sourceVersion="10.4" '
                    f'device="{APPLE_WATCH_DEVICE}" '
                    f'creationDate="{fmt_ts(wo_end)}" '
                    f'startDate="{fmt_ts(wo_start)}" endDate="{fmt_ts(wo_end)}">\n'
                    f'  <WorkoutStatistics type="HKQuantityTypeIdentifierHeartRate" '
                    f'startDate="{fmt_ts(wo_start)}" endDate="{fmt_ts(wo_end)}" '
                    f'average="{avg_hr:.0f}" minimum="{avg_hr * 0.7:.0f}" '
                    f'maximum="{avg_hr * 1.15:.0f}" unit="count/min"/>\n'
                    f'  <WorkoutStatistics type="HKQuantityTypeIdentifierActiveEnergyBurned" '
                    f'startDate="{fmt_ts(wo_start)}" endDate="{fmt_ts(wo_end)}" '
                    f'sum="{energy:.0f}" unit="kcal"/>\n'
                    f' </Workout>\n'
                )
                record_count += 1
                workout_count += 1
                workout_intensity = intensity
                active_kcal += energy * 0.5
                exercise_min += dur * random.uniform(0.7, 1.0)

            # === Sleep (previous night, logged on this day) ===
            base_sleep = p["sleep_base"]
            if is_weekend:
                base_sleep += 0.5
            if prev_workout_intensity > 1.0:
                base_sleep += 0.3

            sleep_h = clamp(random.gauss(base_sleep, 0.8), 3.5, 10.5)
            bed_hour = 22 if not is_weekend else 23
            sleep_start = (current - timedelta(days=1)).replace(
                hour=bed_hour, minute=random.randint(0, 59))
            sleep_end = sleep_start + timedelta(hours=sleep_h + 0.3)

            # InBed
            write_rec("HKCategoryTypeIdentifierSleepAnalysis",
                       "Apple Watch", "",
                       sleep_start, sleep_end,
                       "HKCategoryValueSleepAnalysisInBed")

            # Sleep stages with realistic cycling
            onset = random.randint(5, 25)
            cursor = sleep_start + timedelta(minutes=onset)

            deep_pct = random.uniform(0.13, 0.22)
            rem_pct = random.uniform(0.20, 0.27)
            core_pct = 1.0 - deep_pct - rem_pct - random.uniform(0.03, 0.10)

            for stage, pct in [("AsleepDeep", deep_pct), ("AsleepCore", core_pct),
                                ("AsleepREM", rem_pct)]:
                dur_h = sleep_h * pct
                stage_end = min(cursor + timedelta(hours=dur_h), sleep_end)
                write_rec("HKCategoryTypeIdentifierSleepAnalysis",
                           "Apple Watch", "",
                           cursor, stage_end,
                           f"HKCategoryValueSleepAnalysis{stage}")
                if random.random() < 0.3:
                    awake_end = stage_end + timedelta(minutes=random.randint(1, 8))
                    write_rec("HKCategoryTypeIdentifierSleepAnalysis",
                               "Apple Watch", "",
                               stage_end, min(awake_end, sleep_end),
                               "HKCategoryValueSleepAnalysisAwake")
                    cursor = awake_end
                else:
                    cursor = stage_end

            prev_sleep_quality = clamp((sleep_h - 5) / 4 + random.gauss(0, 0.1), 0, 1)

            # === Blood oxygen (overnight, ~75% of nights) ===
            if random.random() < 0.75:
                spo2 = clamp(random.gauss(97, 1.2), 90, 100)
                write_rec("HKQuantityTypeIdentifierOxygenSaturation",
                           "Apple Watch", "%",
                           sleep_start + timedelta(hours=1),
                           sleep_end - timedelta(hours=1), f"{spo2:.0f}")

            # === Respiratory rate (overnight, ~70%) ===
            if random.random() < 0.70:
                resp = clamp(random.gauss(15.0, 1.5), 10, 25)
                write_rec("HKQuantityTypeIdentifierRespiratoryRate",
                           "Apple Watch", "count/min",
                           sleep_start, sleep_end, f"{resp:.1f}")

            # === Body mass (1-2x/week) ===
            body_mass += p["body_mass_trend"] + random.gauss(0, 0.1)
            body_mass = clamp(body_mass, 40, 200)
            if current_date.weekday() in (0, 4) and random.random() < 0.8:
                ts = current.replace(hour=7, minute=random.randint(0, 15))
                write_rec("HKQuantityTypeIdentifierBodyMass",
                           "iPhone", "kg", ts, ts + timedelta(seconds=10),
                           f"{body_mass:.1f}", device=IPHONE_DEVICE)

            # === VO2 Max (weekly) ===
            vo2max += p["vo2max_trend"] + random.gauss(0, 0.02)
            vo2max = clamp(vo2max, 15, 70)
            if current_date.weekday() == 6 and random.random() < 0.7:
                ts = current.replace(hour=18)
                f.write(
                    f' <Record type="HKQuantityTypeIdentifierVO2Max" '
                    f'sourceName="Apple Watch" sourceVersion="10.4" '
                    f'device="{APPLE_WATCH_DEVICE}" '
                    f'unit="mL/min·kg" creationDate="{fmt_ts(ts)}" '
                    f'startDate="{fmt_ts(ts)}" endDate="{fmt_ts(ts + timedelta(minutes=1))}" '
                    f'value="{vo2max:.1f}">\n'
                    f'  <MetadataEntry key="HKVO2MaxTestType" value="2"/>\n'
                    f' </Record>\n'
                )
                record_count += 1

            # === Walking metrics (few times/week) ===
            if random.random() < 0.4:
                ts = current.replace(hour=12, minute=random.randint(0, 59))
                speed = clamp(random.gauss(1.3, 0.15), 0.8, 2.0)
                write_rec("HKQuantityTypeIdentifierWalkingSpeed",
                           "iPhone", "m/s",
                           ts, ts + timedelta(minutes=10),
                           f"{speed:.2f}", device=IPHONE_DEVICE)

            # === Apple exercise time ===
            if exercise_min > 0:
                write_rec("HKQuantityTypeIdentifierAppleExerciseTime",
                           "Apple Watch", "min",
                           current.replace(hour=8), current.replace(hour=20),
                           f"{int(exercise_min)}")

            # === Stand hours ===
            stand_hours = clamp(random.gauss(10, 2), 4, 16)
            for h in random.sample(range(8, 22), min(int(stand_hours), 14)):
                write_rec("HKCategoryTypeIdentifierAppleStandHour",
                           "Apple Watch", "",
                           current.replace(hour=h),
                           current.replace(hour=h, minute=59),
                           "HKCategoryValueAppleStandHourStood")

            # === Activity summary ===
            f.write(
                f' <ActivitySummary dateComponents="{fmt_date(current_date)}" '
                f'activeEnergyBurned="{active_kcal:.0f}" '
                f'activeEnergyBurnedGoal="500" activeEnergyBurnedUnit="kcal" '
                f'appleExerciseTime="{int(exercise_min)}" appleExerciseTimeGoal="30" '
                f'appleMoveTime="{int(exercise_min * 1.3)}" appleMoveTimeGoal="30" '
                f'appleStandHours="{int(stand_hours)}" appleStandHoursGoal="12"/>\n'
            )
            record_count += 1

            prev_workout_intensity = workout_intensity

        f.write('</HealthData>\n')

    # --- Summary ---
    file_size = Path(output).stat().st_size
    size_str = (f"{file_size / 1024 / 1024:.1f} MB" if file_size > 1024 * 1024
                else f"{file_size / 1024:.0f} KB")

    print(f"\n{'=' * 50}")
    print(f"Generated {record_count:,} XML elements for {days} days")
    print(f"  Workouts:            {workout_count}")
    print(f"  Activity summaries:  {days}")
    print(f"  File size:           {size_str}")
    print(f"  Output:              {output}")
    print(f"{'=' * 50}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic Apple Health export.xml",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Personas:
  default     Average active person (RHR ~64, HRV ~42, ~8k steps/day)
  athlete     Highly trained (RHR ~52, HRV ~65, ~12k steps/day)
  sedentary   Desk worker (RHR ~74, HRV ~28, ~4.5k steps/day)
  biohacker   Optimization-focused (RHR ~58, HRV ~55, ~10k steps/day)

Examples:
  python generate_test_data.py                           # 12 months, default
  python generate_test_data.py --persona athlete         # Athletic profile
  python generate_test_data.py --days 90 --seed 42       # 90 days, reproducible
        """,
    )
    parser.add_argument("--days", type=int, default=365,
                        help="Number of days (default: 365)")
    parser.add_argument("--output", "-o", default="data/export.xml",
                        help="Output path (default: data/export.xml)")
    parser.add_argument("--persona", choices=list(PERSONAS.keys()), default="default",
                        help="Persona profile (default: default)")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for reproducibility")
    args = parser.parse_args()
    generate(args.days, args.output, args.persona, args.seed)


if __name__ == "__main__":
    main()
