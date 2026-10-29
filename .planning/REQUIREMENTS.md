# Requirements: nx2android

**Defined:** 2026-10-29
**Core Value:** A tester on any supported host (Windows x64, macOS Apple Silicon, Linux x64, Linux arm64) can take their own Switch dump and get a working port onto their Android device through the GUI, without help.

## v1 Requirements

Requirements for the cross-platform GUI milestone. Each maps to a roadmap phase.

### Bridge (GUI ↔ porter)

- [ ] **BRDG-01**: User can cancel a running port and every child process (dotnet, MSBuild nodes, clang, shader tools) stops on Windows, macOS and Linux, while the adb server keeps running
- [ ] **BRDG-02**: User closing the window during a port is asked to confirm; confirming stops the run the same way Cancel does
- [ ] **BRDG-03**: User sees the real cause when a porter command fails (structured `error` event or JSON error), never a swallowed stderr or "no game found" for a crash
- [ ] **BRDG-04**: User sees a timeout message with a retry when a one-shot porter call hangs, instead of a stuck view
- [ ] **BRDG-05**: User can open the full saved log of any port run from the GUI
- [ ] **BRDG-06**: User sees "cancelled" only after the run has actually stopped

### Port

- [ ] **PORT-01**: User can add a game by picking its folder, see what was found (base, update, DLC, profile status), and port it with per-stage progress
- [ ] **PORT-02**: User sees whether a game may be ported (supported / experimental / not) as decided by porter, not by GUI logic

### Game library

- [ ] **LIB-01**: User sees every game they have ported in one view, with icon, name, status, built version and last port date, read from a porter-owned registry
- [ ] **LIB-02**: User sees an "update in folder" badge when the game folder holds a newer update than the build
- [ ] **LIB-03**: User can re-port a game after an update, and the port reuses that game's saved settings
- [ ] **LIB-04**: User sees when a game's folder is missing and can relocate it or remove the entry
- [ ] **LIB-05**: User can uninstall from a device, delete build files, or remove from the library as three separate confirmed actions; uninstall warns that saves on the device are lost
- [ ] **LIB-06**: User sees the profile's compatibility line (tested device and version, known issues) and a warning when their built version differs from the tested one

### Device manager

- [ ] **DEV-01**: User sees connected devices with their adb state, and a one-line fix for `unauthorized`, `offline` and `no permissions`
- [ ] **DEV-02**: User sees each device's compatibility verdict (BC textures, Vulkan 1.3, Android 10+, arm64, free space), with unknowns shown as unknown, next to the raw GPU/driver string
- [ ] **DEV-03**: User sees the device list update when a device is plugged in or removed
- [ ] **DEV-04**: User sees which ports are installed on each device and their versions
- [ ] **DEV-05**: User can install, update or remove a port on a chosen device; signer mismatch and save loss each get an explicit confirmation
- [ ] **DEV-06**: User can launch a ported app on the device from the GUI
- [ ] **DEV-07**: User can collect a filtered device log (logcat) for a run

### Per-game settings

- [ ] **SET-01**: User can set 60 fps, language, app name, update version and DLC per game; porter stores them and every later port of that game uses them, from the GUI or the CLI
- [ ] **SET-02**: User can edit env switches in an Advanced section and see a read-only preview of the effective `env.txt`
- [ ] **SET-03**: User sees what applying each setting costs (data pack only / APK rebuild / full re-port), decided by porter, and applying runs only that work
- [ ] **SET-04**: User can edit the touch overlay layout by dragging buttons on a canvas (a numeric table over the same rows if the canvas slips), applied through porter without editing the profile
- [ ] **SET-05**: User can reset a game's settings to defaults

### Guided first run

- [ ] **FRUN-01**: User on first launch is walked through the legal notice, prod.keys (validated, key generation shown), toolchain downloads (progress, cancel, resume, hash check) and connecting a first device
- [ ] **FRUN-02**: User can skip the wizard; a banner names what is missing until setup is complete, and setup can be reopened later
- [ ] **FRUN-03**: User's readiness state comes from porter (`setup --json`) on every launch; the GUI stores none of it

### Diagnostics

- [ ] **DIAG-01**: User can copy diagnostics with one button: doctor output, device info and verdict, inspect result, log tail, and the device log if collected

### Packaging

- [ ] **PKG-01**: User on Windows x64 can unzip the bundle and run it without installing Python
- [ ] **PKG-02**: User on macOS 14+ (Apple Silicon) can download the DMG in a browser and open the Developer ID-signed, notarized, stapled `.app` from Finder without Gatekeeper warnings
- [ ] **PKG-03**: User on Linux x64 (glibc 2.34+) can unpack the `tar.gz` bundle and run it under X11 and Wayland
- [ ] **PKG-04**: User on Linux arm64 (glibc 2.39+: Ubuntu 24.04+, Debian 13, Fedora 40+) can unpack the `tar.gz` bundle and run it under X11 and Wayland
- [ ] **PKG-05**: The bundle never writes into its own folder; it runs from a read-only location, and the macOS signature still verifies after a full port
- [ ] **PKG-06**: Python dependencies are pinned in a hashed universal lockfile, with build and dev requirements declared separately
- [ ] **PKG-07**: Downloaded toolchains (NDK, .NET, platform-tools) and NuGet packages are pinned to exact versions and hashes in one manifest

