"""observation_model.py — the reusable "silo → graph" spine for the private EHR.

Every external data silo (Cronometer nutrition, lab panels, gym machines, …) is
reduced to a flat list of :class:`Observation` records and written with the SAME
shape the rest of the graph already uses::

    (:Source {name})-[:RECORDED]->(:Observation {key,date,type,value,unit,…})
    (:Observation)-[:ON_DAY]->(:Day {date})

``ON_DAY`` is the exact temporal edge Workouts and SleepSessions use
(``etl/load_to_neo4j.py``), so a new silo lands on the existing timeline with no
schema migration — and ``(:Day)`` stays the single spine every source hangs off.

Design notes
------------
* **Idempotent.** Everything is ``MERGE``. Re-importing the same export updates
  observations in place; it never duplicates them. The idempotency handle is
  ``Observation.key`` (``source|category|date|type[|seq]``).
* **Long/tidy, FHIR-ish.** One Observation = one measurement (a code/``type``,
  a ``value``, a ``unit``, an ``effective`` date). This is why a single model
  fits both Cronometer's wide Daily-Nutrition CSV (melted to one row per
  nutrient) and its already-tidy Biometrics CSV.
* **Day creation is opt-out.** ``create_days=True`` MERGEs the Day (nutrition is
  dense daily data that legitimately anchors the timeline). ``create_days=False``
  only links to Days that already exist (mirrors the Document-Intelligence
  ``link_clinical_to_days.cypher``: never strand a Day for a stray dated record).

This module is deliberately self-contained (only ``neo4j`` + stdlib) so a
connector can ``from observation_model import Observation, load_observations,
get_driver`` without dragging in the Apple-Health parse/transform stack.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass

from neo4j import GraphDatabase

log = logging.getLogger(__name__)

BATCH_SIZE = 500

# Optional target database. Default None => the driver/server default (unchanged
# behaviour). Tests set NEO4J_DATABASE to an isolated enterprise db, then reload
# this module so the value is picked up (same pattern as etl/load_to_neo4j.py).
DATABASE = os.environ.get("NEO4J_DATABASE")


# ---------------------------------------------------------------------------
# The record
# ---------------------------------------------------------------------------


@dataclass
class Observation:
    """One dated measurement from one source.

    Parameters
    ----------
    source : str          e.g. ``"cronometer"`` — becomes ``(:Source {name})``.
    category : str        coarse kind, e.g. ``"nutrition"`` / ``"biometric"``.
    date : str            ISO ``YYYY-MM-DD`` (the day this measurement applies to).
    type : str            human metric name, e.g. ``"Energy"``, ``"Protein"``,
                          ``"Weight"`` — also indexed for querying.
    value : float         the numeric value.
    unit : str            unit string, e.g. ``"kcal"``, ``"g"``, ``"mg"``, ``"µg"``.
    time : str | None     optional clock time of the reading (biometrics).
    seq : int | None      disambiguator when a (date, type) legitimately repeats
                          (e.g. two weigh-ins in one day). ``None`` for once-a-day
                          values like daily nutrition totals.
    day_of_week : str | None
                          weekday name, written ON CREATE of a new Day so
                          Days created here match those the Apple-Health ETL makes.
    """

    source: str
    category: str
    date: str
    type: str
    value: float
    unit: str = ""
    time: str | None = None
    seq: int | None = None
    day_of_week: str | None = None

    @property
    def key(self) -> str:
        """Stable idempotency key: ``source|category|date|type[|seq]``."""
        parts = [self.source, self.category, self.date, self.type]
        if self.seq is not None:
            parts.append(str(self.seq))
        return "|".join(parts)

    def as_row(self) -> dict:
        """Flatten to a plain dict for an UNWIND batch parameter."""
        return {
            "key": self.key,
            "source": self.source,
            "category": self.category,
            "date": self.date,
            "type": self.type,
            "unit": self.unit or "",
            "value": float(self.value),
            "time": self.time or None,
            "day_of_week": self.day_of_week or None,
        }


# ---------------------------------------------------------------------------
# Connection (self-contained; mirrors etl/load_to_neo4j.get_driver)
# ---------------------------------------------------------------------------


def get_driver():
    """Connect to Neo4j — auto-detects Desktop (bolt://) vs Aura (neo4j+s://).

    Reads NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD from the environment (load your
    ``.env`` before calling, e.g. via python-dotenv in the connector CLI).
    """
    uri = os.environ.get("NEO4J_URI")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD")

    if not uri or not password:
        print("Error: set NEO4J_URI and NEO4J_PASSWORD (e.g. in .env)", file=sys.stderr)
        print("  Neo4j Desktop:  NEO4J_URI=bolt://localhost:7687", file=sys.stderr)
        print("  Neo4j Aura:     NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io", file=sys.stderr)
        sys.exit(1)

    return GraphDatabase.driver(uri, auth=(user, password))


def _session(driver, **kwargs):
    """Open a session, scoped to NEO4J_DATABASE when set (else server default)."""
    if DATABASE:
        return driver.session(database=DATABASE, **kwargs)
    return driver.session(**kwargs)


# ---------------------------------------------------------------------------
# Schema + load queries
# ---------------------------------------------------------------------------

SCHEMA_STATEMENTS = [
    "CREATE CONSTRAINT source_name IF NOT EXISTS FOR (s:Source) REQUIRE s.name IS UNIQUE",
    "CREATE CONSTRAINT observation_key IF NOT EXISTS FOR (o:Observation) REQUIRE o.key IS UNIQUE",
    # Day uniqueness is normally created by the Apple-Health ETL; declare it here
    # too so a silo can be the FIRST thing ever loaded into a fresh database.
    "CREATE CONSTRAINT day_date IF NOT EXISTS FOR (d:Day) REQUIRE d.date IS UNIQUE",
    "CREATE INDEX observation_type IF NOT EXISTS FOR (o:Observation) ON (o.type)",
    "CREATE INDEX observation_category IF NOT EXISTS FOR (o:Observation) ON (o.category)",
    "CREATE INDEX observation_source IF NOT EXISTS FOR (o:Observation) ON (o.source)",
]

# Shared write of the Source -> Observation half (identical in both variants).
_MERGE_OBSERVATION = """
UNWIND $batch AS row
MERGE (src:Source {name: row.source})
MERGE (o:Observation {key: row.key})
SET o.date = date(row.date),
    o.type = row.type,
    o.unit = row.unit,
    o.value = row.value,
    o.category = row.category,
    o.source = row.source,
    o.time = row.time
MERGE (src)-[:RECORDED]->(o)
"""

# Variant A: create the Day if missing (nutrition anchors its own days).
LOAD_CREATE_DAYS = (
    _MERGE_OBSERVATION
    + """
MERGE (d:Day {date: date(row.date)})
  ON CREATE SET d.day_of_week = row.day_of_week
MERGE (o)-[:ON_DAY]->(d)
"""
)

# Variant B: link only to Days that already exist (never strand a Day). An
# observation whose day is absent is still created+sourced, just not ON_DAY-linked.
LOAD_LINK_ONLY = (
    _MERGE_OBSERVATION
    + """
WITH o, row
MATCH (d:Day {date: date(row.date)})
MERGE (o)-[:ON_DAY]->(d)
"""
)


def ensure_schema(driver) -> None:
    """Create the Source/Observation/Day constraints + indexes (idempotent)."""
    with _session(driver) as session:
        for stmt in SCHEMA_STATEMENTS:
            try:
                session.run(stmt)
            except Exception as exc:  # already-exists / racing creators are fine
                if "already exists" not in str(exc).lower():
                    log.warning("schema statement failed: %s", exc)


def load_observations(driver, observations, *, create_days: bool = True) -> int:
    """Write a list of :class:`Observation` to the graph. Returns rows written.

    ``create_days=True`` MERGEs the (:Day) for each observation; ``False`` only
    links to pre-existing Days.
    """
    rows = [o.as_row() for o in observations]
    if not rows:
        return 0

    ensure_schema(driver)
    query = LOAD_CREATE_DAYS if create_days else LOAD_LINK_ONLY
    with _session(driver) as session:
        for i in range(0, len(rows), BATCH_SIZE):
            session.run(query, {"batch": rows[i : i + BATCH_SIZE]})
    return len(rows)
