# Phase 1: Bridge, Bundles and CI - Context

**Gathered:** 2026-10-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Today's GUI (`gui/app.py`'s Port, Setup and Games tabs, no new views) controls runs reliably and reaches testers as a CI-built bundle on Windows x64, macOS Apple Silicon, Linux x64 and Linux arm64. That covers: process-tree cancel and close confirmation, real errors and timeouts, saved run logs, a bundle that never writes into itself, a hashed lockfile, CI on four OSes with headless bridge tests, and a release workflow that builds, signs, notarizes and smoke-tests all four bundles.

Requirements: BRDG-01..06, PKG-01..06, CI-01..04, TEST-02, TEST-03. The new GUI views, porter hardening (HARD-*), host toolchains and the first-run wizard belong to later phases.

</domain>

<decisions>
## Implementation Decisions

### Carried forward (decided at roadmap/research, not re-asked)
- PySide6-Essentials 6.12 on every host. Floors: macOS 14, glibc 2.34 on x64, glibc 2.39 on arm64. No PySide6 6.8 fallback and no per-arch lock.
- PyInstaller, where the bundle's one executable is both the GUI and the Python that runs `-m porter` and the engine scripts. Windows ships as a zip (unsigned; testers click through SmartScreen), Linux as `.tar.gz`, macOS as a DMG holding a Developer ID-signed, notarized, stapled `.app` with no entitlements to start.
- One universal hashed lockfile from `uv pip compile --universal --generate-hashes`. Build and dev requirements are declared separately.
- CI runners: `windows-2025`, `macos-15`, `ubuntu-22.04`, `ubuntu-24.04-arm`. Never `-latest`.
- BRDG-01 is whole in this phase, including the Windows Job Object and the MSBuild node-reuse env (`MSBUILDDISABLENODEREUSE=1`, `-nodeReuse:false`, `UseSharedCompilation=false`).
- Golden JSON-lines fixtures for the bridge tests. No protocol version field; protocol changes are additive only.
- In upstream's busy files (`porter/cli.py`, `porter/pipeline.py`, `gui/app.py`), edits stay limited to hook lines, and new logic goes in new files.