### CI

- [ ] **CI-01**: Every push runs the test suite on Windows, macOS, Linux x64 and Linux arm64
- [ ] **CI-02**: A release workflow builds all four bundles, signs and notarizes the macOS one, and smoke-tests each frozen bundle
- [ ] **CI-03**: Signing secrets live in a protected release environment, actions are pinned by SHA, and pull-request workflows cannot reach secrets
- [ ] **CI-04**: CI checks the Linux bundles' glibc symbol floor and reports the `nxnative/` diff against upstream

### Host toolchains

- [ ] **TOOL-01**: User on Linux arm64 gets a community arm64 NDK r27c detected or downloaded, verified by hash and a compile probe, and the host build uses its `linux-arm64` folder
- [ ] **TOOL-02**: User on Linux arm64 gets .NET 10 detected or downloaded
- [ ] **TOOL-03**: User on Linux sees the distro adb version; versions without `push -Z` are handled or refused with fix text, and "no permissions" points to the udev rules package
- [ ] **TOOL-04**: User launching the app from Finder or a desktop menu has every tool found by absolute path, without relying on the shell PATH

### Hardening

- [ ] **HARD-01**: Zip and tar extraction cannot write outside the unpack folder (symlinks, `..`, absolute paths); tar uses `filter='data'` and porter refuses Pythons without the CVE-2025-4517 fix (3.11.13 / 3.12.11 / 3.13.4+)
- [ ] **HARD-02**: The signing key is created with mode 0600 and written atomically, and porter refuses to regenerate it when it exists but cannot be read
- [ ] **HARD-03**: FPSLocker configs come from a pinned commit or their hash is recorded and shown in the port log
- [ ] **HARD-04**: User starting a second port of the same game folder gets a clear "already running" message (build-folder lock)
- [ ] **HARD-05**: A stage cut off mid-run is redone on the next run (stage stamps written last and atomically)
- [ ] **HARD-06**: The pipeline passes env dicts with absolute tool paths to subprocesses instead of mutating `os.environ`, and the upstream overrides are named and asserted at import
- [ ] **HARD-07**: A crash during the data-pack swap never leaves the game without a pack, and install hashes files in chunks
- [ ] **HARD-08**: Game names and other control-data strings render escaped in the GUI
- [ ] **HARD-09**: The disk-space check counts files recursively, including DLC folders, and re-checks after extraction
- [ ] **HARD-10**: Repository housekeeping is done: `probes/app/mkapk.py` uses the committed signer, the FLIP version is recorded, Ryujinx local changes are kept as a patch file, the commit hook is bootstrapped, `*.code-workspace` is ignored, and the language list has one source

### Tests

- [ ] **TEST-01**: Tests cover downloads and unpacking (crafted zip/tar), adb and install (resume, size parsing, stale-file removal, replace-signer), toolchain detection per OS, and CLI error paths
- [ ] **TEST-02**: The suite reports a clear skip instead of failing at import when optional engine modules (e.g. `lz4`) are missing
- [ ] **TEST-03**: GUI bridge tests replay golden JSON-lines fixtures and run headless (Qt offscreen)

### Verification

- [ ] **VER-01**: On each of the four hosts, a tester downloads the bundle and ports and installs at least one already-playable title end to end through the new GUI
- [ ] **VER-02**: Current upstream (shirai91/nx2android) merges into the fork with conflicts limited to hook lines in shared files

## v2 Requirements

Deferred to the next milestone. Tracked but not in the current roadmap.

### Games

- **GAME-01**: BotW and TotK are playable (status `playable`, tested on a device)
- **GAME-02**: Mario Kart 8 Deluxe is playable
- **GAME-03**: Super Mario Odyssey is playable
- **GAME-04**: Smash Ultimate is playable
- **GAME-05**: Unicorn Overlord (boots) and Xenoblade Chronicles 3 (WIP) are playable
- **GAME-06**: Super Mario Bros. Wonder holds 60 fps and shows button icons correctly

### Devices

- **DEVC-01**: Ports are verified on other Snapdragon/Adreno phones and tablets
- **DEVC-02**: Ports are verified on Snapdragon retro handhelds (AYN, Retroid)
- **DEVC-03**: Ports are verified on Samsung Xclipse devices

### Cheats

- **CHT-01**: User can drop Atmosphère cheat files per build ID and the engine's cheat VM runs them
- **CHT-02**: Profiles can ship default cheats as data
- **CHT-03**: User can toggle individual cheats in game from the pause menu
- **CHT-04**: User can manage a game's cheats from the GUI

