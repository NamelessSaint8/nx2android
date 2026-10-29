# Feature Research

**Domain:** Desktop frontend for a Switch-to-Android porting pipeline: game library, Android device manager, per-game settings, guided first run
**Researched:** 2026-10-29
**Confidence:** MEDIUM overall. The parts about what the codebase already does are HIGH (read straight from `porter/` and `nxnative/dm/`). Competitor behaviour is MEDIUM: it comes from training knowledge of yuzu/Eden, Ryujinx, Dolphin, Cemu, Playnite, Lutris and SideQuest, and web searches only partly confirmed it (those searches rate LOW on their own). Device-probe commands are HIGH where they follow the AOSP spec.

## Framing: what this audience actually needs

There's no competitor that does the same job, so the closest models are:

- **Emulator frontends** (yuzu/Eden/Citron, Ryujinx/Ryubing, Dolphin, Cemu): a library grid, a per-game "Properties" dialog laid over global settings, and a first-run step for keys and firmware.
- **Library managers** (Playnite, Lutris, Heroic): status columns, the difference between "uninstall" and "remove from library", and update badges.
- **Android sideload tools** (SideQuest, scrcpy GUIs, ADB managers): a device picker that shows adb states, a list of installed apps on each device, install/uninstall, and a warning that uninstalling loses data.

The audience is the developer plus a few testers. When a tester gets stuck, the developer debugs it from a distance. So the features worth the most are the ones that make a failure **understandable and reportable**: a real error, a log you can copy, a compatibility verdict. Discovery and polish features (art scraping, playtime, themes) are worth almost nothing to this group.

### Facts from the codebase that shape every feature (HIGH)

| Fact | Where | Consequence for the GUI |
|------|-------|-------------------------|
| A build lives in `<game folder>/<title ID>_build/`. The data pack carries a JSON manifest (`title_id, name, package, version, display, language, requires, dlc, made`) | `porter/datapack.py` `build`, `read_manifest` | Nothing central lists the ported games. The library needs a registry that porter writes when a port succeeds |
| Language, the profile's `env` rows and 60 fps all end up in the data pack's `env.txt` (plus fps files) | `porter/datapack.py`, `porter/pipeline.py` `data` | Changing them means rebuilding the data pack and pushing it again. The APK doesn't need a rebuild |
| The touch overlay layout is compiled into the host (`android_profile.h`, `DM_AOV_TABLE`) from `overlay_default.tsv` plus the profile's `overlay` rows | `nxnative/dm/android/overlay_default.tsv`, `tools/android_profile.py` | Changing the layout means a `host` + `apk` rebuild (an NDK build) |
| The pause menu on the device already toggles overlay on/off, rumble, the fps display and docked/handheld, and lets the player drag the menu button. These are saved in the app's `settings.txt` | `nxnative/dm/android/front_android.c` | Don't duplicate these in the desktop GUI |
| Saves live in the app's internal storage. Uninstalling, or `--replace-signer`, deletes them. An update keeps them | `porter/adb.py` `install`, `porter/install.py` | Every uninstall or signer replacement needs an explicit "your saves will be deleted" confirmation. Backing up saves isn't possible without runtime support |
| `Adb.gpu()` and `Adb.bc_textures()` already exist (SurfaceFlinger GLES line, vendor heuristic). `free_bytes`, `installed(package)` exist too | `porter/adb.py` | The device manager is mostly a matter of exposing what's there through `porter devices --json` |
| Captured shaders are pulled from the device before a re-port (`pull_captures`) | `porter/pipeline.py` | A re-port should run with the device connected, and uninstalling throws those captures away for good |
| The CLI comes first: every GUI rule lives in `porter/`, and the GUI only displays it | `docs/ARCHITECTURE.md`, `tests/arch_rules.py` | Each feature below lists the porter command it needs. The GUI work is the smaller half |

---

