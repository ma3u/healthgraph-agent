# HealthGraphSync iPhone App — Build Plan

This doc tracks what's built, what's next, and what we explicitly chose to
skip. The companion architectural overview is in `docs/IOS_APP.md`.

**Status as of 2026-05-14 (post-pivot):**

- Architecture pivoted from FastAPI-in-the-middle to **direct iOS ↔ Aura
  GraphQL Data API with Auth0 sign-in**. See
  [`AUTH_RESEARCH.md`](AUTH_RESEARCH.md) for why. The FastAPI backend lives
  on as `archive/backend-legacy/` for reference.
- iOS project builds (Swift 6, iOS 26.5 SDK). Sources rewritten for the new
  flow: `Auth0Client`, `AuraConnection`, `ConnectView`, `GraphQLClient`,
  `AuraIngest`, mutation-based `SyncCoordinator`.
- App icon designed and bundled.
- GraphQL SDL with `@cypher` mutations (`ingestDay` / `ingestWorkout` /
  `ingestSleep`) committed in `cypher/graphql_schema.graphql`.
- **Mutations smoke-tested against real Aura via `scripts/test_aura_mutations.py`:
  all three pass, idempotency verified, cleanup green.** This is the Phase 1
  local-test win.
- Historical data: 3,087 days from 2017-10-29 → 2026-04-15 already in Aura
  via offline `etl/`. The iOS app picks up from 2026-04-16 forward.

---

## Phase 0 — scaffold (DONE)

- [x] FastAPI backend in `backend/` reusing `etl/transform.py` +
  `etl/load_to_neo4j.py`. Endpoints: `/health`, `/auth/login`, `/sync/state`,
  `/ingest/healthkit`. JWT auth (single user, env-configured).
- [x] iOS sources in `ios/HealthGraphSync/Sources/HealthGraphSync/`:
  - `HealthGraphSyncApp` + `RootView` (login gate)
  - `AppConfig` (reads `API_BASE_URL`, `NEODASH_URL` from Info.plist)
  - `Keychain` + `AuthStore` (JWT storage)
  - `APIClient` (URLSession; `/auth/login` + `/ingest/healthkit`)
  - `HealthKitTypes` (cleaned identifiers matching `etl/transform.py`)
  - `HealthKitService` (initial sync month-by-month + incremental via
    `HKAnchoredObjectQuery`)
  - `SyncCoordinator` (UI-bound progress state)
  - SwiftUI screens: `LoginView`, `MainTabsView`, `SyncView`, `DashboardView`
    (WKWebView for NeoDash), `SettingsView`
- [x] `ios/project.yml` → `xcodegen` → buildable `.xcodeproj`
- [x] HealthKit entitlement + Info.plist usage strings
- [x] Local backend smoke test: login → ingest example payload → dry-run
  produces 2 daily summaries + 1 sleep session, no Aura write
- [x] iOS app compiles for iOS Simulator (arm64 + x86_64) under Swift 6 strict
  concurrency
- [x] Docs: `backend/README.md`, `ios/README.md`, `docs/IOS_APP.md`

---

## Phase 1 — first real run (in progress)

Goal: prove every layer of the new stack works against the **real** Aura
instance, ending with the user signing in on a real iPhone and syncing a
delta day end-to-end.

### 1.1 Local mutation smoke test ✅ DONE

Validate the `@cypher` mutations from the SDL run cleanly against your live
Aura, *before* spending time on Auth0 setup. Uses `.env` credentials and a
test date (`2099-01-01`) cleaned up at the end.

```sh
archive/backend-legacy/.venv/bin/python scripts/test_aura_mutations.py
```

Expected (and what we observed on 2026-05-14):

```
✅ All three @cypher mutations succeeded against real Aura.
✅ Idempotency (re-run with new values) verified.
✅ Cleanup left baseline counts unchanged.
```

### 1.2 Aura GraphQL Data API up (USER ACTION)

In the Aura Console → **GraphQL Data APIs** tab (the page in the screenshot
that started this thread):

1. Click **Create** → **Define my own** → paste the contents of
   `cypher/graphql_schema.graphql`.
