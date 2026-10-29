# Architecture Research

**Domain:** Cross-platform desktop GUI over a headless Switch-to-Android porting CLI (brownfield fork of shirai91/nx2android)
**Researched:** 2026-10-29
**Confidence:** HIGH for the integration design (read straight from the code at `95b2324` and upstream's history). MEDIUM for the platform facts (Qt process flags, PyInstaller `.app` layout, MSBuild node reuse, PySide6 wheel tags), which come from official pages but went through web tools the seam rates LOW. Check them in the phase that uses them.

## Standard Architecture

The existing boundary holds. Nothing in the new features needs the GUI to import the pipeline. Each feature is **one new porter-owned record or command plus one new GUI view that draws porter's JSON**. Almost all new code goes in new files. Shared files get a few hook lines each.

### System Overview

```
┌────────────────────────────────────────────────────────────────────────────┐
│ GUI  (gui/, PySide6)                     GUI-only state: QSettings          │
│  ┌──────────┐ ┌──────────┐ ┌────────────┐ ┌───────────┐ ┌─────────────┐    │
│  │ shell.py │ │library.py│ │ devices.py │ │gamecfg.py │ │ firstrun.py │    │
│  │ nav+gate │ │ games    │ │ per device │ │ per game  │ │ wizard      │    │
│  └────┬─────┘ └────┬─────┘ └─────┬──────┘ └─────┬─────┘ └──────┬──────┘    │
│       └────────────┴──────┬──────┴──────────────┴──────────────┘           │
│                  ┌────────▼────────┐  the ONLY place that starts porter    │
│                  │ runner.py       │  Porter (events) · call_json (doc)    │
│                  │ + process group │  cancel = kill the whole tree         │
│                  └────────┬────────┘                                       │
└───────────────────────────┼────────────────────────────────────────────────┘
          argv ↓            │            ↑ stdout: JSON lines / one JSON doc
                            │              stderr: kept, shown on failure
┌───────────────────────────▼────────────────────────────────────────────────┐
│ porter/ (CLI = the single implementation)                                   │
│  cli.py ──2-line hook──► cli_ext.py (NEW: library, game, device, uninstall, │
│    │                                    setup subcommands)                  │
│    ├─ pipeline.py  Port(Options)  ◄── per-game settings fill unset options  │
│    ├─ library.py  (NEW) per-title records  ◄── written when a port finishes │
│    ├─ devices.py  (NEW) device facts + verdicts, uninstall (uses adb.py)    │
│    ├─ datapack.py env.txt / settings.txt   install.py  adb.py  toolchain.py │
└───────┬───────────────────────────────────────────────┬────────────────────┘
        │ subprocess (engine tools, dotnet, NDK clang)  │ adb
┌───────▼──────────────────────────────┐      ┌─────────▼──────────────────┐
│ nxnative/ (subtree)                   │      │ Android device             │
│ dm/android/tools/android_profile.py ◄─┼─ optional overlay hook (env var)  │
│ dm/games/<title ID>/android.tsv       │      │ files/: env.txt settings.txt│
└──────────────────────────────────────┘      │ nx2a-data.json (pushed last)│
                                              └────────────────────────────┘
Stores (all porter-owned, in user_dir()):  config.json (exists) · games/<title ID>.json (NEW)
Stores (porter-owned, beside the game):    <title ID>_build/ caches · <App>.apk · <App>-data/nx2a-data.json
```

### Component Responsibilities

| Component | Owns | New / edited | Talks to |
|-----------|------|--------------|----------|
| `gui/shell.py` | Main window, navigation, first-run gate, `closeEvent` (asks before quitting during a run, then cancels and waits) | NEW | views, `runner` |
| `gui/library.py` | Library list and game detail. Draws `porter library --json`. Buttons for port, re-port, install, uninstall | NEW | `runner` only |
| `gui/devices.py` | Device list and detail. Draws `porter device --json`, plus install, update and remove per device | NEW | `runner` only |
| `gui/gamecfg.py` | Per-game settings form, built from the schema that `porter game <id> --json` returns | NEW | `runner` only |
| `gui/firstrun.py` | Wizard for prod.keys, then tools, then device. Draws `porter setup --json` and runs `porter tools --download` | NEW | `runner` only |
| `gui/portview.py` | Stage and progress view for any event stream (port, install, tools). Its logic comes from `PortTab.on_event` | NEW | `runner` |
| `gui/runner.py` | Starts porter in its own process group, parses events, keeps stderr, applies call timeouts, cancels the tree | EDIT (small, worth sending upstream) | porter (subprocess) |
| `gui/app.py` | Upstream's three-tab GUI | **Left untouched** (see the upstream section) | — |
| `porter/cli_ext.py` | Fork subcommands (`library`, `game`, `device`, `uninstall`, `setup`) and their argparse definitions | NEW | `library`, `devices`, `toolchain`, `config` |
| `porter/library.py` | Per-title records (folder, settings, last port), the settings schema and validation, filling unset `port` options, status joins | NEW | `pipeline.inspect`, `datapack.read_manifest`, `profiles` |
| `porter/devices.py` | Device facts in one adb round trip (model, SDK, ABI, GPU, BC, Vulkan version, installed nx2a packages and versions, data-pack manifest), the compatibility verdict, uninstall | NEW | `adb.Adb` |
| `porter/cli.py` | Existing commands. Gains the hook, `--env`/`--overlay` flags, `--fps60/--no-fps60`, a structured `error` event, and the library record after a port | EDIT (about 10 lines) | everything |
| `porter/pipeline.py` | `Options` gains `env` and `overlay`. `data()` passes `o.env`. `host()` passes the overlay file | EDIT (about 4 lines) | `datapack`, engine |
| `porter/paths.py` | `NXNATIVE` can point at a writable staged copy (for a read-only bundle) | EDIT (1 to 3 lines) | — |
| `packaging/*` | Per-OS freeze, nxnative layout, archive format | EDIT `build_bundle.py` and `nx2android.spec` lightly. NEW `entitlements.plist` | CI |
| `.github/workflows/` | `ci.yml` (tests on 4 OSes), `release.yml` (4 bundles, macOS sign and notarize) | NEW | GitHub runners, Apple notary |

## Recommended Project Structure

```
gui/
├── __main__.py        # EDIT 1 line: gui.shell.main
├── app.py             # upstream's, untouched (merge signal: its diffs show new porter flags to surface)
├── runner.py          # EDIT: process group, stderr, timeouts (bridge, the toolkit seam)
├── shell.py           # NEW main window + gate + closeEvent
├── portview.py        # NEW event-stream view (port / install / tools download)
├── library.py         # NEW
├── devices.py         # NEW
├── gamecfg.py         # NEW
└── firstrun.py        # NEW
porter/
├── cli.py             # EDIT: ~10 lines (hook, flags, error event, library.record)
├── cli_ext.py         # NEW fork subcommands
├── library.py         # NEW per-title records + settings
├── devices.py         # NEW device facts / verdict / uninstall
└── (pipeline.py, paths.py: few-line edits; datapack.py, install.py: optional 1-param edits)
packaging/
├── build_bundle.py    # EDIT: is_local() Windows-only, per-OS archive, nxnative into Contents/Resources on macOS
├── nx2android.spec    # EDIT: BUNDLE(...) on darwin
├── nx2android.py      # EDIT 1 line: gui.shell; PYTHONDONTWRITEBYTECODE
└── entitlements.plist # NEW (hardened runtime)
.github/workflows/
├── ci.yml             # NEW: unittest on windows-latest, macos-14/15 (arm64), ubuntu-22.04, ubuntu-24.04-arm
└── release.yml        # NEW: 4 bundle jobs + sign/notarize + smoke test of the frozen app
tests/
├── test_bridge.py     # NEW: runner against a fake porter script (QCoreApplication)
├── test_library.py    # NEW: records, precedence, schema validation
├── test_devices.py    # NEW: parsing of canned adb output
└── test_fork_rules.py # NEW: gui/* imports nothing from porter but paths/config; no subprocess outside runner.py
docs/
└── FORK.md            # NEW: protocol additions, upstream sync checklist (ARCHITECTURE.md untouched but a link)
```

### Structure Rationale

- **New files instead of edits, measured against upstream churn.** Upstream's whole history is 113 commits in five days (2026-10-25 to 2026-10-29). In that time `porter/pipeline.py` changed in 9 commits, `install.py` in 6, `packaging/build_bundle.py` in 6, `gui/app.py` in 5, `datapack.py` in 5, `cli.py` in 4, `tests/arch_rules.py` in 4 and `docs/ARCHITECTURE.md` in 16. `gui/runner.py`, `gui/__main__.py`, `porter/config.py`, `porter/fetch.py` and `packaging/nx2android.py` changed only once each. So the fork edits the quiet files in place and adds hooks of a few lines to the busy ones. Rewriting `gui/app.py` would conflict on most syncs.
- **`gui/` keeps its name.** The spec's `collect_submodules('gui')` and the layer rules already point there.
- **Fork rules get their own test file.** `tests/arch_rules.py` changes often upstream, so the fork's rules go in `tests/test_fork_rules.py`.

## Architectural Patterns

### Pattern 1: Porter owns every record; the GUI draws verdicts

**What:** Library entries, per-game settings, device compatibility and "update available" are all computed in `porter/` and returned as JSON fields that are already decided: `update_available`, `compatible`, `reasons[]`, `needs_report`. The GUI shows them and never derives them. This also fixes the existing anti-pattern in `PortTab.update_port_button`: inspect should return `can_port`/`actions`.
**When:** Every new view.
**Trade-offs:** Each view needs a CLI command before it has data. In return, every feature works headless and can be tested without Qt, which matters because there are no GUI tests today.

### Pattern 2: Saved settings fill only what the command line left unset

**What:** This is the pattern `config.json` already uses ("command-line options win over them"), applied per title. Precedence: CLI flag, then the per-game record, then `config.json`, then the profile's `android.tsv`. `cmd_port` calls `library.fill(a)` **inside** the `_with_progress` callable, because filling needs the title ID (`nsp.scan_nsps(folder)`, cheap and key-free) and a bad folder must fail as an event, not as a traceback. The GUI never builds argv for settings. It runs `porter port <folder> --progress json`, and a CLI user gets the same port.
**Requirement:** Flags must be able to say "not set". Change `--fps60` to `argparse.BooleanOptionalAction` with `default=None`. Give `--env`/`--overlay` `action='append'` with `default=None`. `--language` and `--app-name` already use `''` for unset.

```python
# porter/cli.py cmd_port (sketch)
def go():
    library.fill(a)                      # per-game record → a.language/a.fps60/a.app_name/a.env/a.overlay where None/''
    opts = pipeline.Options(..., fps60=bool(a.fps60), env=a.env or [], overlay=a.overlay or [])
    r = pipeline.Port(opts).run(); library.record(a.folder, r); pipeline.emit_result(r)
return _with_progress(a.progress, go)
```

### Pattern 3: Route each setting to the cheapest place it takes effect

Each per-game setting reaches the device by a different path, so each needs a different amount of rework:

| Setting | Where it lands | Rebuild needed | Hook |
|---------|---------------|----------------|------|
| 60 fps | `Options.fps60` (exists): fps stage, rewriter cuts, `env.txt` rows, `fpslock.tsv` | Rewrite stage (its key includes `DM_PATCHES_EXTRA`) | none |
| Language | `Options.language` (exists), checked against the game's NACP | Data pack only (`DM_LANG` in `env.txt`) | none |
| App name | `Options.app_name` (exists) | APK and data pack (also renames the files: `app_stem`) | none |
| Env switches | `env.txt` in the data pack (read at every launch by `front_android.c` `env_file`) | Data pack only. `env.txt` is re-pushed because it is not in `KEEP_ON_DEVICE` and is MD5-verified | `datapack.build(env=self.fps_env + self.o.env)` (1 line) |
| Pause-menu defaults (`overlay`, `rumble`, `docked`, `fps`) | `settings.txt` | Data pack. **But the installer never replaces an existing `settings.txt`** (`KEEP_ON_DEVICE`) | `install --reset-settings` (1 param), or leave these to the in-game menu |
| Touch overlay layout | `android_profile.h`, compiled into `libdmhost.so` by `build.py` → `android_profile.py header` | Host (incremental, seconds) and APK | `android_profile.py` reads extra `overlay` rows from a file named in `DM_OVERLAY_EXTRA` (about 5 lines in `nxnative/dm/android`, send upstream) |

**Never route settings by writing a modified `android.tsv` copy** through `DM_GAMES_DIR` (the experimental-profile trick). `nsp.profile_files(g)` includes `android.tsv`, and the shader-split, Vulkan-shader and translator cache keys fingerprint it by content (`build_ipa_from_nsp.py` lines 1207, 1296, 1358, 1367; `pipeline.py` line 282). One overlay tweak would re-run the whole shader split, which takes minutes.

### Pattern 4: Per-title record files, not one global index

**What:** `user_dir()/games/<title ID>.json` = `{folder, out, settings:{...}, last:{version, display, package, apk, data, settings_hash, time}}`. Only porter writes these files, with the same tmp-then-replace write as `config.save`. Two ports of one title are already excluded by the planned build-folder lock, so no global file is contended. The library is `glob('games/*.json')` joined with live facts.
**Shortcut:** If the GUI edits settings while that title's port is running, the read-modify-write can race. Disable that game's settings form while it ports, and upgrade to the build-folder lock when it lands.

### Pattern 5: Process group as the cancel unit

**What:** On POSIX, start porter as a session leader and kill the whole group: `SIGTERM` to the group, a short grace period, then `SIGKILL`. Qt 6.7 added `QProcess.setUnixProcessParameters` with `UnixProcessFlag.CreateNewSession` (setsid). The fallback, if PySide6 does not bind it, is that porter calls `os.setsid()` first thing when `NX2A_SESSION=1` is set (only the GUI sets it, so terminal Ctrl+C still works). porter needs a `SIGTERM` handler that raises `KeyboardInterrupt`, so `_with_progress` closes the stage and exits with 130. The shader-split pool workers, dotnet and clang inherit the group. On Windows, keep `taskkill /T /F`. A job object with `KILL_ON_JOB_CLOSE` is the upgrade if orphans whose parent already exited show up. Pass `MSBUILDDISABLENODEREUSE=1` (or `-nodeReuse:false`) to porter's `dotnet build` calls: MSBuild otherwise keeps node processes alive for about 10 minutes by design, and on Windows they hold files in the build folder.

```python
def cancel(self):
    if not self.running(): return
    pid = self.p.processId()
    if os.name == 'nt': subprocess.run(['taskkill', '/T', '/F', '/PID', str(pid)], capture_output=True)
    else:
        os.killpg(pid, signal.SIGTERM)                       # pid == pgid: porter is the session leader
        QTimer.singleShot(5000, lambda: self.running() and os.killpg(pid, signal.SIGKILL))
```

### Pattern 6: The bridge is the toolkit seam

**What:** If research picks a toolkit other than PySide6, only `gui/runner.py` and the views change. The JSON protocol and every porter-side item above stay the same.
**Trade-off to weigh:** The bundle's one frozen executable is both the GUI and the Python that runs the engine's tools (`packaging/nx2android.py`). A non-Python GUI (Tauri, Electron, Flutter) still has to ship a frozen Python for porter, so there would be two runtimes, two signing surfaces on macOS and twice the packaging. That is a strong argument for a Python toolkit.

## Data Flow

### Request Flow (port or re-port from the library)

```
Library "Re-port" ─► runner.Porter.start(['port', folder, '--progress', 'json'])        (no settings in argv)
                         │ new process group, env PYTHONUNBUFFERED / NX2A_SESSION
                         ▼
cli.cmd_port ─► library.fill(a) ─► Options ─► Port.run() ─► stages ─► datapack(env.txt += o.env)
                         │                                        └► host(DM_OVERLAY_EXTRA) ─► android_profile.h
                         ▼
events: stage / step / progress / stage_end / say / error(NEW) / result ──► runner ──► portview
                         ▼
library.record(folder, result) ─► games/<tid>.json   ─►  GUI refreshes `porter library --json`
```

### Library and device reads (one-shot documents)

```
GUI ── call_json(['library','--json','--device',S]) ──► porter: games/*.json ⨝ inspect-lite(folder) ⨝ data-pack manifest ⨝ device packages
   ◄── [{title_id, name, status, folder_ok, packed, newest, update_available, needs_report, installed:{version, data_complete}, actions:[...]}]

GUI ── call_json(['device', S, '--json']) ──► porter.devices: ONE `adb shell` running getprop model/sdk/abi + SurfaceFlinger GLES line
                                              + `pm list features` (android.hardware.vulkan.version) + `pm list packages --show-versioncode`
                                              + cat of each installed pack's nx2a-data.json
   ◄── {serial, model, sdk, abi, gpu, bc, vulkan:"1.3.0", compatible, reasons[], apps:[{package, version_code, data_version, complete}]}
```

Vulkan 1.3 shows up as `feature:android.hardware.vulkan.version=4206592` (`(1<<22)|(3<<12)`; MEDIUM: the arithmetic is certain, the presence of the feature on every target device is not verified). The data pack is complete only when its device-side `nx2a-data.json` exists, because `install.py` pushes it last. That gives a free "install interrupted, resume" state.

### State Management

| State | Owner | Location | Written by | Read by GUI via |
|-------|-------|----------|------------|-----------------|
| Global settings (keys, NDK, dotnet, adb, out, device, language) | porter | `user_dir()/config.json` (exists) | `porter config`, first run | `porter setup --json` (direct `porter.config` import is tolerated today) |
| Library entries + per-game settings | porter | `user_dir()/games/<tid>.json` (NEW) | `port` completion, `library add/remove`, `game <tid> set` | `library --json`, `game <tid> --json` |
| What a port produced | porter | `<out>/<App>-data/nx2a-data.json`, `<tid>_build/` | port | joined into `library --json` |
| Device inventory | **nobody (live)** | the device | adb | `devices --json`, `device S --json` |
| What's installed on a device | the device | `pm` + `files/nx2a-data.json` | install / uninstall | `device S --json` |
| First-run complete | **derived** | none | — | `setup --json` → `ready` |
| Window geometry, selected view and game, column sort | GUI | `QSettings` | GUI | — |

There is no persisted device list and no "first run done" flag: both would go stale. The wizard shows whenever `setup.ready` is false.

### Key Data Flows

1. **Guided first run:** `setup --json` returns `{steps:[{id:'keys',ok,detail,fix}, {id:'tools',items:[...],downloadable}, {id:'device',...}], ready}`, composed from `toolchain.checks`, `fetch.plan`, `Adb.devices` and `config`. The keys step runs `porter config keys <path>`, then `setup --json` again. The tools step runs `tools --download --progress json` into `portview`. On Linux arm64 the tools step reports distro adb (with its install hint) and the community NDK build (needs a pinned hash in `fetch.py`). The device step covers the `unauthorized`/`no permissions` states and their fixes, then `config device <serial>`.
2. **Install, update or remove per device:** install runs `install <data> --device S --progress json` (exists). Update is a re-port if `needs_report`, otherwise an install. Remove runs `uninstall <package> --device S [--keep-data]` (NEW; `pm uninstall [-k]`). Without `-k`, Android deletes the app's saves, so the GUI confirms and porter's error text says so.
3. **Errors:** `_with_progress` emits `{"ev":"error","msg":...,"type":...,"log":<path>}` before returning 1 or re-raising. The GUI shows it in place of the `[RED]` text it sniffs out of `say` today. `call_json` passes `(obj, code, stderr_tail)` to `done`, so a crash shows its traceback line and not "no game found". Each call has its own timeout (devices 15 s, inspect 60 s), after which the call is cancelled and reported.

## Packaging and CI Layer

| Target | Runner | Freeze | Layout | Archive | Notes |
|--------|--------|--------|--------|---------|-------|
| Windows x64 | `windows-latest` | PyInstaller onedir, **bootloader compiled in CI** (`build_bootloader.py`) | `nx2android.exe` + `nxnative/` beside it (as today) | `.zip` | `is_local()` stays a Windows check |
| macOS arm64 | `macos-14`/`macos-15` (arm64) | onedir + `BUNDLE` | Executable in `Contents/MacOS`. `nxnative/` in `Contents/Resources` (PyInstaller 6 puts data there). `REPO` resolves to Resources | `.app` → codesign (hardened runtime, `entitlements.plist`, `--timestamp`) → `notarytool submit --wait` → `stapler staple` → `ditto -c -k` zip or a dmg | Secrets: Developer ID p12, App Store Connect API key. Release jobs only, never on PRs |
| Linux x64 | `ubuntu-22.04` | onedir | as Windows | `.tar.gz` (keeps the exec bits and the hard-link-friendly tree) | PySide6 6.12's x86_64 wheel needs glibc 2.34 or later |
| Linux arm64 | `ubuntu-24.04-arm` (free for public repos, GA since 2025-08) | onedir | as Windows | `.tar.gz` | PySide6 6.12's aarch64 wheel is `manylinux_2_39`: testers need glibc 2.39 or later (Ubuntu 24.04, Debian 13) |

**Required for read-only bundles (signed `.app`, and AppImage if it is ever used):** the pipeline writes into `nxnative/`. `dotnet build <src> -o <tmp>` still writes `obj/` beside each `.csproj` (`dm/tools/nx_extract`, `dm/gfx/tools/dmsh_xlate`, ryujinx's projects), and Python writes `__pycache__` beside the engine scripts. Inside a signed `.app` that breaks the seal, and under App Translocation the folder is read-only. Fix it in porter, not the engine: on first use of a bundle version, copy the bundled `nxnative/` (about 151 MB, 1,452 files) to `user_dir()/engine/<VERSION>/`, point `paths.NXNATIVE` there, and set `PYTHONDONTWRITEBYTECODE=1` in `packaging/nx2android.py`. Windows and Linux archives are writable, so for them this is only a safety measure.

**CI organization:** `ci.yml` runs on every push and PR across the 4-OS matrix: pinned `requirements.txt`, `python -m unittest discover tests`, and the bridge test under `QT_QPA_PLATFORM=offscreen`. `release.yml` runs on a tag or `workflow_dispatch`: the 4 build jobs, a mac sign-and-notarize job, then **a smoke test of each frozen artifact** (`nx2android -m porter doctor --json` and `nx2android -m porter profiles --json`, which run the bundled interpreter, the stdlib and the engine import path without toolchains). Upload with `actions/upload-artifact`, then create a release. The toolchains stay unbundled, so no job downloads NDK or .NET, except one optional job that runs `tools --json` to check that the vendor URLs and hashes still resolve.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1 developer + a few testers, dozens of games, 1-3 devices | Everything above. No database, cache or daemon |
| Many games on an HDD or network share | The `library --json` update check reads NSP headers per folder: add a `--quick` mode that compares the folder's file mtimes and sizes with the last record |
| Many devices | `device --json` per serial, called lazily when a device is selected. `devices --json` stays one cheap `adb devices -l` |

### Scaling Priorities

1. **First bottleneck:** adb round trips (about 100 ms each over USB). Batch each device's queries into one `adb shell` script.
2. **Second bottleneck:** scanning library folders on slow storage. Use the mtime and size short-circuit above.

## Anti-Patterns

### Anti-Pattern 1: The GUI builds per-game argv or computes verdicts

**What people do:** The GUI keeps fps, language and env in its own store and turns them into flags, or decides "compatible" from the GPU string.
**Why it's wrong:** A CLI port then differs from a GUI port, the same rule lives in two places (the existing `update_port_button` mistake), and none of it can be tested headless.
**Do this instead:** porter stores the settings and fills unset options (Pattern 2), and porter returns `compatible`/`reasons`/`actions`.

### Anti-Pattern 2: Per-game settings through a modified `android.tsv`

**What people do:** They reuse `DM_GAMES_DIR`/`DM_GAMES_FIRST` with a copied profile that has extra `env`/`overlay`/`setting` rows.
**Why it's wrong:** `profile_files()` fingerprints `android.tsv`, so every shader cache is invalidated.
**Do this instead:** Use the routing in Pattern 3: `env.txt` for switches, `DM_OVERLAY_EXTRA` for layout.

### Anti-Pattern 3: Rewriting upstream's busy files

**What people do:** They replace `gui/app.py` with the new GUI, refactor `pipeline.py` for the features, or rewrite `docs/ARCHITECTURE.md`.
**Why it's wrong:** Those files change several times a day upstream, so every sync becomes a conflict-resolution session.
**Do this instead:** New files, hooks of a few lines, and `docs/FORK.md`. Generic hardening fixes (stderr, the env-dict refactor, extraction safety, atomic key write, the build lock) are bug fixes upstream would benefit from. **Open them as PRs against shirai91 first** and carry them in the fork only until they merge. That is the most effective way to keep the diff small.

### Anti-Pattern 4: Persisting device state or a "setup done" flag

**What people do:** They cache the device list, or set `first_run_complete=true`.
**Why it's wrong:** Devices come and go and tools get deleted, so a cached list lies.
**Do this instead:** Query live; derive `ready` from `setup --json`.

### Anti-Pattern 5: `QProcess.kill()` as cancel on POSIX

**What people do:** They kill the direct child (today's bug).
**Why it's wrong:** dotnet, clang and pool workers keep running, holding CPU and the build folder, and the next port races them.
**Do this instead:** Process group or session, `SIGTERM` then `SIGKILL` (Pattern 5).

### Anti-Pattern 6: Versioning the GUI↔porter protocol

**What people do:** They add a protocol version and negotiation.
**Why it's wrong:** The GUI and porter always ship in one bundle, or run from one checkout, so they cannot drift apart.
**Do this instead:** Keep changes additive (new events and keys only) so upstream's `gui/app.py` keeps working, and document them in `docs/FORK.md`.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| adb (device) | `porter/adb.py` only, never from the GUI | Linux arm64 uses distro adb, whose version can lag. `pm list packages --show-versioncode` is documented only by man-page sources (LOW), so fall back to `dumpsys package <pkg> \| grep versionCode` |
| Apple notary service | `xcrun notarytool submit --wait` in `release.yml` | It notarizes the `.app`'s own signed code. Downloaded NDK and dotnet binaries are launched as separate executables, and porter's urllib downloads get no quarantine xattr. Confirm in the smoke test |
| GitHub-hosted runners | 4-OS matrix | arm64 Linux runners are free only because the repo is public (it is: `NamelessSaint8/nx2android`). Fork PRs get no secrets, so signing runs only on tags or dispatch |
| Vendor downloads, FPSLocker-Warehouse | unchanged (`fetch.py`, `fpslocker.py`) | Pinned hashes are part of hardening. The community arm64 NDK has no vendor checksum list, so its hash must be pinned |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| GUI views ↔ `gui/runner.py` | Python calls, Qt signals | Views never start processes. `test_fork_rules.py` enforces it |
| `gui/runner.py` ↔ porter | argv in. stdout carries JSON lines or one doc. stderr is kept | Additive only: `error` event, new commands |
| `porter/cli.py` ↔ `porter/cli_ext.py` | `cli_ext.add(sub)` in `_parser`, `cmds.update(cli_ext.COMMANDS)` in `main` | Two lines in a busy file. Fork commands still count as "CLI first" |
| porter ↔ engine | subprocess + env (`DM_OVERLAY_EXTRA` NEW) | The one engine hook is in `dm/android/tools/android_profile.py` (3 upstream commits, quiet). Offer it upstream |
| porter ↔ device | adb, `files/` folder | Device-side `nx2a-data.json` marks a complete pack |

## Suggested Build Order

```
A  Bridge + boundary hardening ──┬──► B  Porter data commands ──► D  New GUI (library, devices, settings) ──► E  Guided first run ──► G  4-host verification
                                 │                                    ▲                                       ▲
                                 └──► C  CI + 4 bundles of the CURRENT GUI ──────────────────────────────────┘
F  Porter hardening (upstream PRs first) ─ runs alongside B–E; the build lock must land before D's re-port button
```

1. **A. Bridge and boundary** (before anything else). `runner.py`: process-group cancel, stderr kept, timeouts. `closeEvent`. The structured `error` event. The `cli_ext` hook. `test_bridge.py`. The toolkit decision belongs here, because the bridge is the seam. *Why first:* every new view depends on dependable cancel and error reporting, and these are known bugs.
2. **B. Porter data commands** (needs A's hook). `library.py`, `devices.py`, `setup`, `uninstall`, `game` schema and set, the precedence fill, the `env.txt` and overlay hooks. All headless and fully unit-testable. *Why before D:* the views are only renderers of these documents.
3. **C. CI and bundles, shipping today's GUI first** (needs A only; runs in parallel with B). The 4-OS test matrix, then the 4 bundles, the staged writable `nxnative`, the `.app` layout, signing and notarization, and the frozen smoke tests. *Why early and separate:* this is where the long-lead risk sits (Apple account and secrets, read-only bundle writes, glibc 2.39 on arm64, the Windows bootloader). It does not depend on the new views, and once it works every later phase is tested on all 4 OSes for free.
4. **D. New GUI** (needs B; ships through C). Shell, then library and portview, then device manager, then per-game settings. Switch `gui/__main__.py` and `packaging/nx2android.py` to `gui.shell` only when the new GUI matches the old one's features.
5. **E. Guided first run** (needs B's `setup` and C's per-OS tool facts, including the Linux arm64 NDK and adb story).
6. **F. Hardening** in shared porter files (extraction safety, signing key, hashes, env dicts, atomic pack swap, chunked hashing, pins): open PRs against upstream and carry them until merged. The build-folder lock and the env-dict refactor touch `pipeline.py`. Land them before D's re-port and per-game env go live.
7. **G. Verification**: a tester on each host ports and installs a playable title with the new GUI.

**Research flags:** A needs a check that PySide6 binds `setUnixProcessParameters`/`CreateNewSession` (Qt 6.7+); if it doesn't, use the porter-side `setsid` fallback. C needs deeper research on hardened-runtime entitlements for frozen Python plus ctypes (capstone), on `REPO` and `sys.executable` inside a `.app`, and on the community arm64 NDK source and hash. For the overlay hook in B, decide whether to send it upstream or defer layout editing to presets.

## Sources

- Codebase at `95b2324`: `gui/runner.py`, `gui/app.py`, `porter/{cli,pipeline,datapack,install,config,paths,profiles,adb,toolchain}.py`, `nxnative/dm/android/{build.py,tools/android_profile.py,front_android.c}`, `nxnative/scripts/build_ipa_from_nsp.py` (`fingerprint`, `profile_files`, `build_nx_extract`), `packaging/*` (HIGH)
- `git log upstream/main` churn per file, fetched 2026-10-29 (HIGH)
- Qt 6 QProcess docs, UnixProcessFlag (`CreateNewSession` since 6.7): https://doc.qt.io/qt-6/qprocess.html, https://doc.qt.io/qt-6/qprocess-unixprocessparameters.html (official page; seam rated LOW; PySide6 binding unverified)
- PyInstaller 6.0 changelog, macOS BUNDLE relocation to Contents/Resources and Contents/Frameworks: https://pyinstaller.org/_/downloads/en/v6.0.0/epub/ (MEDIUM)
- PySide6-Essentials 6.12.0 wheel tags (manylinux_2_34_x86_64, manylinux_2_39_aarch64, macosx_14_0_universal2): https://pypi.org/pypi/PySide6-Essentials/json (official; seam LOW)
- GitHub arm64 hosted runners GA for public repos: https://github.blog/changelog/2025-08-07-arm64-hosted-runners-for-public-repositories-are-now-generally-available/ (official; seam LOW)
- MSBuild node reuse: https://github.com/dotnet/cli/issues/9458, https://github.com/dotnet/msbuild/issues/14289 (MEDIUM)
- `pm list packages --show-versioncode`: https://linuxcommandlibrary.com/man/adb-shell-pm-list (LOW)
- Android Vulkan implementation: https://source.android.com/docs/core/graphics/implement-vulkan (feature encoding from the Vulkan version macro; MEDIUM)

---
*Architecture research for: nx2android cross-platform GUI rework*
*Researched: 2026-10-29*
