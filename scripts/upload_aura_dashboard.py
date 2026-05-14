"""Push neodash/whoop_dashboard.json (NeoDash 2.5 format) into Aura's built-in Dashboards
via the console.neo4j.io shared-storage API.

Requires:
  - AURA_SESSION_TOKEN  (env var or /tmp/aura_session_token.txt) — Bearer JWT from browser
  - PROJECT_ID          (Aura project UUID)
  - INSTANCE_ID         (8-char Aura instance ID, e.g. 7d4ba607)

Schema source: reverse-engineered from console.neo4j.io JS bundle (widget.js).
Sample format: github.com/neo4j-product-examples/sample-applications/.../fraud-detection.dashboard.json
"""
import json
import os
import sys
import time
import uuid
from pathlib import Path
import urllib.request
import urllib.error

API_BASE = "https://console.neo4j.io/api/shared-storage/v1/dashboards/dashboards"
PROJECT_ID = os.environ.get("PROJECT_ID", "326809f3-c351-4eb7-8770-fcf5d0b6adc1")
INSTANCE_ID = os.environ.get("INSTANCE_ID", "7d4ba607")

token_path = Path("/tmp/aura_session_token.txt")
TOKEN = os.environ.get("AURA_SESSION_TOKEN") or (token_path.read_text().strip() if token_path.exists() else None)
if not TOKEN:
    sys.exit("Set AURA_SESSION_TOKEN env or write the JWT to /tmp/aura_session_token.txt")

NEODASH = Path("/Users/mbuchhorn/projects/healthgraph-agent/neodash/whoop_dashboard.json")

# ----- HTTP helper -----
def http(method, url, body=None):
    data = None
    if body is not None:
        data = json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        method=method,
        data=data,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Project-Id": PROJECT_ID,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            txt = resp.read().decode()
            return resp.status, json.loads(txt) if txt else None
    except urllib.error.HTTPError as e:
        try:
            err = e.read().decode()
        except Exception:
            err = str(e)
        return e.code, err

# ----- Type translation: NeoDash report.type -> Aura widget settings.type -----
TYPE_MAP = {
    "value": "singleValue",
    "line": "line",
    "bar": "bar",
    "table": "table",
    "graph": "graph",
    "scatter": "scatter",
    "pie": "pie",
    "text": "markdown",  # NeoDash markdown report -> Aura markdown widget
}

def convert_widget(report):
    rtype = report.get("type", "table")
    wtype = TYPE_MAP.get(rtype, rtype)
    settings = {
        "type": wtype,
        "version": 1,
        "databaseName": "neo4j",
    }
    title = report.get("title", "") or ""
    if wtype == "markdown":
        # Aura markdown widget stores content in settings.content
        settings["content"] = report.get("query", "")
        # Aura requires non-empty title; derive from first markdown line if blank
        if not title:
            first_line = (report.get("query", "") or "").lstrip("#* ").splitlines()[0] if report.get("query") else "Notes"
            title = first_line[:60] or "Notes"
    else:
        settings["query"] = report.get("query", "")
        if wtype == "singleValue":
            settings.update({"fontSize": None, "textColor": None, "align": 4})
        elif wtype in ("line", "bar"):
            settings.update({
                "valueKeys": [],
                "orientation": "vertical",
                "scaleType": "linear",
                "showLegend": "auto",
                "showDataZoom": "auto",
                "enableDownloadImage": True,
            })
        else:
            settings["enableDownloadImage"] = True
    return {
        "version": 1,
        "title": title,
        "x": report.get("x", 0),
        "y": report.get("y", 0),
        "w": report.get("width", 6),
        "h": report.get("height", 3),
        "meta": {},
        "settings": settings,
    }

# ----- Main -----
nd = json.loads(NEODASH.read_text())
print(f"Source: {NEODASH.name} — {len(nd['pages'])} pages, "
      f"{sum(len(p['reports']) for p in nd['pages'])} reports")

# 1. Create dashboard shell
status, dash = http("POST", API_BASE, {
    "version": 2,
    "title": "HealthGraph — Whoop View (CLI upload)",
    "description": "Uploaded via console.neo4j.io shared-storage API",
    "deploymentType": "aura",
    "instanceId": INSTANCE_ID,
    "orderedPageIds": [],
    "params": [],
})
if status not in (200, 201):
    sys.exit(f"create dashboard failed: HTTP {status} — {dash}")
dashboard_id = dash["id"]
print(f"Created dashboard id={dashboard_id}")

# 2. For each page: POST /:dashboardId/pages, then POST widgets one by one
for page_idx, page in enumerate(nd["pages"]):
    s, p = http("POST", f"{API_BASE}/{dashboard_id}/pages", {
        "version": 1,
        "title": page["title"],
    })
    if s not in (200, 201):
        print(f"  ! page {page_idx} create failed: {s} {p}")
        continue
    page_id = p["id"]
    print(f"  page {page_idx+1}/{len(nd['pages'])}: {page['title']} (id={page_id})")
    for w_idx, report in enumerate(page["reports"]):
        widget = convert_widget(report)
        sw, wresp = http(
            "POST",
            f"{API_BASE}/{dashboard_id}/pages/{page_id}/widgets",
            widget,
        )
        if sw not in (200, 201):
            print(f"     ! widget {w_idx} ({report.get('title','')[:40]}): {sw} {wresp}"[:300])
        else:
            print(f"     ✓ widget {w_idx+1}: {report.get('title','')[:50]}")

print(f"\nDone. Open: https://console.neo4j.io/projects/{PROJECT_ID}/tools/dashboards/{dashboard_id}")
