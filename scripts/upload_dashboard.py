"""Upload whoop_dashboard.json into Aura as a _Neodash_Dashboard node.

Matches the schema used by NeoDash & Aura built-in Dashboards:
  (:_Neodash_Dashboard {uuid, title, version, user, content, date})

After running, the dashboard appears in:
  Aura Console -> Dashboards -> Load -> "Saved in this database"
"""
import json
import os
import uuid
import sys
from pathlib import Path
from datetime import datetime, timezone

from neo4j import GraphDatabase

DASHBOARD_PATH = Path("/Users/mbuchhorn/projects/healthgraph-agent/neodash/whoop_dashboard.json")

# Read .env directly (no python-dotenv needed)
env = {}
for line in Path("/Users/mbuchhorn/projects/healthgraph-agent/.env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip()

URI = env["NEO4J_URI"]
USER = env["NEO4J_USER"]
PW = env["NEO4J_PASSWORD"]

content = DASHBOARD_PATH.read_text()
dash = json.loads(content)
title = dash["title"]
version = dash["version"]

# Deterministic UUID per title so repeated runs MERGE not duplicate
DASHBOARD_UUID = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"healthgraph.{title}"))
NOW = datetime.now(timezone.utc).isoformat()

driver = GraphDatabase.driver(URI, auth=(USER, PW))
with driver.session() as sess:
    res = sess.run(
        """
        MERGE (n:_Neodash_Dashboard {uuid: $uuid})
        SET n.title = $title,
            n.version = $version,
            n.user = $user,
            n.content = $content,
            n.date = datetime($date)
        RETURN n.uuid AS uuid, n.title AS title
        """,
        uuid=DASHBOARD_UUID,
        title=title,
        version=version,
        user=env.get("AURA_INSTANCENAME", "cli-upload"),
        content=content,
        date=NOW,
    ).single()
    print(f"Upserted dashboard: uuid={res['uuid']} title={res['title']!r}")

    # List all dashboards as Aura's picker would
    print("\nDashboards in database:")
    for row in sess.run(
        "MATCH (n:_Neodash_Dashboard) RETURN n.uuid AS uuid, n.title AS title, "
        "toString(n.date) AS date, n.user AS author, n.version AS version "
        "ORDER BY toLower(n.title)"
    ):
        print(f"  - [{row['version']}] {row['title']} (uuid={row['uuid']}, date={row['date']})")
driver.close()
