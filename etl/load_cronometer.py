"""load_cronometer.py — ingest a Cronometer CSV export into the health graph.

Cronometer has **no public API for individuals** (only a partners-only B2B API),
and its Terms prohibit automated extraction *and specifically forbid feeding
Content to AI/ML/LLM systems* — which an agent pipeline like this would trip.
So the sanctioned, robust path is the user's own **manual CSV export**:

    cronometer.com  ->  Profile tab  ->  gear icon (Account Settings)
                    ->  Export Data  ->  pick a date range
                    ->  one CSV per type: Daily Nutrition, Servings,
                        Biometrics, Exercises, Notes  (free; web only)

This connector parses two of those files onto the existing (:Day) timeline as
generic :Observation nodes (see ``observation_model.py``):

  * **Daily Nutrition** — one row per day, wide: ``Date, Completed,
    Energy (kcal), Protein (g), Carbs (g), Fat (g), …`` then a long
    micronutrient tail. Each nutrient cell becomes one ``category="nutrition"``
    Observation (type = nutrient name, unit = the parenthetical).
  * **Biometrics** — already tidy: ``Day, Time, Metric, Unit, Amount``. Each row
    is one ``category="biometric"`` Observation almost 1:1.

Robustness notes baked in (from real-world exports):
  * Parse by **header name**, never column index — Cronometer appends nutrient
    columns over time (Allulose, Added Sugars, Sugar Alcohol are recent).
  * Micrograms use the micro sign ``µg`` (U+00B5) — files are read as UTF-8.
  * Energy can be CSV-quoted with a thousands separator (``"2,154.5"``).
  * Blank nutrient cells are skipped (not written as 0).

Usage
-----
    # synthetic sample shipped in the repo (safe, no personal data)
    python etl/load_cronometer.py \
        --daily-nutrition docs/connectors/cronometer/sample/daily-nutrition.csv \
        --biometrics      docs/connectors/cronometer/sample/biometrics.csv \
        --dry-run

    # your real export (keep it under data/, which is git-ignored)
    python etl/load_cronometer.py --daily-nutrition data/cronometer/nutrition.csv

Run it from the repo root. Requires NEO4J_URI / NEO4J_PASSWORD in .env.
"""

from __future__ import annotations

import argparse
import csv
import logging
import re
import sys
from collections import Counter
from datetime import date as _date
from datetime import datetime
from pathlib import Path

from observation_model import Observation, get_driver, load_observations

log = logging.getLogger(__name__)

# Daily-Nutrition columns that are not nutrients (case-insensitive).
_NON_NUTRIENT_COLS = {"date", "day", "completed"}

# Accept the common single-cell date renderings Cronometer emits per account locale.
_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%d.%m.%Y", "%Y/%m/%d")

# "Energy (kcal)" -> ("Energy", "kcal"); "Net Carbs (g)" -> ("Net Carbs", "g").
_HEADER_RE = re.compile(r"^\s*(.*?)\s*\(([^()]*)\)\s*$")


# ---------------------------------------------------------------------------
# Cell-level parsing
# ---------------------------------------------------------------------------


def parse_header(col: str) -> tuple[str, str]:
    """Split a ``Name (Unit)`` column header into ``(name, unit)``.

    Columns with no parenthetical (rare) return ``(name, "")``.
    """
    m = _HEADER_RE.match(col or "")
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return (col or "").strip(), ""


