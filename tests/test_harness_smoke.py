"""Smoke test for the E2E harness.

Proves the ``e2e_db`` fixture gives us a working, ISOLATED enterprise database:
we can MERGE a node, read it back, and the database is genuinely separate from
the server-default ``neo4j`` database (so tests never pollute real data).
"""

from __future__ import annotations


def test_merge_and_read_back(e2e_db):
    """MERGE a node into the isolated DB and read it back."""
    e2e_db.execute_query(
        "MERGE (n:HarnessProbe {key: $k}) SET n.value = $v",
        k="smoke",
        v=42,
    )

    records = e2e_db.execute_query(
        "MATCH (n:HarnessProbe {key: $k}) RETURN n.value AS value",
        k="smoke",
    )
    assert len(records) == 1, "expected exactly one HarnessProbe node"
    assert records[0]["value"] == 42


def test_session_helper_is_bound_to_isolated_db(e2e_db):
    """The session() helper writes/reads against the isolated database."""
    with e2e_db.session() as sess:
        sess.run("MERGE (n:HarnessProbe {key: 'via-session'}) SET n.ok = true")
        rec = sess.run("MATCH (n:HarnessProbe {key: 'via-session'}) RETURN n.ok AS ok").single()
    assert rec is not None
    assert rec["ok"] is True


def test_db_name_is_isolated_not_default(e2e_db):
    """The fixture database is named e2etest* and is NOT the default 'neo4j'."""
    assert e2e_db.name != "neo4j"
    assert e2e_db.name.startswith("e2etest")
    # All-lowercase alphanumeric, valid Neo4j db name starting with a letter.
    assert e2e_db.name.isalnum()
    assert e2e_db.name.islower()
    assert e2e_db.name[0].isalpha()


def test_isolation_default_neo4j_db_has_no_probe(e2e_db):
    """A node MERGEd into the isolated DB must NOT appear in default 'neo4j'.

    This confirms the harness never leaks writes into the real database. We
    only READ from 'neo4j' here (a count), we never write to it.
    """
    # Write a uniquely-keyed probe into the isolated database.
    marker = "isolation-marker"
    e2e_db.execute_query("MERGE (n:HarnessProbe {key: $k})", k=marker)

    # Read-only check against the default 'neo4j' database: the marker is absent.
    records, _, _ = e2e_db.driver.execute_query(
        "MATCH (n:HarnessProbe {key: $k}) RETURN count(n) AS c",
        k=marker,
        database_="neo4j",
    )
    assert records[0]["c"] == 0, "isolation breach: probe leaked into the default 'neo4j' database"

    # And it IS present in the isolated database.
    iso = e2e_db.execute_query("MATCH (n:HarnessProbe {key: $k}) RETURN count(n) AS c", k=marker)
    assert iso[0]["c"] == 1