### Wii / Wii U

- **WII-01**: Written feasibility verdict, with a throwaway spike, on PowerPC static recompilation of Wii and Wii U titles within this pipeline

### Later conveniences

- **LATER-01**: Wireless adb pairing
- **LATER-02**: Scan a games root folder for portable titles
- **LATER-03**: OS notifications when a port finishes
- **LATER-04**: Link to a newer release
- **LATER-05**: Save backup and restore (needs runtime support)

## Out of Scope

| Feature | Reason |
|---------|--------|
| macOS Intel bundle | No Intel test hardware; dropped rather than shipped unverified |
| Windows code signing | Testers can click through SmartScreen; revisit before any public release |
| AppImage / Flatpak | `tar.gz` is enough for testers and keeps the bundle's one-interpreter layout |
| Non-Python GUI toolkit | The frozen executable is also the pipeline's Python; another toolkit doubles runtimes and signing |
| Mali / PowerVR GPUs | No BC texture support, which the runtime requires |
| Shipping keys, game files or FPSLocker configs | Players supply their own; the warehouse configs have no license |
| Cover-art scraping, online update checks, telemetry | Network features with no value for a developer + testers audience |
| Desktop copies of pause-menu settings | Overlay on/off, rumble, fps display and docked mode already live in the in-game menu |
| Emulator-style graphics knobs | The port runs natively; per-title fixes belong in profiles |
| Batch or multi-device jobs | One port at a time keeps the lock and cancel model simple |
| Firmware step or help finding keys | Not needed by the pipeline; key acquisition is the player's responsibility |
| Public-release polish (installer, public docs, support) | This milestone is for the developer and a few testers |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| BRDG-01 | Phase 1 | Pending |
| BRDG-02 | Phase 1 | Pending |
| BRDG-03 | Phase 1 | Pending |
| BRDG-04 | Phase 1 | Pending |
| BRDG-05 | Phase 1 | Pending |
| BRDG-06 | Phase 1 | Pending |
| PORT-01 | Phase 4 | Pending |
| PORT-02 | Phase 4 | Pending |
| LIB-01 | Phase 4 | Pending |
| LIB-02 | Phase 4 | Pending |
| LIB-03 | Phase 4 | Pending |
| LIB-04 | Phase 4 | Pending |
| LIB-05 | Phase 4 | Pending |
| LIB-06 | Phase 4 | Pending |
| DEV-01 | Phase 3 | Pending |
| DEV-02 | Phase 5 | Pending |
| DEV-03 | Phase 5 | Pending |
| DEV-04 | Phase 5 | Pending |
| DEV-05 | Phase 5 | Pending |
| DEV-06 | Phase 5 | Pending |
| DEV-07 | Phase 5 | Pending |
| SET-01 | Phase 4 | Pending |
| SET-02 | Phase 4 | Pending |
| SET-03 | Phase 4 | Pending |
| SET-04 | Phase 4 | Pending |
| SET-05 | Phase 4 | Pending |
| FRUN-01 | Phase 3 | Pending |
| FRUN-02 | Phase 3 | Pending |
| FRUN-03 | Phase 3 | Pending |
| DIAG-01 | Phase 5 | Pending |
| PKG-01 | Phase 1 | Pending |
| PKG-02 | Phase 1 | Pending |
| PKG-03 | Phase 1 | Pending |
| PKG-04 | Phase 1 | Pending |
| PKG-05 | Phase 1 | Pending |
| PKG-06 | Phase 1 | Pending |
| PKG-07 | Phase 2 | Pending |
| CI-01 | Phase 1 | Pending |
| CI-02 | Phase 1 | Pending |
| CI-03 | Phase 1 | Pending |
| CI-04 | Phase 1 | Pending |
| TOOL-01 | Phase 3 | Pending |
| TOOL-02 | Phase 3 | Pending |
| TOOL-03 | Phase 3 | Pending |
| TOOL-04 | Phase 3 | Pending |
| HARD-01 | Phase 2 | Pending |
| HARD-02 | Phase 2 | Pending |
| HARD-03 | Phase 2 | Pending |
| HARD-04 | Phase 2 | Pending |
| HARD-05 | Phase 2 | Pending |
| HARD-06 | Phase 2 | Pending |
| HARD-07 | Phase 2 | Pending |
| HARD-08 | Phase 2 | Pending |
| HARD-09 | Phase 2 | Pending |
| HARD-10 | Phase 2 | Pending |
| TEST-01 | Phase 2 | Pending |
| TEST-02 | Phase 1 | Pending |
| TEST-03 | Phase 1 | Pending |
| VER-01 | Phase 6 | Pending |
| VER-02 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 60 total
- Mapped to phases: 60
- Unmapped: 0 ✓

---
*Requirements defined: 2026-10-29*
*Last updated: 2026-10-29 after roadmap creation*
