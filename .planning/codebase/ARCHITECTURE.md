---
last_mapped_commit: 9d67edec2175ae5f4beadbd65f37eaa88105d132
last_mapped_at: 2026-10-29
---
<!-- refreshed: 2026-10-29 -->
# Architecture

**Analysis Date:** 2026-10-29

## System Overview

```text
┌──────────────────────────────────────────────────────────────────────┐
│  GUI (PySide6 desktop app)            `gui/app.py`, `gui/runner.py`   │
│  tabs: Port | Setup | Games           never imports the pipeline      │
└───────────────┬──────────────────────────────────────────────────────┘
                │ QProcess: `python -m porter <cmd> --progress json`
                │ (or `--json` for one-shot calls), stdout read as JSON lines
                ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Headless CLI / port pipeline         `porter/` (entry `porter/cli.py`)│
│  inputs → extract → fps → rewrite → shaders → captures → translator   │
│  → host → apk → icon → data → install        (`porter/pipeline.py`)   │
└───────┬─────────────────────────────────────────────┬────────────────┘
        │ subprocess: each engine tool run as          │ adb (install)
        │ `python <script.py>` (or dotnet, NDK clang) │
        ▼                                             ▼
┌──────────────────────────────────────┐   ┌──────────────────────────┐
│  Engine: `nxnative/` (git subtree)     │   │  Android device           │
│  dm/host, dm/gfx, dm/tools  (shared)   │   │  APK: libdmhost.so +      │
│  dm/android  (Android runtime, NDK,    │   │  NVN replayed on Vulkan   │
│               APK writer, shaders)     │   │  data pack in app files   │
│  dm/games/<title ID>/  (profiles)      │   └──────────────────────────┘
│  dm/third_party/  (vendored upstream)  │
└──────────────────────────────────────┘

Bundle path: `packaging/nx2android.py` is one frozen executable that is both
the GUI and the Python interpreter used for the pipeline's subprocesses.
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| GUI window and tabs | Port (pick folder, options, run, progress), Setup (tool check, downloads, settings), Games (profile list) | `gui/app.py` |
| Process bridge | Starts `porter` as a `QProcess`, parses JSON events into Qt signals, cancels the process tree | `gui/runner.py` |
| GUI entry | `python -m gui` runs `gui.app.main` | `gui/__main__.py` |
| CLI | argparse subcommands: `doctor`, `profiles`, `inspect`, `port`, `install`, `devices`, `tools`, `config` | `porter/cli.py` |
| Port pipeline | `Options` dataclass and `Port` class; one method per stage | `porter/pipeline.py` |
| Game inspection | Finds base game, updates, DLC in a folder and matches a profile | `porter/pipeline.py` (`inspect`) |
| Paths | Repo root (`REPO`, the bundle folder when frozen), per-player folder, signing key | `porter/paths.py` |
| Settings | Saved player settings (prod.keys, NDK, dotnet, adb, output, device) | `porter/config.py` |
| Toolchains | Locates NDK, .NET SDK, platform-tools per OS | `porter/toolchain.py` |
| Downloads | Fetches NDK, .NET, platform-tools from vendor URLs | `porter/fetch.py` |
| Upstream helpers | Engine-source helpers; APFS clone check (macOS only) | `porter/upstream.py` |
| Profiles | Reads game profiles, `android.tsv` keys | `porter/profiles.py` |
| Device I/O | adb wrapper, long-path handling on Windows | `porter/adb.py` |
| Data pack | Assembles the files the app reads at runtime | `porter/datapack.py` |
| FPS locker | Converts the build's FPSLocker config for `--fps60` | `porter/fpslocker.py` |
| Engine host | Horizon OS service stand-ins, NVN graphics layer | `nxnative/dm/host/`, `nxnative/dm/gfx/` |
| Android runtime | Vulkan backend, NativeActivity front end, NDK build, APK writer | `nxnative/dm/android/` |
| Rewriter and shader tools | Patch NSO code, split shaders, translate to SPIR-V | `nxnative/dm/tools/patch_nso.py`, `nxnative/dm/tools/shader_split.py`, `nxnative/dm/android/tools/shader_vk.py` |
| Game profiles | Data per title: `game.tsv`, shader tables, `patches.py`, `android.tsv` | `nxnative/dm/games/<title ID>/` |
| Bundle | PyInstaller spec and builder for the Windows zip | `packaging/nx2android.spec`, `packaging/build_bundle.py` |
| Bundle entry | Dispatches `-m module`, `script.py`, or the GUI | `packaging/nx2android.py` |
| Dev tools | Device bring-up, pushing, screen recording, soak, traces | `devtools/*.py`, `devtools/*.sh` |

## Pattern Overview

**Overall:** Headless pipeline with a thin GUI shell. The GUI and CLI share one implementation: the GUI launches the CLI as a child process and draws its JSON output. Compiled engine code is separate and driven by the pipeline through subprocesses.

**Key Characteristics:**
- The GUI holds no pipeline logic. A rule in `gui/` must not duplicate what `porter/` does (documented in `docs/ARCHITECTURE.md`).
- Process boundary as the API. Long commands print one JSON object per line (`--progress json`, events `stage`, `step`, `progress`, `stage_end`, `say`, `result`). Short commands print one JSON document (`--json`). `gui/runner.py` is the only consumer of this protocol.
- The engine (`nxnative/`) is a vendored, git-subtree copy of an upstream project and is built per port with the player's NDK. Shared core code must stay small because it is merged with `git subtree pull`.
- Data-only game profiles. A profile is compiled into the host at build time (`game_profile.h`, `android_profile.h`, generated by `nxnative/dm/android/build.py`).
- Cached stages. Slow stages (extract, rewrite, shader split, translator build, Vulkan shaders) store output keyed by their inputs and are skipped when unchanged.

## Layers

**GUI (presentation):**
- Purpose: Screens for the player: setup check, game folder, options, progress, install.
- Location: `gui/`
- Contains: `Window`, `PortTab`, `SetupTab`, `GamesTab` in `gui/app.py`; `Porter` (long process) and `call_json` (one-shot) in `gui/runner.py`.
- Depends on: PySide6; `porter.config` and `porter.paths` (imported directly for settings and `REPO`); `porter` via subprocess.
- Used by: The player, through `python -m gui` or the frozen `nx2android.exe`.

**CLI and pipeline (application):**
- Purpose: Everything the port does, runnable without a UI.
- Location: `porter/`
- Contains: `cli.py` (command dispatch in `main`), `pipeline.py` (`Port` class with stage methods `inputs`, `extract`, `fps_unlock`, `rewrite`, `shaders`, `pull_captures`, `translator`, `host`, `apk`, `icon`, `data`, `install`), support modules.
- Depends on: Standard library, `porter/paths.py`, `porter/config.py`; reuses steps of `nxnative/scripts/build_ipa_from_nsp.py` by import.
- Used by: `gui/runner.py`, and users at the command line (`python -m porter`).

**Engine core (shared, domain):**
- Purpose: Run Switch code natively: a host that stands in for Horizon OS services, and a graphics layer that replays NVN calls.
- Location: `nxnative/dm/host/`, `nxnative/dm/gfx/`, `nxnative/dm/tools/`
- Contains: `hle_*.c` service stand-ins (`hle_fs.c`, `hle_hid.c`, `hle_audren.c`, ...), NVN implementations for `gl`, `metal`, `vk`, and `nvn`, the rewriter and shader tools.
- Depends on: `nxnative/dm/third_party/` (for example `flip`, `libvpx`, `stb_vorbis`, `vulkan-headers`, and `ryujinx` for the shader translator).
- Used by: Both platforms. Platform differences are guarded by `DM_ANDROID`, `__APPLE__`, or `DM_TARGET`.

**Engine Android runtime (platform):**
- Purpose: The Android side of the engine.
- Location: `nxnative/dm/android/`
- Contains: `front_android.c` (NativeActivity front end: gamepad, pause menu, text entry, haptics, audio), `gfx_vk_*.c` (Vulkan backend), `build.py` (NDK build), `apk/mkapk.py` (APK writer), `tools/shader_vk.py`, `tools/android_profile.py`, `overlay_default.tsv`.
- Depends on: NDK (player's own), shared core in `dm/host` and `dm/gfx`.
- Used by: The port's `host` and `apk` stages.

**Game profiles (data):**
- Purpose: Everything specific to one title.
- Location: `nxnative/dm/games/<title ID>/`
- Contains: `game.tsv`, shader tables, `patches.py` (the only code allowed here), `android.tsv`.
- Depends on: Nothing; read by the pipeline and by `nxnative/dm/android/tools/android_profile.py`.
- Used by: `porter/pipeline.py` (`inputs`, `use_profile_dir`, `experimental_profile`).

**Distribution (packaging):**
- Purpose: Build the player's Windows zip.
- Location: `packaging/`
- Contains: PyInstaller spec, `build_bundle.py` (copies the git-tracked `nxnative/` next to the executable), `build_bootloader.py`, `nx2android.py` (dispatcher), `INSTALL.md`.
- Depends on: PyInstaller, PySide6, committed sources only.
- Used by: Release process.

## Data Flow

### Primary Request Path: Port a game

1. The player picks a game folder on the Port tab. `PortTab.inspect` calls `call_json(self, ['inspect', d, '--json'], ...)` (`gui/app.py`), which runs `python -m porter inspect`.
2. `porter/cli.py` `main` dispatches `inspect` to `cmd_inspect`, which calls `porter/pipeline.py` `inspect(folder)`. The result shows the status card.
3. Clicking Port runs `PortTab.start` (`gui/app.py`), which builds args (`port <folder> --progress json`, plus `--app-name`, `--language`, `--out`, `--install`, `--debug`, `--experimental`) and calls `Porter.start` (`gui/runner.py`).
4. `Porter.start` launches `sys.executable -m porter ...` as a `QProcess` in `REPO`. `Porter._out` splits stdout into lines and emits each JSON object as a Qt `event` signal.
5. `cmd_port` (`porter/cli.py`) builds `Port(Options)` and calls `run()` (`porter/pipeline.py`). Each stage prints its events; the final `result` event (`emit_result`) carries the output paths.
6. Engine tools run as child processes. `rewrite` runs `nxnative/dm/tools/patch_nso.py` with `DM_TARGET=android`; `shaders` runs `shader_split.py` then `shader_vk.py`; `host` runs `nxnative/dm/android/build.py`; `apk` runs `nxnative/dm/android/apk/mkapk.py`. Under the bundle these run through `packaging/nx2android.py` as `nx2android <script.py>`.
7. Outputs land in `<game folder>/<title ID>_build/` (`porter/paths.py` for locations). The `install` stage pushes files with `porter/adb.py`.
8. `Porter._done` reports the exit code. Cancelling kills the process tree (`taskkill /T` on Windows; `QProcess.kill` elsewhere).

### Runtime path on the device

1. The APK starts `libdmhost.so` (built from `nxnative/dm/host` and `nxnative/dm/android`), which loads the game's NSO code from the data pack.
2. Switch service calls are served by `hle_*.c` in the host. NVN calls go to the Vulkan backend `nxnative/dm/android/gfx_vk_*.c`.
3. Input and text entry go through `front_android.c`. Shaders come from `shaders.dmsv`, and captured shaders are written to `captured_shaders/` in the app's files folder.

### Setup path

1. `SetupTab` (`gui/app.py`) calls `porter doctor --json` and `porter tools --download` through `call_json` or `Porter`.
2. `porter/toolchain.py` locates tools; `porter/fetch.py` downloads them into `porter/paths.py` `player_tools()`.
3. Settings are read and written through `porter/config.py` (`config.load`, `config` command in `porter/cli.py`).

**State Management:**
- Player settings and signing key: a per-player folder from `porter/paths.py` `user_dir()` (`%APPDATA%\nx2android` on Windows, `~/Library/Application Support/nx2android` on macOS, `~/.config/nx2android` elsewhere; overridable by `NX2A_HOME`).
- GUI state lives in widget attributes (`PortTab.info`, `PortTab.result`) and is not persisted; the Port tab's last game folder is not saved.
- Pipeline state lives in the game folder's build directory and in stage caches keyed by input hashes.

## Key Abstractions

**`Port` (pipeline stage runner):**
- Purpose: Runs the port's stages in order and reports each as a JSON event.
- Examples: `porter/pipeline.py` (`class Port`, `def run`)
- Pattern: One method per stage; each stage is skipped when its cache key is unchanged.

**`Options`:**
- Purpose: Typed options for one port run.
- Examples: `porter/pipeline.py` (`class Options`)
- Pattern: Dataclass built from CLI args in `cmd_port`.

**`Porter` (GUI process bridge):**
- Purpose: Runs one long porter command and turns its stdout into Qt signals.
- Examples: `gui/runner.py` (`class Porter`)
- Pattern: `QProcess` plus `Signal(dict)` per JSON event. The GUI never parses pipeline internals beyond the event fields.

**Game profile:**
- Purpose: Per-title data (name, IDs, shader tables, Android status and settings).
- Examples: `nxnative/dm/games/010015100B514000/` (Super Mario Bros. Wonder), `porter/profiles.py`
- Pattern: Directory keyed by title ID, data files only, `patches.py` for per-build rewriter cuts.

**Engine tool invocation:**
- Purpose: Run upstream Python tools unchanged.
- Examples: `packaging/nx2android.py` (dispatch), `nxnative/dm/tools/patch_nso.py`
- Pattern: Subprocess `python <script>`; under the bundle the same executable is the interpreter.

## Entry Points

**GUI:**
- Location: `gui/__main__.py` (`python -m gui`), and `main` in `gui/app.py`
- Triggers: Player opens the app or `python -m gui`.
- Responsibilities: Creates `QApplication` (Fusion style), `Window` with three tabs.

**CLI:**
- Location: `porter/__main__.py` (`python -m porter`), `main` in `porter/cli.py`
- Triggers: Command line, or the GUI's `QProcess`.
- Responsibilities: Subcommands `doctor`, `profiles`, `inspect`, `port`, `install`, `devices`, `tools`, `config`.

**Bundle executable:**
- Location: `packaging/nx2android.py`
- Triggers: The frozen `nx2android.exe`.
- Responsibilities: `-m module` runs a module; `*.py` runs a script with its folder on `sys.path`; no arguments opens the GUI and hides the Windows console when double-clicked.

**Engine host:**
- Location: `nxnative/dm/host/entry.S`, `nxnative/dm/host/crash.c`
- Triggers: Loaded by the Android APK.
- Responsibilities: Assembly entry point and crash handler; the service stand-ins are in `nxnative/dm/host/hle_*.c`.

**Dev and probe tools (not part of the port):**
- Location: `devtools/` (for example `devtools/device.py`, `devtools/soak.sh`), `probes/` (C probes and `probes/app/mkapk.py`)
- Triggers: Run by hand against a connected device.

## Architectural Constraints

- **Threading:** The GUI runs on the Qt event loop in one thread. Long work runs in child processes (`QProcess`). The shader splitter (`nxnative/dm/tools/shader_split.py`) runs a multiprocessing pool; the bundle calls `multiprocessing.freeze_support()` in `packaging/nx2android.py`.
- **Global state:** Module-level settings in `porter/paths.py` (`REPO`, `NXNATIVE`, `DM`) computed at import time. `REPO` changes meaning when frozen (`sys.executable`'s folder).
- **Circular imports:** None observed in the sampled modules. `gui` imports `porter`; `porter` does not import `gui`.
- **Shared core must stay upstream-compatible:** Changes to `nxnative/dm/{host,gfx,tools,third_party}` are merged with `git subtree pull`. Keep diffs small and platform-guarded.
- **No game-specific code in Android runtime:** Enforced by `tests/arch_rules.py` (run by `tests/test_architecture.py`): no title IDs, game names, or per-game branches in `nxnative/dm/android/`.
- **Profiles are data:** Enforced by `tests/arch_rules.py`: only `patches.py` may hold code in a profile folder; `android.tsv` keys and status values are checked.
- **Platform:** Shipping target is Windows x64 (`packaging/build_bundle.py`, `packaging/INSTALL.md`). Code paths exist for macOS (`porter/paths.py`, `porter/toolchain.py`, `porter/fetch.py`, `porter/upstream.py` APFS clone) and Linux (XDG paths). Not verified from code whether macOS or Linux GUI runs are tested.
- **Toolchains are not bundled:** The bundle carries no NDK, .NET or adb; `porter/fetch.py` downloads them, or the player installs them.

## Anti-Patterns

### Pipeline logic in the GUI

**What happens:** `gui/app.py` `PortTab.update_port_button` decides whether Port is enabled from `info['supported']` and `info['experimental']`. The GUI also imports `porter.config` and `porter.paths` directly for settings.
**Why it's wrong:** The rule that Port is allowed is a pipeline decision duplicated in the GUI. `docs/ARCHITECTURE.md` says the GUI must not hold pipeline logic.
**Do this instead:** Have `porter inspect --json` return the allowed action, and make the GUI only display it. Settings access is acceptable as it is UI state.

### Game-specific branches in shared code

**What happens:** Per-game details have crept into comments as "found with" references, and some per-build rewrites live in `nxnative/dm/tools/sdk_patches.py`.
**Why it's wrong:** The Android runtime must be game-independent (enforced by `tests/arch_rules.py`), and the shared core is merged with upstream.
**Do this instead:** Put per-title data in `nxnative/dm/games/<title ID>/` (`android.tsv` key, `patches.py`), and keep the code generic.

### Implicit contract between GUI and CLI output

**What happens:** `gui/runner.py` `Porter._out` treats any non-JSON stdout line as a `say` event, and `PortTab.start` builds argv by hand.
**Why it's wrong:** A new CLI flag must be added in two places, and a stray print reaches the log without warning.
**Do this instead:** Add the flag in `porter/cli.py` first, then pass it from `PortTab.start`; print only through the pipeline's event output.

## Error Handling

**Strategy:** Errors are reported as JSON events in port mode and as a JSON document with an `error` key in `--json` mode. Exit codes are returned by `porter/cli.py` `main`.

**Patterns:**
- `gui/runner.py` `Porter._done` shows the last line of stderr (a traceback's last line) in red when the exit code is non-zero.
- `gui/app.py` `on_inspect` shows `error` from the inspect JSON in red on the card.
- Pipeline stages raise and the stage reports a failure event; the GUI shows it on the stage row.

## Cross-Cutting Concerns

**Logging:** Port events (`say`, `step`) to stdout as JSON in GUI mode; plain `print` in CLI mode. The GUI log is a `QPlainTextEdit` capped at 20000 blocks (`gui/app.py`).

**Validation:** Game folder checks in `porter/pipeline.py` `inputs` (title ID, version, drive space in `check_space`). Profile checks in `tests/arch_rules.py`.

**Authentication:** None for the app. The player supplies `prod.keys` from their own Switch (path in saved settings). The APK is signed with the player's key (`porter/paths.py` `signing_key`).

---

*Architecture analysis: 2026-10-29*