## 1. Game Library

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| One list of every game ported on this machine: icon, name, title ID, profile status (playable/boots/wip/experimental), built version, language, build date | Every frontend opens on its library (yuzu/Eden grid, Ryujinx list, Playnite). Today a tester has to remember game folders | MEDIUM | Needs a registry in `user_dir()` (for example `library.json`: title ID → game folder, build folder, out folder, last options), written by `porter port` when it succeeds, plus a `porter library --json` that joins it with each data pack's manifest. Icon: the `icon.jpg`/PNG that `nx_extract` already writes. No scraping needed |
| An "Add game" action (pick a folder) that runs `inspect` and shows "Ready to port" before the first port | The library can't only list what already exists, or the Port tab stays the real entry point | LOW | Reuses `porter inspect --json`. The Port tab turns into the library entry's detail/run view |
| Installed state for each game on the selected device (not installed / installed vN / installed but older than the build / installed by another signer) | SideQuest and Playnite show installed state inline, and testers need to know "is this on my tablet" | MEDIUM | `pm list packages` plus `dumpsys package <pkg>` for versionName/versionCode. Porter computes this and returns it as data. Depends on Device Manager |
| An "Update available in folder" badge and a **Re-port** button | The milestone requirement. Yuzu/Eden show update versions under Add-Ons, and Playnite/Heroic show update badges | MEDIUM | `inspect` already finds every update in the folder. Compare the newest version there with the manifest's `version`. Re-port reuses the saved per-game options (see Settings) and runs with the device attached, so captured shaders get pulled |
| Two separate actions, **Uninstall from device** and **Delete build files** (with sizes), plus **Remove from library** | Lutris users complain when "remove" and "uninstall" blur together, and it leaves ghost entries. Here the three really are different (saves on device vs GBs on disk vs a list row) | LOW-MEDIUM | Uninstall from device warns that saves are deleted. Delete build files shows how much space it frees and warns that the next port starts cold (no stage cache). Remove from library leaves files alone |
| Missing folder detection | Game folders sit on external drives. A dead path has to say "folder not found, locate…" instead of crashing | LOW | Porter checks this when it builds the library list |
| Open folder / show APK in the file manager | Every frontend has "Open game location". Testers need it to send files | LOW | Already done for the Port tab output |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Compatibility at a glance: each row shows the profile's `tested` line (device and version it was verified on) and its known issues | Telling a tester "this is playable on the Y700 at v1.2.1, button icons show as ?" saves a round trip with the developer | LOW | The data is already in `android.tsv` comments and the `tested` row. Expose it through `porter profiles --json` |
| A "Built version ≠ profile's tested version" warning (derived profile) | The pipeline already prints a red line for this. Putting it in the library row stops a whole class of "it crashes" reports | LOW | The result carries `derived`. Store it in the registry |
| Launch on device | One click (`am start`) after install closes the loop without picking up the tablet | LOW | `Adb.prepare_app_files` already uses `am start -n <pkg>/android.app.NativeActivity` |
| Scan a games root folder (one subfolder per game) to fill in "Ready to port" candidates | Cemu/Ryujinx/yuzu all use "game directories" | MEDIUM | `inspect` per subfolder may be slow over many NSPs and needs keys. Run it in the background with a cache keyed on folder mtime. Move it to v1.x |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Online metadata and cover-art scraping (IGDB, SteamGridDB, title DBs) | Playnite and LaunchBox make libraries look rich | Network dependency, API keys and rate limits for a handful of testers. Also no value: the dump already carries the official icon | Use the `icon.jpg` from the dump's control data |
| Checking Nintendo's CDN or title databases for new game updates | "Tell me when an update is out" | Legally grey, fragile, and the player has to dump the update themselves anyway | Only report updates already sitting in the game folder |
| Playtime tracking, favourites, categories, tags, sorting by genre | Standard in Playnite/Lutris | The game runs on the device, so the desktop can't see playtime. With fewer than 20 games, categories are noise | Sort by name, sort by status, filter by text |
| Grid/cover-flow or a controller-navigable "big picture" view | Looks like a console | A desktop tool driven by mouse and keyboard, with a small library | A plain table/list with an icon column |

---

