#!/usr/bin/env bash
# Set GitHub Actions secrets from values in .env so the daily snapshot
# workflow (.github/workflows/snapshot.yml) can run.
#
# Run from repo root:
#   bash scripts/setup_github_secrets.sh
#
# Requires: gh CLI, authenticated as the repo owner.

set -euo pipefail

if [ ! -f .env ]; then
    echo "ERROR: .env not found. Copy .env.example and fill it in first." >&2
    exit 1
fi

# Source .env into the script's environment without leaking on the command line
set -a
source .env
set +a

repo="ma3u/healthgraph-agent"

required=(NEO4J_URI NEO4J_USER NEO4J_PASSWORD)
optional=(AURA_INSTANCEID AURA_CLIENT_ID AURA_CLIENT_SECRET)

echo "Setting required secrets on $repo …"
for var in "${required[@]}"; do
    if [ -z "${!var:-}" ]; then
        echo "  ✗ $var is empty in .env — skipping" >&2
        continue
    fi
    gh secret set "$var" --repo "$repo" --body "${!var}"
    echo "  ✓ $var"
done

echo
echo "Setting optional secrets (needed for auto-resume of paused Aura) …"
for var in "${optional[@]}"; do
    if [ -z "${!var:-}" ]; then
        echo "  - $var not set in .env — skipping (optional)"
        continue
    fi
    gh secret set "$var" --repo "$repo" --body "${!var}"
    echo "  ✓ $var"
done

echo
echo "Done. Current secrets:"
gh secret list --repo "$repo"

echo
echo "Trigger the workflow manually with:"
echo "  gh workflow run snapshot.yml --repo $repo"
