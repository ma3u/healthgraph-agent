# Installing on a real iPhone

## Prerequisites (one-time)

1. **Sign in to Xcode with your Apple ID.**
   `Xcode → Settings → Accounts → "+" → Apple ID`. Complete 2FA. Your team
   appears under the account on the right.

2. **Generate an Apple Development certificate on this Mac.**
   In the same dialog, click **"+" → "Apple Development"**. Xcode generates a
   cert and puts the private key into this Mac's Keychain. Verify:

   ```sh
   security find-identity -p codesigning -v
   # should show one valid identity now
   ```

3. **Find your Team ID.** Same Accounts pane — it's the 10-character code
   shown next to your name in the team list, or run:

   ```sh
   xcrun altool --list-apps 2>/dev/null  # if you have App Store Connect
   ```

4. **Set the Team ID in `ios/project.yml`** under `settings.base.DEVELOPMENT_TEAM`.
   Then regenerate:

   ```sh
   cd ios && xcodegen generate
   ```

5. **Connect & trust the iPhone.**
   - Plug in via USB-C.
   - On first connect, the iPhone shows "Trust this computer?" — tap Trust.
   - The Mac prompts for the iPhone's passcode.

## Verify the device is visible

```sh
xcrun devicectl list devices
# Should list "Mabu" or your iPhone's name with State=connected
```

## Build & install (CLI)

Use the device ID (UDID) from the previous command:

```sh
DEVICE_ID="BB59A0C5-44D2-5C01-9916-4023884E4106"   # yours

cd ios
xcodebuild \
  -project HealthGraphSync.xcodeproj \
  -scheme HealthGraphSync \
  -destination "id=$DEVICE_ID" \
  -configuration Debug \
  -allowProvisioningUpdates \
  build

# Install the freshly built .app
APP_PATH=$(xcodebuild -project HealthGraphSync.xcodeproj -scheme HealthGraphSync \
  -destination "id=$DEVICE_ID" -configuration Debug \
  -showBuildSettings 2>/dev/null \
  | awk -F' = ' '/^[[:space:]]*BUILT_PRODUCTS_DIR/ {print $2}' | head -1)/HealthGraphSync.app

xcrun devicectl device install app --device "$DEVICE_ID" "$APP_PATH"
```

## First launch on device

1. On the iPhone, tap the **HealthGraph Sync** icon.
2. iOS will refuse to open it with: *"Untrusted Developer"*. Go to
   **Settings → General → VPN & Device Management → [your Apple ID] → Trust**.
   Confirm in the dialog.
3. Launch the app again.
4. **HealthKit permission prompt** appears — grant read access for all
   requested types. (You can change this anytime in
   *Settings → Privacy & Security → Health → HealthGraph Sync*.)
5. **Sign in** with your `BACKEND_USER` / plaintext password.
6. **Sync tab → "Check what's missing"** — the app calls the backend, fetches
   the latest Day in Aura (today: `2026-04-15`), scans HealthKit from that
   date, and shows you a per-type breakdown of samples to upload.
7. Tap **"Confirm & Upload"**. On success the app switches to the
   **Dashboard tab** (NeoDash WebView).

## Free-tier limitations

A free Apple ID gives you **7-day** signing — after a week the cert expires
and the app on the phone stops opening until you rebuild + reinstall. A
$99/year Apple Developer Program membership extends this to 1 year.

## Troubleshooting

- *"No signing certificate found"*: skipped step 2 above. Click **"+" → Apple
  Development** in the Xcode signing dialog.
- *"Could not launch app — Untrusted developer"*: see step 2 of "First launch
  on device".
- *Device not appearing in `devicectl list devices`*: re-plug the USB-C cable,
  unlock the iPhone, accept the "Trust" prompt again, and re-run.

## HealthKit permission gotcha

On first sync the iOS permission sheet lists every HK type the app requests
(HeartRate, RestingHeartRate, HRV, StepCount, ActiveEnergyBurned, sleep, etc.)
and **each one is individually toggleable**. If you tap *Allow* without
flipping every switch on, the un-toggled types are silently denied — the
sync will run but those types return zero samples.

To check or re-enable later: **Settings → Privacy & Security → Health →
HealthGraph Sync**. Toggle on every category you want synced. Re-run the
sync — it'll now pick up the previously-missing types.

(Bug-symptom that points here: the *Sync* tab's *Quantity samples* list
omits common types like StepCount or HeartRate but shows others.)
- *Backend unreachable*: `localhost` works only from the iOS Simulator. From a
  real iPhone you need either a Tailscale-funneled URL or a deployed backend.
  Update `API_BASE_URL` in `ios/project.yml` and re-run `xcodegen generate`.
