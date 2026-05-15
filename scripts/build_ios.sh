#!/usr/bin/env bash
# Build & install HealthGraphSync on the connected iPhone.
#
# Reads dev-mode secrets (AURA_GRAPHQL_URL + AURA_GRAPHQL_API_KEY) from .env
# and patches them into the freshly-generated Info.plist after xcodegen runs.
# This avoids committing the API key to git.
#
# Usage (from repo root):
#   bash scripts/build_ios.sh                       # build + install on first device
#   DEVICE_ID=BB59A0C5-... bash scripts/build_ios.sh

set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
    echo "ERROR: .env not found" >&2
    exit 1
fi
set -a; source .env; set +a

if [ -z "${AURA_GRAPHQL_URL:-}" ] || [ -z "${AURA_GRAPHQL_API_KEY:-}" ]; then
    echo "ERROR: AURA_GRAPHQL_URL or AURA_GRAPHQL_API_KEY missing from .env" >&2
    echo "       Run scripts/create_aura_data_api.py first." >&2
    exit 1
fi

# Pick the connected device unless DEVICE_ID is set explicitly
if [ -z "${DEVICE_ID:-}" ]; then
    DEVICE_ID=$(xcrun devicectl list devices 2>/dev/null \
                | awk '/connected.*iPhone/ {print $3; exit}')
    if [ -z "$DEVICE_ID" ]; then
        echo "ERROR: no connected iPhone. Plug it in and try again." >&2
        exit 1
    fi
fi
echo "Target device: $DEVICE_ID"

cd ios

# 1. Regenerate the project (idempotent)
xcodegen generate >/dev/null

# 2. Patch the freshly-generated Info.plist with the dev secrets so the app
#    can bypass Auth0 and talk directly to the GraphQL Data API.
INFO_PLIST="HealthGraphSync/Resources/Info.plist"
/usr/libexec/PlistBuddy -c "Set :DEV_AURA_GRAPHQL_URL $AURA_GRAPHQL_URL" "$INFO_PLIST"
/usr/libexec/PlistBuddy -c "Set :DEV_AURA_API_KEY $AURA_GRAPHQL_API_KEY" "$INFO_PLIST"
if [ -n "${NEODASH_URL:-}" ]; then
    /usr/libexec/PlistBuddy -c "Set :NEODASH_URL $NEODASH_URL" "$INFO_PLIST"
    echo "  patched NEODASH_URL → $NEODASH_URL"
fi
if [ -n "${AURA_DASHBOARD_URL:-}" ]; then
    /usr/libexec/PlistBuddy -c "Set :AURA_DASHBOARD_URL $AURA_DASHBOARD_URL" "$INFO_PLIST"
    echo "  patched AURA_DASHBOARD_URL → $AURA_DASHBOARD_URL"
fi
# Aura Agent (Dashboard "Ask your graph" panel). All four must be set or the
# panel stays hidden.
if [ -n "${AURA_AGENT_URL:-}" ] && [ -n "${AURA_AGENT_TOKEN_URL:-}" ] \
   && [ -n "${AURA_AGENT_CLIENT_ID:-}" ] && [ -n "${AURA_AGENT_CLIENT_SECRET:-}" ]; then
    /usr/libexec/PlistBuddy -c "Set :AURA_AGENT_URL $AURA_AGENT_URL" "$INFO_PLIST"
    /usr/libexec/PlistBuddy -c "Set :AURA_AGENT_TOKEN_URL $AURA_AGENT_TOKEN_URL" "$INFO_PLIST"
    /usr/libexec/PlistBuddy -c "Set :AURA_AGENT_CLIENT_ID $AURA_AGENT_CLIENT_ID" "$INFO_PLIST"
    /usr/libexec/PlistBuddy -c "Set :AURA_AGENT_CLIENT_SECRET $AURA_AGENT_CLIENT_SECRET" "$INFO_PLIST"
    echo "  patched AURA_AGENT_* (Dashboard 'Ask your graph' enabled)"
fi
# Auth0 production path — if AUTH0_DOMAIN is set in .env, switch from dev-mode
# to real Auth0 sign-in. Clears DEV_AURA_* so AppConfig.isDevMode returns false.
if [ -n "${AUTH0_DOMAIN:-}" ] && [ -n "${AUTH0_CLIENT_ID:-}" ]; then
    /usr/libexec/PlistBuddy -c "Set :AUTH0_DOMAIN $AUTH0_DOMAIN" "$INFO_PLIST"
    /usr/libexec/PlistBuddy -c "Set :AUTH0_CLIENT_ID $AUTH0_CLIENT_ID" "$INFO_PLIST"
    /usr/libexec/PlistBuddy -c "Set :AUTH0_AUDIENCE ${AUTH0_AUDIENCE:-https://healthgraph.io/aura}" "$INFO_PLIST"
    /usr/libexec/PlistBuddy -c "Set :DEV_AURA_GRAPHQL_URL " "$INFO_PLIST"
    /usr/libexec/PlistBuddy -c "Set :DEV_AURA_API_KEY " "$INFO_PLIST"
    echo "  patched AUTH0_DOMAIN/_CLIENT_ID/_AUDIENCE (Auth0 production path)"
    echo "  cleared DEV_AURA_* (dev-mode disabled)"
else
    echo "  patched DEV_AURA_GRAPHQL_URL + DEV_AURA_API_KEY (dev-mode path)"
fi

# 3. Build
echo "Building for $DEVICE_ID..."
xcodebuild \
    -project HealthGraphSync.xcodeproj \
    -scheme HealthGraphSync \
    -destination "id=$DEVICE_ID" \
    -configuration Debug \
    -allowProvisioningUpdates \
    build 2>&1 | tail -3

# 4. Install
APP_PATH=$(xcodebuild \
    -project HealthGraphSync.xcodeproj \
    -scheme HealthGraphSync \
    -destination "id=$DEVICE_ID" \
    -configuration Debug \
    -showBuildSettings 2>/dev/null \
    | awk -F' = ' '/^[[:space:]]*BUILT_PRODUCTS_DIR/ {print $2}' | head -1)/HealthGraphSync.app

echo "Installing $APP_PATH ..."
xcrun devicectl device install app --device "$DEVICE_ID" "$APP_PATH" 2>&1 | tail -3

echo
echo "Done. Launch HealthGraph Sync on the iPhone."
echo "  - Dev-mode: app skips Auth0 and talks directly to your GraphQL Data API"
echo "  - To switch back to Auth0 production path: clear DEV_AURA_* from"
echo "    Info.plist and set AUTH0_DOMAIN/CLIENT_ID/AUDIENCE in project.yml"