### Errors, timeouts and logs
- **D-01:** Porter writes the full log of every long command (port and install, CLI runs included) to `<user dir>/logs/<time>-<command>[-<title ID>].log`. The GUI does not write logs. The path is reported in the protocol (on the `result` and `error` events, and early enough in the run that a killed or crashed run's log can still be opened).
- **D-02:** The log is readable text, not raw JSON-lines. It holds the same lines the GUI log pane shows (stage start and end with times, `say` lines, `[RED]` errors), plus porter's full traceback and the paths of the per-tool logs under `<tid>_build/logs/`. A tester can attach it as it is.
- **D-03:** Each one-shot call (`inspect`, `doctor`, `devices`, `profiles`, `tools --json`, `config`) gets its own timeout, sized to what it does. For example: `devices` 15 s (adb stalls on a bad cable), `doctor` 30 s, `inspect` 60 s (headers of a large XCI on a slow disk). At the limit the process is killed, and the view shows "porter didn't answer in N s", the last lines of stderr, and a Retry button. `call_json` keeps stderr from now on.
- **D-04:** A failed port or install shows its cause inline. The status line shows the real cause from a structured `error` event, replacing "failed after X (the log says why)". An **Open log** button opens the saved log in the system's viewer (`QDesktopServices`). The red line stays in the log pane. No modal dialog.

### Cancel and close
- **D-05:** Cancel first asks the whole tree to stop: SIGTERM to the process group on POSIX, CTRL_BREAK to the group on Windows. While it stops, the status shows "stopping…" and Cancel is greyed out. After about 5 s, whatever is left is force-killed (killpg SIGKILL, or terminating the Job Object). "cancelled" appears only after every process is gone. Today `PortTab.cancel` prints it straight away, and that changes. During the grace period porter writes which stage it was in and closes its log, then exits with 130. The adb server must survive, so it is never started inside a port's process group.
- **D-06:** Closing the window during a run asks with two buttons, **Stop and quit** and **Keep running**. Stop and quit runs the D-05 stop; the window stays open showing "stopping…" and quits by itself when the tree is gone. During an install, the dialog text adds that the app on the device may be left half-installed.
- **D-07:** The close confirmation also covers a running toolchain download (the Setup tab's own `Porter` process, `self.fetch`), using the same dialog and stop. That leaves no orphaned download writing into `toolchains/`. The download Cancel button itself stays in Phase 3 (FRUN-01).
- **D-08:** A coarse "run in progress" marker covers cut-off builds until Phase 2's per-stage stamps (HARD-05) replace it. Porter writes the marker in `<tid>_build/` when a port starts and removes it when the run ends cleanly (success or a reported error). If the next port of that game finds the marker, it says "the last port of this game was cut off" and redoes every cached stage. This works even after a SIGKILL. Write it in new porter code, with a hook line in `pipeline.py`. — **Reversibility:** reversible — Phase 2 removes it when HARD-05 lands.

### Decided during planning (2026-10-29, from RESEARCH.md open questions)
- **D-09:** On Windows, D-05's CTRL_BREAK is replaced, because PySide6 can't set `CREATE_NEW_PROCESS_GROUP` on a `QProcess`. The GUI writes `stop\n` to porter's stdin. Porter has put itself in a kill-on-close Job Object at startup (after `adb start-server`, so the adb server stays outside it). On `stop` it writes the stage it was in, closes its log, and ends the job with exit code 130. The force-kill after the grace period is a plain kill of porter, which takes the whole job down. POSIX keeps D-05 as written (new session, SIGTERM then SIGKILL to the group).
- **D-10:** Fork release tags are `v<upstream version>-ns.<n>` (for example `v0.1.2-ns.1`). The release workflow triggers only on `v*-ns.*` tags (and `workflow_dispatch`), and the assets are named `nx2android-<version>-<os>-<arch>.<ext>`, for example `nx2android-0.1.2-ns.1-macos-arm64.dmg`. — **Reversibility:** one-way (decided).
- **D-11:** The macOS bundle identifier is `io.github.namelesssaint8.nx2android`, with display name `nx2android`. — **Reversibility:** one-way (decided).

### Claude's Discretion
These areas were not discussed. Follow the research defaults, and surface any item rated one-way as a `checkpoint:decision`.
- **Release trigger:** `release.yml` runs on a `v*` tag push and on `workflow_dispatch`. It publishes a **draft** GitHub Release on the fork (NamelessSaint8/nx2android) with four assets, `nx2android-<version>-windows-x64.zip`, `-macos-arm64.dmg`, `-linux-x64.tar.gz` and `-linux-arm64.tar.gz`, and the developer publishes it by hand. Whether `ci.yml` also uploads short-lived unsigned per-push artifacts for testers is the planner's call.
- **Fork tag and version scheme:** fork tags must never clash with upstream's (upstream is at `v0.1.2`, and `git fetch upstream --tags` would collide). Pick a scheme, for example a fork suffix on upstream's version. — **Reversibility:** one-way — published tags and bundle file names are what testers download and report against, and renaming them later breaks links and the version shown in logs.
- **macOS bundle identifier and app name** in `Info.plist`. — **Reversibility:** one-way — the notarized identity, and any macOS per-app state (TCC grants, preferences) are keyed to the bundle ID.
- **Read-only bundle:** split `REPO` into a read-only resource root (`Contents/Resources` on macOS, the exe folder elsewhere) and a writable user root. Set `sys.dont_write_bytecode` / `PYTHONDONTWRITEBYTECODE=1`, and run porter with a user-folder cwd, not `REPO`. Preferred: copy `nxnative/` into `user_dir()/engine/<version>/` on first use, so the engine's and pipeline's write paths (dotnet `obj/` and others) stay untouched upstream. The `BaseIntermediateOutputPath` redirect is the alternative if research shows the copy is too slow or too large. Old engine copies get cleaned up.
- **Smoke-test depth:** CI runs `nx2android -m porter doctor --json` and an offscreen GUI start from a read-only copy of each bundle (`chmod -R a-w` on Linux, and `codesign --verify --strict` after the smoke run on macOS). The full-port check from a read-only location, and `codesign --verify --strict` after it, are manual on the developer's Mac with a real title (CI has no game files or keys). They are recorded in `docs/RELEASE_CHECK.md`.
- Log retention, for example keeping the last 30 run logs and pruning when a run starts.
- For failed one-shot calls: the card or tab shows the structured error, or stderr's last lines, never "No game found" for a crash.
- Exact timeout values and the exact grace period.
- Whether `tools --download` also writes a saved log like port and install do.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Scope and requirements
- `.planning/ROADMAP.md` §Phase 1: goal, the 18 requirement IDs, and the 5 success criteria
- `.planning/REQUIREMENTS.md`: BRDG-01..06, PKG-01..06, CI-01..04, TEST-02, TEST-03 (the exact wording)
- `.planning/PROJECT.md`: Constraints (upstream compatibility, engine subtree, architecture rule, macOS distribution, Python floors) and Key Decisions
- `.planning/STATE.md` §Blockers/Concerns: the Phase 1 research items (entitlements for frozen Python and ctypes/capstone, `sys.executable`/`REPO` inside a `.app`, PySide6 `setUnixProcessParameters` vs porter-side `setsid`, collection of the `wayland-*` plugins, .NET 10 MSBuild server env-var names) and the Apple Developer ID status

### Research (already done; do not redo)
- `.planning/research/SUMMARY.md`: the stack, phase implications and reconciled disagreements
- `.planning/research/STACK.md`: version pins, runners, the macOS signing and notarization flow, the uv lockfile
- `.planning/research/PITFALLS.md` §Pitfall 1 (bundle writes into itself), §2 (notarization and hardened runtime), §3 (process tree survives cancel), §4 (cut-off stage trusted by the cache), §5 (glibc floor), §6 (Qt on Linux: xcb-cursor, Wayland), §15 (CI secrets), §16 (reproducible builds), §17 (bundle exe is also the Python), §18 (fork and subtree mergeability), and the "Looks Done But Isn't" checklist
- `.planning/research/ARCHITECTURE.md`: `gui/runner.py` as the toolkit seam, additive protocol changes, the `cli_ext` hook pattern

### Codebase maps and rules
- `.planning/codebase/CONCERNS.md`: the known GUI bugs this phase fixes (cancel on POSIX, swallowed stderr, no `closeEvent`, no timeouts)
- `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/STACK.md`: layers and the current packaging
- `docs/ARCHITECTURE.md`: the GUI/porter boundary rule and the "Distribution" row; update it when the protocol gains the `error` event or the log path
- `tests/arch_rules.py`: the enforced layer rules (no PySide6 in `porter/`, no toolchains committed)
- `docs/RELEASE_CHECK.md`: today's Windows-only manual release check, to extend to four hosts and to the manual read-only and codesign check

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `gui/runner.py` (69 lines): `Porter` (the long command: QProcess, JSON-lines into `event`/`finished` signals) and `call_json` (one-shot). This is the only place that starts porter, so process groups, the grace-then-kill stop, stderr capture and timeouts all go here. Both of `gui/app.py`'s long processes (`PortTab.porter`, `SetupTab.fetch`) already use it, so D-05 to D-07 apply to both.
- `porter/cli.py` `_with_progress()` (lines 78-95): already maps `BuildError` → `[RED]` say and exit 1, `KeyboardInterrupt` → exit 130, and other exceptions → `[RED] Type: msg` plus a re-raise. This is the natural place for the structured `error` event, opening and closing the run log, and the SIGTERM handler.
- `porter/upstream.py` `PROG`: the progress emitter (`say`, `plan`, `close`, mode `json`). The run log can mirror what it prints.
- `porter/paths.py`: `REPO` (the exe folder when frozen, which is what makes the bundle write into itself), `user_dir()` (honours `NX2A_HOME`, so tests stay isolated), `player_tools()`.
- `packaging/nx2android.py`: the dispatcher (`-m module`, `script.py`, or the GUI). Keep its `freeze_support` and `WINEXE` handling.

### Established Patterns
- Dense one-line Python style, `[RED] ` prefix for problems, English-only logs, comments that state the why and cite the evidence (see `.claude/CLAUDE.md` Conventions).
- `--progress json` events: `stage`, `step`, `progress`, `stage_end`, `say`, `result`. Non-JSON stdout lines become `say`. An `error` event (and any log-path field) is an additive change.
- Exit code 130 means interrupted. `PortTab.on_finished` already shows "cancelled" for it.
- Tests are `unittest` under `tests/`. `NX2A_HOME` isolates the player folder.

### Integration Points
- `gui/app.py` hook lines: `PortTab.cancel` (line 174, prints "cancelled" too early), `PortTab.on_finished` (line 225, the status text and the Open log button), `PortTab.on_inspect` (line 112, the "No game found" fallback), the Setup tab's `doctor`/`tools`/`devices` callbacks, and the `Window` class (it needs a `closeEvent`).
- `porter/pipeline.py`: `self.work = o.folder / f'{tid}_build'` (line 122) and `self.logs` (line 148) are where the D-08 marker and the per-tool log paths live. Add only a hook line.
- `packaging/build_bundle.py` and `packaging/build_bootloader.py`: Windows-only today (the `is_local()` bootloader check and the zip output). They need per-OS output (zip, DMG, tar.gz) and to skip the local bootloader off Windows.
- `packaging/nx2android.spec`: one-folder, `console=True`, `collect_all` for capstone, lz4, PIL and yaml. It needs `BUNDLE()` on macOS with `nxnative/` in `Contents/Resources`, per-binary `codesign_identity`, and the Wayland/XCB plugins on Linux.
- `tests/test_porter.py`: imports the whole engine and fails without `lz4`; TEST-02 turns that into a skip.
- There is no `.github/` folder yet, so `ci.yml` and `release.yml` are new.

</code_context>

<specifics>
## Specific Ideas

- The saved log should be something a tester can attach to a GitHub issue as it is, which is why it is readable text rather than JSON (`packaging/INSTALL.md` already sends testers to Issues with "the red lines").
- When a run stops, the developer wants the GUI's state to be truthful: "stopping…" until the tree is really gone, and "cancelled" only after that.
- The developer prefers the smallest edit to upstream's `gui/app.py`: inline status and an Open log button rather than dialogs.

</specifics>

<deferred>
## Deferred Ideas

- A Cancel button for toolchain downloads (with resume): Phase 3, FRUN-01. Phase 1 only makes closing the window stop a download cleanly.
- Per-stage atomic stamps replacing the D-08 marker: Phase 2, HARD-05.

</deferred>

---

*Phase: 01-bridge-bundles-and-ci*
*Context gathered: 2026-10-29*