2. Name the API something like *HealthGraph*.
3. After it's created, copy the **endpoint URL** (looks like
   `https://<api-id>.<region>.data.neo4j.io/graphql`) — you'll need it for
   the iOS app's Connect screen.
4. Add a **JWKS auth provider** pointing at your Auth0 tenant. See §1.3.

### 1.3 Auth0 tenant (USER ACTION)

Walk through **`docs/AUTH_SETUP.md`** — roughly 15 minutes:

- Create Auth0 tenant
- Native iOS application with callback `io.healthgraph.sync://callback`
- Enable Apple + Google + GitHub + Microsoft social connections
- Create an API audience (any URL string)
- `aura-cli data-api graphql auth-provider create … --type jwks --url
  https://YOUR_TENANT.us.auth0.com/.well-known/jwks.json`

### 1.4 iOS project config (USER ACTION + REGEN)

Edit `ios/project.yml`:

```yaml
info:
  properties:
    AUTH0_DOMAIN: YOUR_TENANT.us.auth0.com
    AUTH0_CLIENT_ID: ...
    AUTH0_AUDIENCE: https://healthgraph.io/aura
settings:
  base:
    DEVELOPMENT_TEAM: YOUR_TEAM_ID    # from Xcode → Settings → Accounts
```

Then:

```sh
cd ios && xcodegen generate
```

### 1.5 Manual curl test (verify the wires)

Per `docs/AUTH_SETUP.md` §7: grab a JWT from the Auth0 dashboard, then:

```sh
curl -X POST "$AURA_GRAPHQL_ENDPOINT" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"query":"{ days(options:{sort:[{date: DESC}], limit: 1}) { date } }"}'
```

Expect a JSON response with `data.days[0].date == "2026-04-15"`.

### 1.5b Dev-mode shortcut ✅ DONE

While Auth0 setup is pending, the iOS app supports a **dev-mode** that
bypasses Auth0 entirely and talks directly to the Aura GraphQL Data API
using `x-api-key`. Triggered when `AUTH0_DOMAIN` is empty AND
`DEV_AURA_GRAPHQL_URL` + `DEV_AURA_API_KEY` are set in `Info.plist`.

`scripts/build_ios.sh` wraps the whole loop — reads `.env`, patches the
Info.plist (secrets never committed), regenerates the xcodeproj, builds
for the connected iPhone, and installs:

```sh
bash scripts/build_ios.sh
```

### 1.6 Device install ✅ docs ready

Follow `docs/IOS_DEVICE_INSTALL.md`:

- Xcode → Settings → Accounts → Apple ID → 2FA
- "+" → Apple Development (puts cert + private key in Keychain)
- `xcodebuild … -allowProvisioningUpdates build` and
  `xcrun devicectl device install app …`
- On the iPhone: Settings → General → VPN & Device Management → Trust

### 1.7 End-to-end on device

In order on the iPhone:

1. **HealthGraphSync icon → Continue** → Auth0 sheet → pick a social
   provider → land back in the app.
2. **Connect screen** → paste the Aura GraphQL endpoint URL → app does a
   `{ __typename }` probe → green.
3. **Sync tab → "Check what's missing"** — calls Aura for `max(Day.date)`
   (2026-04-15), scans HealthKit since then, shows per-type counts.
4. **Confirm & Upload** — three mutations per day (`ingestDay`,
   `ingestWorkout`, `ingestSleep`).
5. On success, the app auto-switches to **Dashboard** (NeoDash WebView).

### Done when

- `MATCH (d:Day) RETURN max(d.date)` in Aura returns a date ≥ today.
- The Dashboard tab renders at least one chart with data through today.
- A second sync run an hour later reports "0 days to upload" (idempotency).

---

## Phase 2 — production-ready polish

- [ ] **Pre-flight server check** in the app: ping `/health` before login so
  errors are clearer than "401" when the backend is down.
- [ ] **Per-type chunking** for initial sync. Months that contain a year of
  HRV at 5-min granularity can produce 50k samples — split by week instead
  of month when payload would exceed N samples.
- [ ] **Background refresh** via `BGAppRefreshTask` + `HKObserverQuery` so
  sync runs without the user opening the app. Requires
  `enableBackgroundDeliveryForType` per HK type.
