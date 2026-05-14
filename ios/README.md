# HealthGraphSync (iOS)

Native iOS app that:

1. Logs into the [sync backend](../backend/README.md) (email + password → JWT,
   stored in iOS Keychain).
2. Reads HealthKit samples (heart rate, sleep, steps, workouts, etc.).
3. POSTs them to the backend for ingestion into **Neo4j Aura**.
4. Embeds the existing **NeoDash** dashboard in a WKWebView so you can view
   results without leaving the app.

```
┌─────────────────────┐    JWT + JSON     ┌─────────────────────┐    MERGE     ┌──────────────┐
│  HealthGraphSync.app│ ───────────────▶  │  FastAPI backend    │ ───────────▶ │  Neo4j Aura  │
│  (iPhone, HealthKit)│ ◀───────────────  │  (reuses etl/)      │              └──────────────┘
└─────────────────────┘    server_anchor  └─────────────────────┘
        │
        └── WKWebView ─────▶  NeoDash dashboard (NEODASH_URL)
```

## Generate the Xcode project

The Swift sources live under `HealthGraphSync/Sources/`. To get a buildable
`.xcodeproj`, use [XcodeGen](https://github.com/yonaskolb/XcodeGen):

```sh
brew install xcodegen
cd ios
xcodegen generate
open HealthGraphSync.xcodeproj
```

The generated project includes:

- HealthKit capability + entitlement
- `NSHealthShareUsageDescription` in Info.plist
- Custom Info.plist keys `API_BASE_URL` and `NEODASH_URL` that the app reads
  via `AppConfig.swift`

Before signing & running on a device, edit `ios/project.yml` and set
`DEVELOPMENT_TEAM` to your Apple developer team ID, then re-run
`xcodegen generate`.

## Configuration

Either edit `project.yml` and regenerate, or edit `Info.plist` directly after
generation:

| Key             | Example                                                | Purpose                            |
| --------------- | ------------------------------------------------------ | ---------------------------------- |
| `API_BASE_URL`  | `https://healthgraph.your-domain.com`                  | Backend base URL.                  |
| `NEODASH_URL`   | `https://neodash.your-domain.com/?dashboardName=Whoop` | Dashboard URL embedded in WKWebView. |

## Running

1. Make sure the **backend** is running and reachable from your phone
   (e.g. via Tailscale/Funnel or a deployed instance). `localhost` will only
   work from the simulator.
2. In Xcode: pick a target device or simulator, build & run.
3. Log in with the credentials configured in the backend's `.env`.
4. **Sync tab → "Initial sync"** — the app will request HealthKit permissions,
   then upload your history month-by-month.
5. **Dashboard tab** shows the embedded NeoDash.

## Manual setup (without XcodeGen)

If you'd rather not install XcodeGen:

1. Xcode → File → New → Project → App → name it `HealthGraphSync`, choose
   SwiftUI, iOS 17+, Swift 6.
2. Delete the auto-generated `ContentView.swift` and `*App.swift`.
3. Drag all files under `HealthGraphSync/Sources/HealthGraphSync/` into the
   project (keep groups in sync with folders).
4. Target → Signing & Capabilities → "+" → **HealthKit**.
5. Target → Info → add `NSHealthShareUsageDescription` and
   `NSHealthUpdateUsageDescription` strings.
6. Target → Info → add `API_BASE_URL` (String) and `NEODASH_URL` (String).

## Known v1 limitations

- **No per-sample storage in Aura.** The backend reuses the existing pipeline
  which aggregates to `DailySummary` nodes; HealthKit *deletions* therefore
  can't be reflected. Move to per-sample nodes if you need delete-fidelity.
- **Single user.** Auth is one email/password pair from env. See
  `backend/README.md` for the upgrade path.
- **iCloud sync gap.** HealthKit can take a while to sync from Apple Watch
  to iPhone. If a recent workout doesn't appear after sync, give iCloud a
  minute and try Incremental again.
