"""Pytest fixtures for integration/E2E tests against a LOCAL Neo4j DBMS.

The whole point of this harness is to run real Cypher / ETL against a real
Neo4j without ever touching the developer's data or the default ``neo4j``
database. Every test session that asks for ``e2e_db`` gets its OWN isolated
*enterprise* database (``e2etest<pid>``), created on entry and dropped on exit.

How another test file requests an isolated database
---------------------------------------------------
Depend on the ``e2e_db`` fixture. It yields an :class:`E2EDatabase` whose
``.name`` is the isolated DB and whose ``.session()`` / ``.driver`` are bound to
it. To point production code (ETL, lifecycle, renderer) at the same isolated DB,
set these env vars from the fixture before invoking that code::

    monkeypatch.setenv("NEO4J_URI", e2e_db.uri)
    monkeypatch.setenv("NEO4J_USER", e2e_db.user)
    monkeypatch.setenv("NEO4J_PASSWORD", e2e_db.password)
    monkeypatch.setenv("NEO4J_DATABASE", e2e_db.name)

``NEO4J_DATABASE`` is the new knob (default unset = unchanged behavior) that
makes ETL/lifecycle/renderer target the isolated database instead of the
server-default ``neo4j``.

Connection details come from ``.env`` (LOCAL_NEO4J_URI / LOCAL_NEO4J_USER /
LOCAL_NEO4J_PASSWORD). If the local DBMS is unreachable or not Enterprise (no
multi-database support), the fixture calls ``pytest.skip`` with a clear message.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

# Resolve the repo root from this file so the .env path is stable regardless of
# the pytest invocation cwd.
REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"

# How long to wait for a freshly-created enterprise database to come online.
_ONLINE_TIMEOUT_S = 60.0
_ONLINE_POLL_S = 0.5


def load_local_neo4j_env() -> dict[str, str] | None:
    """Load LOCAL_NEO4J_* from .env via python-dotenv (explicit Path('.env')).

    Returns a dict with keys ``uri``, ``user``, ``password`` when all three are
    present, otherwise ``None`` so the caller can skip cleanly.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - dependency declared in requirements
        return None

    # Explicit path so this works no matter what cwd pytest runs from.
    load_dotenv(Path(".env"))
    # Also load from the resolved repo root in case cwd is not the repo root.
    load_dotenv(ENV_PATH)

    uri = os.environ.get("LOCAL_NEO4J_URI")
    user = os.environ.get("LOCAL_NEO4J_USER")
    password = os.environ.get("LOCAL_NEO4J_PASSWORD")
    if not uri or not user or not password:
        return None
    return {"uri": uri, "user": user, "password": password}


@dataclass
class E2EDatabase:
    """Handle to an isolated enterprise database created for one test session.

    Attributes
    ----------
    name : str
        The isolated database name (e.g. ``e2etest12345``). NEVER ``neo4j``.
    uri, user, password : str
        Connection details (the LOCAL_NEO4J_* values), exposed so tests can
        propagate them into production code via env vars.
    driver :
        A neo4j driver connected to the DBMS.
    """

    name: str
    uri: str
    user: str
    password: str
    driver: object

    def session(self, **kwargs):
        """Return a driver session BOUND to the isolated database."""
        return self.driver.session(database=self.name, **kwargs)

    def execute_query(self, query: str, **params):
        """Convenience: run a query against the isolated database, return records."""
        records, _, _ = self.driver.execute_query(query, database_=self.name, **params)
        return records

    @property
    def env(self) -> dict[str, str]:
        """The env vars a subprocess/production module needs to target this DB."""
        return {
            "NEO4J_URI": self.uri,
            "NEO4J_USER": self.user,
            "NEO4J_PASSWORD": self.password,
            "NEO4J_DATABASE": self.name,
        }


def _valid_db_name(name: str) -> str:
    """Coerce to a valid Neo4j database name: lowercase letters + digits only.

    Neo4j database names must start with a letter; we prefix with ``e2etest`` so
    that's guaranteed. We strip anything that isn't [a-z0-9] from the suffix.
    """
    cleaned = "".join(ch for ch in name.lower() if ch.isalnum())
    return cleaned