def parse_number(raw: str | None) -> float | None:
    """Parse a numeric cell, returning ``None`` for blanks/non-numeric.

    Locale-robust: Cronometer renders numbers per the account's locale, so a cell
    can be US ``"2,154.5"`` *or* European ``"2.154,5"`` / ``"78,4"``. Naively
    stripping commas would turn ``78,4`` kg into ``784`` (a silent 10× error), so:

    * both ``,`` and ``.`` present -> the **last** separator is the decimal point,
      the other is thousands grouping (handles ``"2,154.5"`` and ``"2.154,5"``).
    * only ``,`` present -> treat as a decimal comma when it's a single comma with
      1-2 trailing digits (``"78,4"``, ``"18,25"``); otherwise as thousands
      grouping (``"2,154"``, ``"1,234,567"``).
    * only ``.`` / no separator -> already a plain float.
    """
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return None

    has_comma = "," in s
    has_dot = "." in s
    if has_comma and has_dot:
        if s.rfind(",") > s.rfind("."):  # comma is the decimal (European)
            s = s.replace(".", "").replace(",", ".")
        else:  # dot is the decimal (US)
            s = s.replace(",", "")
    elif has_comma:
        parts = s.split(",")
        if len(parts) == 2 and 1 <= len(parts[1]) <= 2:
            s = s.replace(",", ".")  # decimal comma, e.g. "78,4"
        else:
            s = s.replace(",", "")  # thousands grouping, e.g. "2,154"

    try:
        return float(s)
    except ValueError:
        return None


def parse_date(raw: str | None) -> _date:
    """Parse a Cronometer date cell to a ``datetime.date``.

    Accepts a bare ISO date, an ISO datetime prefix, and a few locale formats.
    Raises ``ValueError`` if nothing matches (caller decides to skip/abort).
    """
    s = (raw or "").strip()
    if not s:
        raise ValueError("empty date cell")
    # ISO datetime like 2026-06-01T08:05:00 -> take the date prefix.
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        s = s[:10]
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unrecognized date: {raw!r}")


def _find_col(fieldnames, candidates) -> str | None:
    """Return the actual header matching any candidate name (case-insensitive)."""
    lower = {(c or "").strip().lower(): c for c in (fieldnames or [])}
    for cand in candidates:
        if cand.lower() in lower:
            return lower[cand.lower()]
    return None


# ---------------------------------------------------------------------------
# File parsers -> Observation lists
# ---------------------------------------------------------------------------


def parse_daily_nutrition(path, source: str = "cronometer") -> list[Observation]:
    """Parse a Daily Nutrition CSV (one row/day, wide) into Observations.

    Every nutrient column with a value becomes one nutrition Observation; the
    ``Date`` and ``Completed`` columns are not emitted as observations.
    """
    path = Path(path)
    obs: list[Observation] = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        date_col = _find_col(reader.fieldnames, ("Date", "Day"))
        if not date_col:
            raise ValueError(f"{path}: no Date/Day column found in header")
        for lineno, row in enumerate(reader, start=2):
            try:
                d = parse_date(row.get(date_col))
            except ValueError as exc:
                log.warning("%s:%d skipping row, %s", path.name, lineno, exc)
                continue
            iso, wd = d.isoformat(), d.strftime("%A")
            for col, raw in row.items():
                if col is None:
                    continue
                if col.strip().lower() in _NON_NUTRIENT_COLS or col == date_col:
                    continue
                value = parse_number(raw)
                if value is None:
                    continue  # blank/non-numeric nutrient cell — skip, don't zero
                name, unit = parse_header(col)
                obs.append(
                    Observation(
                        source=source,
                        category="nutrition",
                        date=iso,
                        type=name,
                        unit=unit,
                        value=value,
                        day_of_week=wd,
                    )
                )
    return obs


