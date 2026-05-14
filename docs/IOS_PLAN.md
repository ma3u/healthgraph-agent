# HealthGraphSync iPhone App — Build Plan

This doc tracks what's built, what's next, and what we explicitly chose to
skip. The companion architectural overview is in `docs/IOS_APP.md`.

**Status as of 2026-05-14:** scaffold complete, backend HTTP-tested end-to-end
in dry-run mode, iOS project builds against the iOS 26.5 SDK / Swift 6 for the
simulator. Not yet run on a real iPhone.

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

## Phase 1 — first real run (NEXT)

Goal: log in, sync one day of real HealthKit data into a sandbox Aura DB,
view the result in NeoDash from inside the app.

1. **Switch the active developer dir** so terminal Xcode tooling works:
   ```
   sudo xcode-select -s /Applications/Xcode.app/Contents/Developer
   ```
   (You'll be prompted for the sudo password.)

2. **Wait for the iOS 26.5 Simulator runtime** to finish downloading in the
   Xcode app. Until then, the project compiles but you can't boot a simulator.

3. **Pick a deployment target for the backend.** Easiest options:
   - Local + Tailscale Funnel (no DNS, free): expose `:8000` to your phone
   - Render / Fly.io / Railway free tier
   - Run on a Mac that's always on; expose via Tailscale alone (no Funnel)
     since your phone is on the same tailnet.

4. **Provision a sandbox Aura DB** (separate from your prod data). Set its
   credentials in `.env` so accidents stay isolated.

5. **Set the real config** in `ios/project.yml`:
   - `API_BASE_URL` → the URL from step 3
   - `NEODASH_URL` → your NeoDash dashboard URL
   - `DEVELOPMENT_TEAM` → your Apple developer team ID (from Xcode → Settings → Accounts)

6. **Regenerate the project** and open it:
   ```
   cd ios && xcodegen generate && open HealthGraphSync.xcodeproj
   ```

7. **Run on a real iPhone.** Simulators don't have HealthKit data by default,
   so first-run testing should be a tethered device. Trust the dev cert in
   Settings → General → VPN & Device Management.

8. **Verify the loop**: Login → Sync tab → Initial sync → grant HealthKit
   permissions → wait for progress to reach 100% → check the sandbox Aura
   browser for `Day` / `Workout` / `DailySummary` nodes.

**Done when:** the sync log on the phone matches Aura's node counts within a
few %, and the embedded NeoDash dashboard renders at least one chart with
your data.

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