@pytest.fixture(scope="session")
def e2e_db():
    """Session-scoped isolated enterprise database.

    - Connects to the local DBMS using LOCAL_NEO4J_* from .env.
    - Skips (with a clear message) if unreachable or not Enterprise.
    - CREATE DATABASE e2etest<pid>; polls SHOW DATABASE until online.
    - Yields an :class:`E2EDatabase` bound to that database.
    - On teardown: STOP + DROP the database. Never writes to ``neo4j``.
    """
    creds = load_local_neo4j_env()
    if creds is None:
        pytest.skip(
            "Local Neo4j credentials not found. Set LOCAL_NEO4J_URI, "
            "LOCAL_NEO4J_USER and LOCAL_NEO4J_PASSWORD in .env to run E2E tests."
        )

    try:
        from neo4j import GraphDatabase
        from neo4j.exceptions import (
            ClientError,
            Neo4jError,
            ServiceUnavailable,
        )
    except ImportError:  # pragma: no cover
        pytest.skip("neo4j driver not installed — pip install -r tests/requirements-test.txt")

    driver = GraphDatabase.driver(creds["uri"], auth=(creds["user"], creds["password"]))

    # 1) Reachability check.
    try:
        driver.verify_connectivity()
    except Exception as exc:  # ServiceUnavailable, AuthError, etc.
        driver.close()
        pytest.skip(
            f"Local Neo4j at {creds['uri']} is unreachable: {exc!r}. "
            "Is Neo4j Desktop running and are the LOCAL_NEO4J_* creds correct?"
        )

    # 2) Enterprise check — multi-database (CREATE DATABASE) requires Enterprise.
    try:
        records, _, _ = driver.execute_query(
            "CALL dbms.components() YIELD edition RETURN edition LIMIT 1",
            database_="system",
        )
        edition = records[0]["edition"] if records else "unknown"
    except Exception as exc:
        driver.close()
        pytest.skip(f"Could not read DBMS edition: {exc!r}")

    if str(edition).lower() != "enterprise":
        driver.close()
        pytest.skip(
            f"Local Neo4j edition is '{edition}', not 'enterprise'. "
            "Isolated test databases (CREATE DATABASE) require Neo4j Enterprise."
        )

    db_name = _valid_db_name(f"e2etest{os.getpid()}")
    assert db_name != "neo4j", "refusing to use the default 'neo4j' database"
    assert db_name and db_name[0].isalpha(), f"invalid db name: {db_name!r}"

    # 3) Create the isolated database (drop any stale leftover first).
    try:
        driver.execute_query(f"CREATE OR REPLACE DATABASE {db_name} WAIT", database_="system")
    except Neo4jError as exc:
        driver.close()
        pytest.skip(f"Could not CREATE DATABASE {db_name}: {exc!r}")

    # 4) Poll SHOW DATABASE until currentStatus == 'online'.
    deadline = time.monotonic() + _ONLINE_TIMEOUT_S
    online = False
    last_status = "unknown"
    while time.monotonic() < deadline:
        try:
            recs, _, _ = driver.execute_query(
                "SHOW DATABASE $name YIELD name, currentStatus RETURN currentStatus",
                name=db_name,
                database_="system",
            )
        except (ServiceUnavailable, ClientError) as exc:  # transient during create
            last_status = f"poll-error: {exc!r}"
            time.sleep(_ONLINE_POLL_S)
            continue
        if recs:
            last_status = recs[0]["currentStatus"]
            if last_status == "online":
                online = True
                break
        time.sleep(_ONLINE_POLL_S)

    if not online:
        # Best-effort cleanup before skipping.
        try:
            driver.execute_query(f"DROP DATABASE {db_name} IF EXISTS", database_="system")
        except Exception:
            pass
        driver.close()
        pytest.skip(
            f"Database {db_name} did not come online within {_ONLINE_TIMEOUT_S}s "
            f"(last status: {last_status})."
        )

    handle = E2EDatabase(
        name=db_name,
        uri=creds["uri"],
        user=creds["user"],
        password=creds["password"],
        driver=driver,
    )

    try:
        yield handle
    finally:
        # Teardown: STOP then DROP. Never touch the default 'neo4j' database.
        try:
            driver.execute_query(f"STOP DATABASE {db_name} IF EXISTS WAIT", database_="system")
        except Exception:
            pass
        try:
            driver.execute_query(f"DROP DATABASE {db_name} IF EXISTS WAIT", database_="system")
        except Exception:
            pass
        driver.close()


@pytest.fixture(autouse=True)
def _clean_isolated_db(request):
    """Wipe the isolated database before each test that uses ``e2e_db``.

    ``e2e_db`` is session-scoped (one throwaway database per run, shared by every
    test file), so without this, nodes created by one test leak into another and
    make count-based assertions order-dependent. Tests that don't request
    ``e2e_db`` are untouched (no DB hit).
    """
    if "e2e_db" in request.fixturenames:
        request.getfixturevalue("e2e_db").execute_query("MATCH (n) DETACH DELETE n")
    yield