## 2. Device Manager

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| List every device adb sees **with its adb state** (`device`, `unauthorized`, `offline`, `no permissions`) and the fix for each | Most "it can't see my phone" reports are an `unauthorized` or Linux udev problem. Android Studio and scrcpy GUIs show the state | LOW | `adb devices -l` already runs. Map each state to one line of guidance: "Accept the USB debugging prompt on the device", "Unplug and replug", "Linux: add udev rules / plugdev group" |
| Device identity: model, serial, Android version/SDK, ABI, free storage | SideQuest/ADB managers show these. Android 10+ and arm64-v8a are hard requirements here | LOW | `getprop ro.product.model`, `ro.build.version.sdk`, `ro.product.cpu.abi`, plus the existing `free_bytes` |
| A **compatibility verdict** per device: BC textures, Vulkan ≥ 1.3, Android ≥ 10 (SDK 29), arm64-v8a, plus "enough space for this game" when a game is selected | The milestone requirement. It turns "black screen on my Mali phone" into a red cell before a 30-minute port | MEDIUM | BC: the existing `Adb.bc_textures()` (Adreno/Xclipse yes, Mali/PowerVR no, otherwise unknown). Vulkan: `pm list features` → `feature:android.hardware.vulkan.version=<N>`, which every device with a Vulkan driver must declare (AOSP). N is `VK_MAKE_API_VERSION`, `major<<22 \| minor<<12 \| patch`, so 1.3.0 = 4206592. Porter computes the verdict (the GUI shows pass/fail/unknown and the reason). Show unknown as unknown, never as pass |
| Pick the target device and remember it (`config.device`). If the remembered device is absent and exactly one other is connected, pick that one | `Adb.pick()` already follows this rule. Today the GUI has a combo box with no state | LOW | Existing setting |
| Hotplug refresh: the list updates within a few seconds when a device is plugged in, unplugged or authorized | Users expect it to "just appear", and a manual Refresh button alone feels broken | LOW-MEDIUM | Poll `porter devices --json` every 2–3 s while the window is focused (simpler than `adb track-devices`, and good enough). Give the call a timeout so a hung adb server can't freeze the UI |
| Per device: the nx2android ports installed on it, with their versions, and Install / Update / Remove for each | The milestone requirement. Same as SideQuest's "Currently installed apps" | MEDIUM | Match installed packages against the library's packages and the profiles' `package` rows (and the `org.nx2a.` prefix). Update = `porter install` with the built pack (resumable, verified). Remove = `adb uninstall` behind a saves-loss confirmation |
| Signer mismatch handled as a decision, not an error: "This device has a build signed with another key. Replace it (deletes saves) / Cancel" | `INSTALL_FAILED_UPDATE_INCOMPATIBLE` is the most likely install failure for testers who used a build from someone else | LOW | The CLI already has `--replace-signer` and a clear message. The GUI turns it into a dialog |
| Free-space check before a push | Data packs run to several GB, and a full device mid-push leaves a broken install | LOW | `free_bytes` exists. Porter refuses with a size message |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| GPU name and driver line shown raw beside the verdict (for example "Adreno (TM) 830, OpenGL ES 3.2 V@0800…") | The developer gets the exact driver without asking, which helps with next milestone's device families | LOW | Already returned by `Adb.gpu()` |
| "Collect device log" for a game: `logcat` filtered to the app's PID/tag for the last run, saved next to the GUI log | Testers can send a crash log without knowing adb | MEDIUM | `adb logcat -d --pid=$(pidof <pkg>)` loses the PID once the app has crashed. Instead grab the buffer filtered by the runtime's log tag |
| Wireless debugging (Android 11+ `adb pair` / `adb connect`) | Tablets on a stand, no cable | MEDIUM | Pairing needs a code-entry UI and mDNS quirks differ per OS. Move it to v1.x: USB works for every tester today |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Screen mirroring / remote control (embedding scrcpy) | scrcpy GUIs do it | A big native dependency per OS, and unrelated to porting | Testers who want it run scrcpy themselves |
| A general APK sideloader / installed-app browser for all apps / device file explorer | SideQuest and ADB managers have them | Scope creep, and a risk of uninstalling the wrong app | Show nx2android packages only |
| Save backup/restore | SideQuest backs up save data, and losing saves on uninstall hurts | Saves sit in internal storage. A release (non-debuggable) APK blocks `run-as`, and `adb backup` is deprecated and honours `allowBackup` | Deferred: it needs a runtime feature (copy saves to the app's external files folder on request). In v1, warn clearly before any action that deletes saves |
| Installing to several devices at once | Feels efficient | Testers have one device each. Parallel adb pushes complicate progress, cancel and the build-folder lock | One target device at a time. Switch device, then install |
| Emulator/AVD support | Developers like emulators | Android emulators don't support BC textures/Vulkan 1.3 the way the runtime needs, so it would fail confusingly | The verdict marks emulators incompatible |

---

## 3. Per-Game Settings

The model to copy is yuzu/Eden's per-game **Properties** dialog: each setting either follows the global value or overrides it, and only the overrides get stored (Dolphin's GameINI does the same thing, layered user → default → global). Here the layers are **profile default → player's per-game override**, plus global defaults for language and output folder.

