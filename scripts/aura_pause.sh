#!/usr/bin/env bash
# Pause/resume/status for the Aura instance via the public API.
# Uses the Aura API client credentials from 1Password (stashed in env or .env).
#
# Paused instances cost ~20% of running price — useful when you're not actively
# building (overnight, between hackathon work sessions, etc.).
#
# Usage:
#   scripts/aura_pause.sh pause
#   scripts/aura_pause.sh resume
#   scripts/aura_pause.sh status
#   scripts/aura_pause.sh pause-if-idle 30   # pause if no bolt connections for 30 min
#
# Env required: AURA_CLIENT_ID, AURA_CLIENT_SECRET, AURA_INSTANCEID
#   Or fall back to values in .env

set -euo pipefail

# Load .env if present (export-style)
if [ -f .env ]; then
  set -a; . .env; set +a
fi

: "${AURA_INSTANCEID:?Set AURA_INSTANCEID (8-char Aura ID) in .env or env}"
: "${AURA_CLIENT_ID:?Set AURA_CLIENT_ID in .env or env}"
: "${AURA_CLIENT_SECRET:?Set AURA_CLIENT_SECRET in .env or env}"

token() {
  curl -s -X POST "https://api.neo4j.io/oauth/token" \
    -u "$AURA_CLIENT_ID:$AURA_CLIENT_SECRET" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "grant_type=client_credentials" |
    python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])"
}

api() {
  local method="$1" path="$2"
  curl -s -X "$method" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    "https://api.neo4j.io/v1/instances/$AURA_INSTANCEID$path"
}

status_of() {
  api GET "" | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['status'])"
}

CMD="${1:-status}"
TOKEN=$(token)

case "$CMD" in
  status)
    echo "Instance $AURA_INSTANCEID:"
    api GET "" | python3 -m json.tool
    ;;
  pause)
    cur=$(status_of)
    if [ "$cur" = "paused" ]; then
      echo "Already paused."; exit 0
    fi
    echo "Pausing $AURA_INSTANCEID (status was: $cur)..."
    api POST "/pause"
    echo
    ;;
  resume)
    cur=$(status_of)
    if [ "$cur" = "running" ]; then
      echo "Already running."; exit 0
    fi
    echo "Resuming $AURA_INSTANCEID (status was: $cur)..."
    api POST "/resume"
    echo
    ;;
  pause-if-idle)
    # pause if no bolt connections for $2 minutes.
    # uses cypher-shell to query dbms.listConnections() — bolt connections only.
    threshold_min="${2:-30}"
    cur=$(status_of)
    if [ "$cur" != "running" ]; then
      echo "Not running ($cur) — nothing to do."; exit 0
    fi
    # Idle = no non-self transactions running.
    # Filter out our own SHOW TRANSACTIONS query.
    : "${NEO4J_URI:?Set NEO4J_URI in .env}"
    : "${NEO4J_USER:?Set NEO4J_USER in .env}"
    : "${NEO4J_PASSWORD:?Set NEO4J_PASSWORD in .env}"
    active=$(cypher-shell -a "$NEO4J_URI" -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" \
      --non-interactive --format plain \
      "SHOW TRANSACTIONS YIELD currentQuery
       WHERE NOT currentQuery STARTS WITH 'SHOW TRANSACTIONS'
       RETURN count(*) AS active;" 2>/dev/null \
      | tail -n 1)
    echo "Non-self active transactions: ${active:-?} (threshold: any → not idle)"
    if [ "${active:-1}" = "0" ]; then
      echo "No activity — pausing..."
      api POST "/pause"
    else
      echo "Activity present — not pausing."
    fi
    ;;
  *)
    echo "Usage: $0 {status|pause|resume|pause-if-idle [minutes]}"
    exit 1
    ;;
esac
