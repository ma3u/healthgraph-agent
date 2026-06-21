"""Tests for the Aura "automatic shutdown and restart" lifecycle.

``scripts/aura_lifecycle.py`` keeps the Aura instance paused most of the time and
only wakes it for the morning sync, auto-pausing again after a true 30-minute
idle window. The idle signal is a sliding TTL stored *in the graph itself*:
``(:System {key:'aura'}).lastActivityAt``.

These tests verify that decision logic WITHOUT calling real Aura:
  - The Aura REST layer (get_token / instance_status / api) is monkeypatched to
    simulate 'running'/'paused' and to CAPTURE pause / resume calls.
  - The activity signal uses the ISOLATED database (NEO4J_DATABASE set from the
    e2e_db fixture), so stamp_activity()/idle_minutes() read/write real Cypher
    against a throwaway db — never the user's real 'neo4j'.

Scenarios:
  - Fresh stamp => idle ~0 => pause-if-idle(30) must NOT pause (sliding TTL keeps
    it alive).
  - lastActivityAt set far in the past => idle is large => pause-if-idle(30)
    DOES pause.
  - wake() issues a resume when the instance is paused, and stamps activity.
"""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

pytestmark = pytest.mark.e2e


class FakeAura:
    """Stand-in for the Aura platform REST API.

    Records every pause/resume POST and lets the test drive the reported status.
    """

    def __init__(self, status: str = "running"):
        self.status = status
        self.calls: list[tuple[str, str]] = []  # (method, suffix)

    # Patched in for aura_lifecycle.get_token
    def get_token(self) -> str:
        return "fake-token"

    # Patched in for aura_lifecycle.instance_status
    def instance_status(self, _token: str) -> str:
        return self.status

    # Patched in for aura_lifecycle.api
    def api(self, method: str, suffix: str, _token: str) -> dict:
        self.calls.append((method, suffix))
        if suffix == "/pause":
            self.status = "paused"
        elif suffix == "/resume":
            self.status = "running"
        return {"data": {"status": self.status}}

    # Convenience assertions
    @property
    def paused(self) -> bool:
        return ("POST", "/pause") in self.calls

    @property
    def resumed(self) -> bool:
        return ("POST", "/resume") in self.calls


@pytest.fixture
def lifecycle(e2e_db, monkeypatch):
    """Import aura_lifecycle with env pointed at the isolated db and the Aura
    REST layer stubbed out. Yields (module, fake_aura, args_namespace_factory)."""
    # Route the activity-signal driver at the isolated database.
    for key, value in e2e_db.env.items():
        monkeypatch.setenv(key, value)

    import aura_lifecycle as mod

    mod = importlib.reload(mod)

    fake = FakeAura(status="running")
    monkeypatch.setattr(mod, "get_token", fake.get_token)
    monkeypatch.setattr(mod, "instance_status", fake.instance_status)
    monkeypatch.setattr(mod, "api", fake.api)

    # Clean slate: remove any prior activity stamp in the isolated db so
    # idle_minutes()/no-stamp paths are deterministic per test.
    e2e_db.execute_query("MATCH (s:System {key: 'aura'}) DETACH DELETE s")

    def make_args(**kw):
        return types.SimpleNamespace(**kw)

    return mod, fake, make_args


def test_stamp_then_idle_is_near_zero(lifecycle):
    """After stamp_activity(), idle_minutes() is ~0 (sliding TTL just refreshed)."""
    mod, _fake, _ = lifecycle
    mod.stamp_activity()
    idle = mod.idle_minutes()
    assert idle is not None, "idle_minutes() should not be None right after a stamp"
    assert idle < 1.0, f"expected ~0 idle right after stamp, got {idle:.3f} min"


def test_pause_if_idle_does_not_pause_when_recently_active(lifecycle, monkeypatch):
    """Fresh activity => idle < threshold => running instance is NOT paused."""
    mod, fake, make_args = lifecycle

    # Avoid the in-flight check probing the system db over the network; the
    # decision under test is the idle-vs-threshold branch.
    monkeypatch.setattr(mod, "has_inflight_transactions", lambda: False)

    mod.stamp_activity()  # idle ~ 0
    rc = mod.cmd_pause_if_idle(make_args(minutes=30.0, dry_run=False))

    assert rc == 0
    assert not fake.paused, "instance was paused despite being recently active"
    assert fake.status == "running"