Each setting should show **what changing it costs**, because the cost varies a lot in this pipeline:

| Cost class | Settings | What applying it takes |
|------------|----------|------------------------|
| Data pack only (fast: rebuild the pack, push `env.txt` and a few files) | Language, 60 fps, env switches, DLC on/off | `data` stage + data push. No NDK build |
| APK rebuild (slow: `host` + `apk` stages, NDK build) | Touch overlay layout, app name, package (side-by-side install), debug build | Re-port. Cached stages before `host` are skipped |
| Full re-port | Game version to pack (`--version`), experimental profile | Re-port from `inputs` |
| On device only, not in the desktop GUI | Overlay on/off, rumble, fps display, docked/handheld, menu button position | Already in the pause menu (`settings.txt`). Leave them there |

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| A per-game settings panel (on the library entry) for 60 fps, language (only the languages the game ships, from `control.nacp`), version to pack, include DLC, app name | Every frontend has per-game properties. Today these are CLI flags or one-off checkboxes that get forgotten | MEDIUM | Porter stores the overrides per title ID in `user_dir()`, and `porter port` reads them, so a CLI re-port matches a GUI re-port. Add the CLI side first (`porter settings <title> [key] [value] --json`, or extend `config`) |
| Settings persist and re-port reuses them | Without this, "Re-port after update" silently drops 60 fps or the language | LOW (once the store exists) | This is why the settings store has to come before Re-port |
| A "needs re-port" / "needs data update" badge after a change, plus an Apply button that runs the cheapest path that's enough | Users expect a change to take effect, and they won't guess which changes need an NDK build | MEDIUM | Porter decides the cost class (the GUI doesn't). Data-only changes need a `porter port --only data` or a `porter data` path that rebuilds and pushes the pack |
| 60 fps tells you where the cap comes from (the profile's own cap vs the FPSLocker-Warehouse config for this build) and when none exists for this version | 60 fps may silently do nothing on an unsupported build | LOW | The fps stage already knows this. Return it in `inspect --json` |
| Reset to profile defaults | yuzu/Eden's "use global" pattern. The way out after a bad experiment | LOW | Delete the override file |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| A visual touch-overlay editor: a canvas at the device's aspect ratio that draws each control from `overlay_default.tsv` plus the profile rows. Drag to move, a handle to resize. It saves `overlay <name> <x> <y> [<r>]` rows as a player override | The milestone asks for overlay layout in the UI. The data model is tiny (normalized x, y, r per control), so a drag editor is cheap compared with how much it helps | MEDIUM-HIGH | A QGraphicsScene (or the chosen toolkit's canvas) with circles and labels. Use the selected device's aspect when known, otherwise 16:10. Note that it costs an APK rebuild. Needs porter to accept player overlay rows on top of the profile's (CLI first). Keep the pause menu's runtime drag for the menu button |
| Env switches under an "Advanced" disclosure: a KEY=VALUE table showing the profile's rows (read-only, explained) and the player's extra rows, validated with the same regex `android_profile.py` uses | The developer and testers try `DM_VK_*` switches today by editing files | LOW-MEDIUM | Warn that unknown keys are passed through unchecked. Don't build a catalogue of every switch with descriptions in v1, since the switches change with the engine |
| Show the effective `env.txt` that will be written (read-only preview) | Removes guessing during debugging | LOW | Porter renders it |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Desktop mirrors of the in-game settings (rumble, fps display, overlay visibility, docked mode) | One place for everything | Two sources of truth: the device's `settings.txt` changes in game and the desktop copy goes stale | Leave them in the pause menu, and show a note pointing there |
| Graphics knobs like an emulator's (resolution scale, anisotropy, shader backend, accuracy) | Emulator users expect them | They don't exist in this runtime, and inventing them means engine work and support burden | Only the env switches the runtime really reads |
| Controller remapping in the desktop GUI | Emulators have input config pages | The device's controller drives the game. Mapping belongs in the runtime | Defer to a runtime feature |
| Global profiles / presets shared across games | Power-user convenience | With fewer than 20 games and very different engines, presets mislead | Per-game overrides plus reset-to-default |
| Editing `android.tsv` profile files from the GUI | "Let testers fix profiles" | Profiles are versioned upstream data checked by `arch_rules`. Edits would be lost on sync | Player overrides live in `user_dir()`, never in `nxnative/dm/games/` |

---

## 4. Guided First Run

The model: Cemu's "Getting started" dialog (game path plus an optional download of community packs), EmuDeck's linear wizard (disclaimer → storage → components → BIOS/keys), and the Ryujinx/Eden convention that the app never supplies keys and asks for the player's own. The wizard has to be a **view over `porter doctor --json`**, not its own state machine. Each step's done/not-done comes from porter, so the wizard resumes correctly and stays in sync with the Setup checks it replaces.

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Opens automatically when `doctor` reports a missing requirement. Linear steps with Back/Next/Skip. It can be reopened from a menu later | EmuDeck/Cemu do it, and the milestone's core value is "without help" | MEDIUM | Steps: 1 Welcome + legal (own dumps, own keys, third-party licenses) → 2 prod.keys → 3 Toolchains → 4 Device → 5 Done (offer "Add your first game"). Skipping lands in a usable app with the remaining steps shown as a banner |
| **prod.keys step**: browse, or auto-detect common locations (Ryujinx/Eden `system/` and `keys/` folders), then validate: the file parses, has the keys the pipeline needs, and reports the highest key generation present | A wrong or old prod.keys is the most common failure in Switch tooling, and it shows up later as an opaque decrypt error | MEDIUM | Needs porter validation (`porter doctor --json` or a `porter keys check <path> --json`). Never upload or copy keys anywhere. Only store the path. A game that needs a newer key generation should give a specific message at `inspect` time |
| **Toolchain step**: for each tool (NDK r27c, .NET 10 SDK, platform-tools; on Linux arm64 the community NDK and distro adb), show found/missing, version and size. One "Download all missing" button with per-file progress, cancel, resume and hash verification. "I already have it" → browse | Existing `porter tools --download` covers most of this. Testers on slow links need resume and real progress | MEDIUM | Porter: pinned hashes (hardening item), resume, disk-space check before starting (NDK unpacks to several GB). Linux arm64: if no distro adb is found, show the exact package command (`apt install adb` / `dnf install android-tools`) instead of a download |
| **Device step**: illustrated guidance (enable Developer options, USB debugging, accept the prompt), live device detection and the compatibility verdict. Skippable ("Port now, install later") | The first device is the hardest part for non-developers. Shows the `unauthorized` / udev state as it happens | LOW-MEDIUM | Reuses the Device Manager list and verdict. On Linux, show the udev hint when the state is `no permissions` |
| License acceptance recorded once | The current download dialog already says that downloading means accepting the vendors' licenses | LOW | Store the acceptance in config so the dialog doesn't come back every run |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| A "first game" step that ends with a supported game in the library and a recommended title list (the 11 playable ones) | The tester leaves the wizard knowing which of their dumps will work | LOW | `porter profiles --json` filtered to `playable` |
| Reusing an existing Android SDK/NDK or .NET install (`ANDROID_HOME`, `ANDROID_NDK_HOME`, `dotnet --list-sdks`) | Saves gigabytes for the developer and technical testers | LOW-MEDIUM | `porter/toolchain.py` already locates tools. Check that it reports the source |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Links to, or help finding, keys/firmware online | "Make it easier" | Illegal distribution. The project's legal rule says never ship keys | Point to dumping your own (Lockpick_RCM docs) with neutral wording |
| Firmware install step | Ryujinx/yuzu need firmware | This pipeline doesn't use Switch firmware. Asking for it confuses testers | Leave it out |
| A blocking wizard that can't be skipped | Ensures setup | Blocks the developer, and blocks testers who only want to look at the library | Skippable, with a persistent "Setup incomplete" banner |
| Auto-updating the app itself | Standard in public apps | Signing and notarization complexity per OS, for a few testers | Show the version, plus a "new release on GitHub" link if one is cheaply detectable (v1.x) |

---

## 5. Cross-Cutting GUI Behaviour

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Cancel stops the whole process tree on every OS, and the UI shows "Cancelling…" until children are gone | A hardening requirement. Leftover `dotnet`/`clang` processes hold the build lock and CPU | MEDIUM | Process-group kill on POSIX (`start_new_session` + `killpg`), Job Object or `taskkill /T` on Windows |
| Closing the window during a port or install asks first, then stops the run cleanly | A hardening requirement. Desktop convention | LOW | `closeEvent` |
| One long job at a time, with conflicting actions disabled (no install to a device while it's being pushed to, no settings Apply during a port of that game). A queue isn't needed | Prevents the races the build-folder lock guards against | LOW | Porter's per-build-folder lock is the real guard. The GUI just disables buttons |
| Stage progress list: each stage shows pending / running (elapsed) / cached-skipped / done / failed, with an overall bar | Already partly there. "Cached" matters, because a re-port taking 40 s vs 30 min has to look intentional | LOW | Events already include `stage`, `stage_end`, `progress` |
| Errors show the real cause in plain words, with the expandable full stderr/traceback, plus a **Copy** button | A hardening requirement. Today stderr is lost and crashes look like "no game found" | MEDIUM | Porter emits a structured `error` event (`message`, `hint`, `detail`). The GUI never interprets tracebacks |
| A persistent log per run under `user_dir()/logs/`, with "Open log folder" | Testers have to be able to send the log after the window is closed | LOW | Rotate: keep the last N runs |
| No call blocks the UI thread. Every one-shot call has a timeout and a visible busy state | A hung adb freezes today's GUI | LOW-MEDIUM | Hardening item (call timeouts) |
| Game names and paths shown as plain text, never as interpreted rich text | A hardening item (unescaped rich text) | LOW | |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **"Copy diagnostics" / "Save report"**: the app version, OS, `doctor --json`, the device info and verdict, the game's inspect result and last log tail, as one text block or zip | This is what helps a developer supporting testers from afar most. It replaces five back-and-forth messages | LOW-MEDIUM | All the pieces already exist as JSON. Strip `prod.keys` contents and leave paths out of anything shared publicly |
| An OS notification when a long port finishes or fails | Ports take tens of minutes and testers walk away | LOW | `QSystemTrayIcon.showMessage` or the toolkit's equivalent |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| A job queue / batch port of several games | "Port everything overnight" | Multiplies cancel, lock and error-reporting paths. Ports compete for CPU | One job, with a notification when it's done |
| Telemetry / crash upload | Helps the developer | Privacy, and a server to run, for a handful of known testers | Copy diagnostics |
| Themes, skins, localization of the GUI | Polish | Public-release polish is out of scope | One clean default theme following the OS light/dark mode |

---

## Feature Dependencies

```
porter registry + `porter library --json`
    └──required by──> Library list
                          ├──enhanced by──> Device installed-state column ──requires──> Device Manager (`porter devices --json` extended)
                          └──required by──> Re-port ──requires──> Per-game settings store (porter, CLI first)
                                                       └──requires──> "update in folder" detection (inspect, exists)

Device Manager (states, identity, verdict)
    ├──required by──> Install / Update / Remove per device ──requires──> saves-loss confirmation, signer-mismatch dialog
    ├──required by──> First-run Device step
    └──required by──> Copy diagnostics (device section)

Per-game settings store
    ├──required by──> Settings panel, Apply-with-cost ──requires──> porter data-only rebuild path (`port --only data` or similar)
    └──required by──> Overlay editor ──requires──> porter accepts player overlay rows (APK rebuild)

`porter doctor --json` with per-item status + prod.keys validation
    └──required by──> Guided first run (wizard is a view over doctor)
                          └──requires──> Toolchain download with progress/cancel/resume/hash (fetch hardening)

Structured `error` event + process-tree cancel + run logs (hardening)
    └──required by──> every long-running feature above (port, re-port, install, download)

Overlay editor ──conflicts──> desktop mirrors of pause-menu settings (two sources of truth; keep runtime-only settings on device)
Batch/multi-device install ──conflicts──> build-folder lock + single-job cancel model
```

### Dependency Notes

- **Re-port requires the per-game settings store.** Re-port has to reproduce the last port's options (60 fps, language, version, app name). Without a stored record it silently changes the build.
- **The library requires a porter-side registry.** Builds sit inside each game folder, and nothing central records them. If the GUI scanned folders itself, that would be pipeline logic in the GUI (an architecture violation).
- **The device installed-state column requires the Device Manager.** The library row's installed state is per device, so the device selection and the probe come first.
- **The first run requires doctor JSON with per-step status.** If the wizard kept its own state, it would drift from the real checks. Building it over `doctor` gives resume for free.
- **The hardening items (structured errors, tree cancel, timeouts, logs) come before every feature.** Each new long-running action reuses that bridge. Building features on today's bridge means doing them twice.

## MVP Definition

### Launch With (v1)

- [ ] Hardened process bridge: structured errors, process-tree cancel, close confirmation, timeouts, per-run logs. Every feature rides on it
- [ ] Porter registry + library list with status, versions, update-in-folder badge, Re-port, and the three separate remove actions
- [ ] Device manager: adb states with fixes, identity, compatibility verdict (BC, Vulkan ≥ 1.3, SDK ≥ 29, arm64, space), remembered target, polling refresh, installed ports per device, install/update/remove, signer-mismatch and saves-loss dialogs
- [ ] Per-game settings store and panel (60 fps, language, version, DLC, app name, env switches under Advanced), cost badges and Apply, reset
- [ ] Overlay layout editor (drag canvas). It's the one differentiator the milestone asks for by name. If time runs short, fall back to a numeric table over the same rows
- [ ] Guided first run over `doctor --json`: legal, prod.keys validation, toolchain downloads (resume + hash), device step, skippable with a banner
- [ ] Copy diagnostics. It's cheap and pays off at the first tester bug report

### Add After Validation (v1.x)

- [ ] Scan a games root folder for candidates. Add it when testers have more than 3–4 dumps
- [ ] Wireless debugging pairing. Add it when a tester asks for cable-free installs
- [ ] Collect device log (filtered logcat). Add it when the first runtime crash report arrives without a log
- [ ] Launch on device, OS notification on finish. Small conveniences
- [ ] A "new release" link check

### Future Consideration (v2+)

- [ ] Save backup/restore. Needs runtime support for exporting saves
- [ ] Cheat manager UI. Next milestone, runtime cheat VM first
- [ ] Multi-device-family compatibility notes (Retroid/AYN, Xclipse). Next milestone's device work

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Hardened bridge (errors, cancel, logs, timeouts) | HIGH | MEDIUM | P1 |
| Library list + registry | HIGH | MEDIUM | P1 |
| Re-port with saved options | HIGH | LOW (after store) | P1 |
| Device states + compatibility verdict | HIGH | MEDIUM | P1 |
| Install/update/remove per device + saves-loss dialogs | HIGH | MEDIUM | P1 |
| Per-game settings store + panel + cost badges | HIGH | MEDIUM | P1 |
| Guided first run (over doctor) | HIGH | MEDIUM | P1 |
| prod.keys validation | HIGH | MEDIUM | P1 |
| Copy diagnostics | HIGH | LOW | P1 |
| Overlay drag editor | MEDIUM | MEDIUM-HIGH | P1 (numeric fallback) |
| Env switches Advanced table | MEDIUM | LOW | P1 |
| Launch on device | MEDIUM | LOW | P2 |
| Collect device log | MEDIUM | MEDIUM | P2 |
| Games root scan | MEDIUM | MEDIUM | P2 |
| Wireless pairing | LOW | MEDIUM | P3 |
| OS notification | LOW | LOW | P2 |

## Competitor Feature Analysis

| Feature | Emulator frontends (yuzu/Eden, Ryujinx, Dolphin, Cemu) | Library / sideload tools (Playnite, Lutris, SideQuest) | Our Approach |
|---------|------------------|------------------|--------------|
| Library | Grid/list from scanned game dirs. Icon from the game's own metadata. Right-click → Properties / open location | Playnite/Lutris: installed status, "uninstall" vs "remove from library" (Lutris users report ghost entries when these blur) | List from a porter registry. Icon from the dump. Three separate remove actions |
| Updates | yuzu/Eden: Add-Ons tab lists installed updates/DLC. No online checks | Heroic/Playnite: store-driven update badges | "Update in folder" badge + Re-port. No online checks |
| Per-game settings | yuzu/Eden Properties: each setting "use global" or custom. Dolphin GameINI layered user > default > global, only changed keys stored. Ryujinx: right-click → per-game config | n/a | Profile default → player override, only overrides stored, with a cost badge per setting |
| First run | Ryujinx/Eden: the player supplies prod.keys (and firmware). Cemu: Getting-started dialog (game path, optional graphic-pack download). EmuDeck: linear wizard | n/a | A wizard over `doctor --json`: keys validation, toolchain downloads, device step, skippable |
| Device handling | n/a | SideQuest: device status, installed apps list, uninstall (data loss warning), backups. scrcpy GUIs: device list with adb state | adb states with fixes, compatibility verdict, nx2android packages only, saves-loss warnings. No backup in v1 |

## Sources

- Codebase (HIGH): `porter/cli.py`, `porter/adb.py`, `porter/datapack.py`, `porter/pipeline.py`, `porter/config.py`, `gui/app.py`, `nxnative/dm/android/front_android.c`, `nxnative/dm/android/overlay_default.tsv`, `nxnative/dm/android/tools/android_profile.py`, `nxnative/dm/games/010015100B514000/android.tsv`, `.planning/codebase/ARCHITECTURE.md`, `.planning/PROJECT.md`
- AOSP Vulkan implementation guide, which requires `FEATURE_VULKAN_HARDWARE_VERSION` and `..._LEVEL` (source.android.com/docs/core/graphics/implement-vulkan). PackageManager FeatureInfo (developer.android.com/reference/android/content/pm/FeatureInfo). Encoding per `VK_MAKE_API_VERSION` (MEDIUM-HIGH. Check `pm list features` on the Y700 before relying on it)
- Ryujinx/Eden key and firmware setup, per-game "Manage User Configuration": secondary guides (tech-insider.org, mintlify Ryujinx mirror) (LOW-MEDIUM)
- Dolphin GameINI layering: forums.dolphin-emu.org threads (LOW-MEDIUM)
- SideQuest installed apps / uninstall / backup: uploadvr.com, skarredghost.com, windowscentral.com (LOW-MEDIUM)
- Lutris uninstall vs remove: forums.lutris.net/t/why-its-not-possible-to-remove-games-completely-anymore/11145 (LOW)
- Cemu Getting-started dialog: copr.fedorainfracloud.org/coprs/jn64/Cemu, third-party guides (LOW-MEDIUM)
- EmuDeck wizard flow: pimylifeup.com/steam-deck-emudeck, heldgames.com (LOW)
- adb `unauthorized` handling, Linux udev: wiki.archlinux.org/title/ADB (MEDIUM)
- yuzu/Eden per-game "use global configuration" Properties dialog: training knowledge, not re-verified this session (MEDIUM)

---
*Feature research for: nx2android cross-platform GUI rework (library, device manager, per-game settings, first run)*
*Researched: 2026-10-29*