def parse_biometrics(path, source: str = "cronometer") -> list[Observation]:
    """Parse a Biometrics CSV (tidy ``Day,Time,Metric,Unit,Amount``).

    Each row is one biometric Observation. A (date, metric) that legitimately
    repeats in a day (e.g. two weigh-ins) gets a running ``seq`` so both survive
    and re-imports of the same file stay idempotent.
    """
    path = Path(path)
    records: list[dict] = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        c_day = _find_col(reader.fieldnames, ("Day", "Date"))
        c_time = _find_col(reader.fieldnames, ("Time",))
        c_metric = _find_col(reader.fieldnames, ("Metric",))
        c_unit = _find_col(reader.fieldnames, ("Unit",))
        c_amount = _find_col(reader.fieldnames, ("Amount", "Value"))
        if not (c_day and c_metric and c_amount):
            raise ValueError(f"{path}: expected Day/Metric/Amount columns in header")
        for lineno, row in enumerate(reader, start=2):
            try:
                d = parse_date(row.get(c_day))
            except ValueError as exc:
                log.warning("%s:%d skipping row, %s", path.name, lineno, exc)
                continue
            metric = (row.get(c_metric) or "").strip()
            value = parse_number(row.get(c_amount))
            if not metric or value is None:
                continue
            records.append(
                {
                    "date": d.isoformat(),
                    "day_of_week": d.strftime("%A"),
                    "metric": metric,
                    "unit": (row.get(c_unit) or "").strip() if c_unit else "",
                    "value": value,
                    "time": (row.get(c_time) or "").strip() if c_time else "",
                }
            )

    # Assign seq deterministically by (date, metric, time) so a re-export with
    # reordered rows produces the SAME keys -> idempotent re-import even for a
    # metric logged several times in one day (e.g. two weigh-ins).
    records.sort(key=lambda r: (r["date"], r["metric"], r["time"]))
    seq: Counter = Counter()
    obs: list[Observation] = []
    for r in records:
        group = (r["date"], r["metric"])
        n = seq[group]
        seq[group] += 1
        obs.append(
            Observation(
                source=source,
                category="biometric",
                date=r["date"],
                type=r["metric"],
                unit=r["unit"],
                value=r["value"],
                time=r["time"] or None,
                seq=n,
                day_of_week=r["day_of_week"],
            )
        )
    return obs


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _summarize(observations: list[Observation]) -> str:
    by_cat = Counter(o.category for o in observations)
    days = sorted({o.date for o in observations})
    span = f"{days[0]}..{days[-1]}" if days else "—"
    cats = ", ".join(f"{k}={v}" for k, v in sorted(by_cat.items()))
    return f"{len(observations)} observations ({cats}) across {len(days)} days [{span}]"


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(
        description="Ingest a Cronometer CSV export into the Neo4j health graph."
    )
    parser.add_argument("--daily-nutrition", help="Path to a Daily Nutrition CSV")
    parser.add_argument("--biometrics", help="Path to a Biometrics CSV")
    parser.add_argument("--source", default="cronometer", help="Source node name")
    parser.add_argument(
        "--no-create-days",
        action="store_true",
        help="Only link to Days that already exist (don't create missing Days)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse + summarize only; do not write to Neo4j",
    )
    args = parser.parse_args(argv)

    if not args.daily_nutrition and not args.biometrics:
        parser.error("provide --daily-nutrition and/or --biometrics")

    observations: list[Observation] = []
    if args.daily_nutrition:
        n = parse_daily_nutrition(args.daily_nutrition, args.source)
        log.info("Daily Nutrition: %s", _summarize(n))
        observations += n
    if args.biometrics:
        b = parse_biometrics(args.biometrics, args.source)
        log.info("Biometrics:      %s", _summarize(b))
        observations += b

    log.info("TOTAL: %s", _summarize(observations))

    if args.dry_run:
        for o in observations[:8]:
            log.info("  e.g. %s %s = %s %s [%s]", o.date, o.type, o.value, o.unit, o.category)
        log.info("dry-run: not writing to Neo4j")
        return 0

    # Load .env then connect (only now — dry-run needs no DB/secrets).
    try:
        from dotenv import load_dotenv

        load_dotenv(Path(".env"))
    except ImportError:
        pass

    driver = get_driver()
    try:
        written = load_observations(driver, observations, create_days=not args.no_create_days)
        log.info("wrote %d observations to the graph", written)
    finally:
        driver.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