def test_pause_if_idle_pauses_when_idle_exceeds_threshold(lifecycle, monkeypatch, e2e_db):
    """Old lastActivityAt => idle >> threshold => running instance IS paused."""
    mod, fake, make_args = lifecycle
    monkeypatch.setattr(mod, "has_inflight_transactions", lambda: False)

    # Simulate a stamp from 2 hours ago directly in the isolated db.
    e2e_db.execute_query(
        "MERGE (s:System {key: 'aura'}) " "SET s.lastActivityAt = datetime() - duration({hours: 2})"
    )

    idle = mod.idle_minutes()
    assert idle is not None and idle > 60, f"expected idle > 60 min for a 2h-old stamp, got {idle}"

    rc = mod.cmd_pause_if_idle(make_args(minutes=30.0, dry_run=False))

    assert rc == 0
    assert fake.paused, "instance should have been paused after exceeding idle threshold"
    assert fake.status == "paused"


def test_pause_if_idle_dry_run_does_not_pause(lifecycle, monkeypatch, e2e_db):
    """--dry-run reports the decision but never issues the pause."""
    mod, fake, make_args = lifecycle
    monkeypatch.setattr(mod, "has_inflight_transactions", lambda: False)

    e2e_db.execute_query(
        "MERGE (s:System {key: 'aura'}) " "SET s.lastActivityAt = datetime() - duration({hours: 2})"
    )

    rc = mod.cmd_pause_if_idle(make_args(minutes=30.0, dry_run=True))
    assert rc == 0
    assert not fake.paused, "dry-run must not actually pause"


def test_pause_if_idle_noop_when_already_paused(lifecycle):
    """If the instance is already paused, pause-if-idle does nothing."""
    mod, fake, make_args = lifecycle
    fake.status = "paused"
    rc = mod.cmd_pause_if_idle(make_args(minutes=30.0, dry_run=False))
    assert rc == 0
    assert ("POST", "/pause") not in fake.calls, "should not pause an already-paused instance"


def test_wake_resumes_when_paused(lifecycle):
    """wake() issues a /resume POST when the instance is paused."""
    mod, fake, make_args = lifecycle
    fake.status = "paused"

    rc = mod.cmd_wake(make_args(wait=False, timeout=300))

    assert rc == 0
    assert fake.resumed, "wake() should issue a /resume when the instance is paused"
    assert fake.status == "running", "FakeAura should report running after resume"


def test_wake_with_wait_resumes_then_stamps_activity(lifecycle):
    """With --wait, wake() polls until running, then stamps the sliding TTL.

    cmd_wake only stamps once it OBSERVES status == 'running'. After the resume
    POST, FakeAura reports 'running', so the --wait poll confirms it and the
    activity stamp fires (idle clock starts fresh at ~0).
    """
    mod, fake, make_args = lifecycle
    fake.status = "paused"

    rc = mod.cmd_wake(make_args(wait=True, timeout=300))

    assert rc == 0
    assert fake.resumed, "wake() should issue a /resume when the instance is paused"
    assert fake.status == "running"

    idle = mod.idle_minutes()
    assert (
        idle is not None and idle < 1.0
    ), f"wake(--wait) should stamp activity once running; idle was {idle}"


def test_wake_does_not_resume_when_already_running(lifecycle):
    """If already running, wake() must NOT issue a redundant resume but DOES
    stamp activity (it observes 'running' immediately)."""
    mod, fake, make_args = lifecycle
    fake.status = "running"

    rc = mod.cmd_wake(make_args(wait=False, timeout=300))

    assert rc == 0
    assert (
        "POST",
        "/resume",
    ) not in fake.calls, "wake() should not resume an already-running instance"
    # It still stamps activity to extend the sliding window.
    idle = mod.idle_minutes()
    assert idle is not None and idle < 1.0
