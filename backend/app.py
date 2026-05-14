"""FastAPI app for the HealthGraph iOS sync service.

Endpoints:
  GET  /health              liveness probe
  POST /auth/login          email+password -> JWT
  GET  /sync/state          auth-protected, returns last anchor + counts
  POST /ingest/healthkit    auth-protected, accepts an IngestPayload

Local run:
  cd backend
  uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload

Env (from repo .env or process env):
  NEO4J_URI              same as etl/ uses
  NEO4J_USER
  NEO4J_PASSWORD
  BACKEND_USER           login email
  BACKEND_PASSWORD_HASH  bcrypt hash
  BACKEND_JWT_SECRET     HS256 secret
  BACKEND_JWT_TTL_HOURS  default 720
  BACKEND_DRY_RUN        if "1", skip Aura writes (smoke testing)
"""

from __future__ import annotations

import os
import logging
import secrets
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm

from .auth import issue_token, require_user, verify_credentials
from .ingest import ingest_to_aura
from .models import (
    IngestPayload,
    IngestResponse,
    LoginResponse,
    SyncPreview,
    SyncState,
)
import sys
_BACKEND_DIR = Path(__file__).resolve().parent
_ETL_DIR = _BACKEND_DIR.parent / "etl"
if str(_ETL_DIR) not in sys.path:
    sys.path.insert(0, str(_ETL_DIR))
import load_to_neo4j  # type: ignore  noqa: E402

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("healthgraph.backend")

app = FastAPI(title="HealthGraph Sync API", version="0.1.0")

# CORS — permissive in dev so a browser-hosted NeoDash on a different origin can talk to /sync/state
# Tighten this in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("BACKEND_CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# In-memory sync state. For a single-user hackathon app this is fine; if you
# want this to survive restarts, persist it in Aura (e.g. a SyncState node).
_state = SyncState()


@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@app.post("/auth/login", response_model=LoginResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if not verify_credentials(form_data.username, form_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token, expires_at = issue_token(form_data.username)
    return LoginResponse(access_token=token, expires_at=expires_at)


@app.get("/sync/state", response_model=SyncState)
def sync_state(user: str = Depends(require_user)):
    return _state


@app.get("/sync/preview", response_model=SyncPreview)
def sync_preview(user: str = Depends(require_user)):
    """Return the last Day.date written to Aura so the iOS app can compute
    what's missing locally before uploading."""
    driver = load_to_neo4j.get_driver()
    try:
        with driver.session() as session:
            days = session.run(
                "MATCH (d:Day) RETURN max(d.date) AS latest, count(d) AS n"
            ).single()
            workouts = session.run(
                "MATCH (w:Workout) RETURN count(w) AS n"
            ).single()
            latest = days["latest"]
            return SyncPreview(
                latest_day_in_aura=str(latest) if latest else None,
                total_days_in_aura=days["n"] or 0,
                total_workouts_in_aura=workouts["n"] or 0,
            )
    finally:
        driver.close()


@app.post("/ingest/healthkit", response_model=IngestResponse)
def ingest_healthkit(payload: IngestPayload, user: str = Depends(require_user)):
    dry_run = os.environ.get("BACKEND_DRY_RUN") == "1"
    try:
        result = ingest_to_aura(payload, dry_run=dry_run)
    except Exception as exc:
        log.exception("Ingest failed")
        raise HTTPException(status_code=500, detail=f"Ingest failed: {exc}") from exc

    new_anchor = secrets.token_urlsafe(16)
    _state.last_anchor = new_anchor
    _state.last_sync_at = datetime.now(timezone.utc)
    _state.total_samples_seen += result["accepted_samples"] + result["accepted_workouts"]

    return IngestResponse(
        accepted_samples=result["accepted_samples"],
        accepted_workouts=result["accepted_workouts"],
        days_affected=result["days_affected"],
        server_anchor=new_anchor,
    )