- [ ] **Retry / resume.** Persist a `lastSuccessfulMonth` flag so a network
  blip during initial sync doesn't restart from year zero on next launch.
- [ ] **Visible diagnostics screen.** Last 20 sync runs (count, days,
  duration, error). Surfaces silent regressions.
- [ ] **HTTPS everywhere.** Right now `API_BASE_URL` may be `http://localhost`
  for dev; ATS will block release builds. Add an explicit
  `NSAppTransportSecurity` exception for local dev or move to Tailscale-HTTPS.

---

## Phase 3 — graph fidelity

Things the v1 ingest deliberately doesn't do, with the upgrade path:

- [ ] **Per-sample nodes.** Today only `DailySummary` lands in Aura. To
  reflect HealthKit deletions / corrections faithfully, add `(:Sample {uuid,
  type, value, unit, start, end})` plus `(:Sample)-[:ON_DAY]->(:Day)` and
  rebuild `DailySummary` from the sample set on every change. The anchored
  query already gives us deletion UUIDs — they're just dropped today.
- [ ] **Source attribution.** `HKSourceRevision` is already in the payload
  (`source_name`, `source_version`). Promote it to a `(:Source)` node so we
  can answer "which device contributed this metric?" in Cypher.
- [ ] **Workout statistics & events.** `HKWorkout.workoutEvents` (laps, pause
  / resume) and `statistics(for:)` (avg HR per workout) aren't carried over.
  Extend `WorkoutPayload` + the ingest translator.
- [ ] **Categorical sleep stages.** SleepAnalysis currently lands as a single
  duration. Split into `(:SleepStage {name, minutes})` per stage so the
  longevity report can distinguish REM vs deep deficit.

---

## Phase 4 — beyond the hackathon

Out of scope for the Jun 15 deadline; capture here so we don't forget.

- [ ] **Multi-user.** Replace env-backed auth with a real user store and
  scope writes by `Person.name`. Add per-user Aura instance routing if we
  want full isolation rather than logical separation.
- [ ] **HealthKit *write* capability.** If the agent ever recommends "log a
  walk", we'd need write entitlements (`HKQuantityTypeIdentifier...` + share
  authorization). Keep this off the v1 release.
- [ ] **WhoOp / Oura integration.** The existing `cypher/whoop_queries.cypher`
  hints at this — pulling Whoop via their REST API instead of just HealthKit.
  Backend can grow another `/ingest/whoop` route that reuses the same
  transform pipeline.
- [ ] **App Store submission.** Privacy nutrition labels need to be filled
  out before submission; the data is uploaded to a server you control, which
  Apple treats as "linked to user" for "health & fitness" data.

---

## Decisions we already made (so we don't re-litigate)

- **No Aura Swift SDK.** There isn't one. Direct app-to-Aura was rejected
  because it puts DB creds on the device and forces a Swift rewrite of
  `etl/transform.py`.
- **WebView for NeoDash.** Chosen over building native SwiftUI charts so we
  ship faster and reuse `neodash/longevity_dashboard.json` and
  `neodash/whoop_dashboard.json`.
- **Single user.** The hackathon target is one person's data into one Aura
  instance. Multi-user is a Phase 4 problem.
- **MERGE everywhere.** Ingest is idempotent on purpose so retries are safe
  and the iOS app doesn't need to track per-sample upload state — it just
  re-sends affected full days.

---

## Open questions for the user

These will block parts of Phase 1 — answer when you get to them, not before:

1. **Backend hosting.** Local + Tailscale, or hosted (Fly / Render)? Affects
   `API_BASE_URL` and TLS posture.
2. **Apple developer team.** Personal team (free, 7-day signing) is enough
   for testing. Paid team ($99/year) is needed if we want longer device
   lifetimes or App Store submission.
3. **Aura sandbox.** Spin up a second Aura instance for the iOS path, or are
   you comfortable pointing the app at the existing one? Sandbox is safer
   while we iron out incremental-sync semantics.
4. **NeoDash hosting.** The dashboard JSON exists locally
   (`neodash/longevity_dashboard.json`); where is NeoDash actually running
   for the `NEODASH_URL` to point at?
