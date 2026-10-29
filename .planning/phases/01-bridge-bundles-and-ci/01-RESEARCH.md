# Phase 1: Bridge, Bundles and CI - Research

**Researched:** 2026-10-29
**Domain:** Process-tree control from a PySide6 GUI, porter run logs and errors, PyInstaller bundles for four hosts (signed and notarized on macOS), GitHub Actions CI and release
**Confidence:** HIGH for the Qt, PyInstaller and lockfile mechanics (spiked locally this session); MEDIUM for Windows (Job Object code not run on Windows here) and CI runner details; LOW where marked `[ASSUMED]`

## Summary

The phase is mostly glue, with about ten small decisions. Several facts were checked this session with a local spike (PySide6-Essentials 6.12.0, PyInstaller 6.22.3, Python 3.14.5 on macOS arm64):

- PySide6 6.12 binds `QProcess.setUnixProcessParameters` and `QProcess.UnixProcessFlag.CreateNewSession`. In the spike, a QProcess started with that flag ran in its own session, and `os.killpg(pid, SIGTERM)` also killed its grandchild.
- PySide6 does **not** bind `setCreateProcessArgumentsModifier` (none of the 6.10, 6.12 or dev typesystems has `CreateProcessArguments`). It does not bind `setChildProcessModifier` either. So the GUI cannot start porter with `CREATE_NEW_PROCESS_GROUP` on Windows, and D-05's "CTRL_BREAK to the group on Windows" cannot be done as written. The recommended Windows equivalent: the GUI writes `stop\n` to porter's stdin. Porter records the stage, closes its log and calls `TerminateJobObject(job, 130)`. Porter put itself into that Job Object (`KILL_ON_JOB_CLOSE`) at startup, so the force-kill is simply `QProcess.kill()` on porter: closing the job's last handle kills every descendant.
- A PyInstaller 6.22 frozen app already has `sys.dont_write_bytecode == True` and `sys.flags.ignore_environment == 1`. The `__pycache__` worry is therefore already handled, and `PYTHON*` env vars passed to the frozen exe are ignored, which is why the spec needs its `u` and `X utf8` options.
- In a macOS `BUNDLE()` build, data files land in `Contents/Resources/<dest>`, with symlinks in `Contents/Frameworks`. `sys.executable` is `Contents/MacOS/<name>` and `sys._MEIPASS` is `Contents/Frameworks`.
- Adding any file under `Contents/Resources` after signing breaks `codesign --verify --deep --strict` ("a sealed resource is missing or invalid"). Re-signing only the outer `.app` restores it.
- `EXE(console=True)` + `BUNDLE()` writes `LSBackgroundOnly=True` (no Dock icon) unless `info_plist` overrides it.
- `BUNDLE` signing errors are only warnings unless `PYINSTALLER_STRICT_BUNDLE_CODESIGN_ERROR=1`.
- PyInstaller's Qt hook collects the `wayland-decoration-client`, `wayland-graphics-integration-client` and `wayland-shell-integration` plugins with QtGui. The 6.12 aarch64 wheel ships `platforms/libqwayland.so`, `libqxcb.so`, `libqoffscreen.so` and `wayland-shell-integration/libxdg-shell.so`.
- `uv pip compile --universal --generate-hashes --python-version 3.11` produces one hashed lock covering all four hosts, keeping `backports-zstd==1.8.0 ; python_full_version < '3.14'`.

The engine needs a writable copy. `dotnet build` writes `obj/` into `nxnative/dm/tools/nx_extract` and into the Ryujinx project folders that `dmsh_xlate` references, and neither call can be redirected without editing the subtree or `pipeline.py`. Copying the 1,452 tracked `nxnative/` files (about 151 MB on disk) into `user_dir()/engine/<engine id>/` on first use is the cheapest correct option, and CONTEXT already prefers it.

On POSIX, the adb server calls `setsid()` itself (AOSP `client/main.cpp`), so a group kill never reaches it. On Windows it is started with `DETACHED_PROCESS` only, with no job breakaway, so porter must start it with `adb start-server` *before* it joins its Job Object.

**Primary recommendation:** Put all new behaviour in two new porter modules (`porter/procs.py`: session, signals, Job Object, stop channel, detached adb server, MSBuild env; `porter/runlog.py`: run log, `log`/`error` events, the D-08 marker). Hook them with one line in `porter/cli.py` `main`, one line in `pipeline.py` `inputs()` and a small `paths.py` change. Rework `gui/runner.py` in place for stop, timeouts and stderr. Edit `gui/app.py` only at its hook points.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Starting porter, stop request, grace, force-kill, "finished only when the tree is gone" | GUI process (`gui/runner.py`) | OS (session / Job Object) | runner.py is the only place that starts porter (arch rule 5) |
| Stop handling inside the run (stage name, log close, exit 130) | porter CLI process (`porter/procs.py`) | — | Pipeline rules live in porter; the GUI only signals |
| Windows tree kill | porter (`procs.py` Job Object) | GUI `QProcess.kill()` | PySide6 can't set creation flags; the job is created from inside porter |
| adb server outside the port's group/job | porter (`procs.py`) | adb itself (`setsid` on POSIX) | Porter knows which adb and when it is needed |
| MSBuild node reuse and server off | porter env at startup | — | `Port.run` builds `self.env = dict(os.environ, …)`, so the startup env reaches every `dotnet` |
| Run log file, `log`/`error` events, retention | porter (`porter/runlog.py`) | GUI opens the file | D-01: "The GUI does not write logs" |
| Cut-off marker (D-08) | porter (`runlog.py` + hook in `pipeline.py`) | — | Build folder is porter's |
| One-shot timeouts, stderr tail, Retry | GUI (`runner.call_json` + views) | — | A pure UI concern; porter has no idea it is "hung" |
| Read-only bundle: resource root vs writable root | porter (`porter/paths.py`) | packaging (layout, ENGINE id) | Paths are porter's; packaging decides layout |
| macOS `.app`, signing, notarization, DMG | packaging + CI release job | — | Build-time only |
| Lockfile | repo root (`requirements*.in/.txt`) | CI install | Build-time only |
| Test suite on 4 OSes, bridge replay tests | CI (`.github/workflows`) + `tests/` | — | — |

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Carried forward (decided at roadmap/research, not re-asked)
- PySide6-Essentials 6.12 on every host. Floors: macOS 14, glibc 2.34 on x64, glibc 2.39 on arm64. No PySide6 6.8 fallback and no per-arch lock.
- PyInstaller, where the bundle's one executable is both the GUI and the Python that runs `-m porter` and the engine scripts. Windows ships as a zip (unsigned; testers click through SmartScreen), Linux as `.tar.gz`, macOS as a DMG holding a Developer ID-signed, notarized, stapled `.app` with no entitlements to start.
- One universal hashed lockfile from `uv pip compile --universal --generate-hashes`. Build and dev requirements are declared separately.
- CI runners: `windows-2025`, `macos-15`, `ubuntu-22.04`, `ubuntu-24.04-arm`. Never `-latest`.
- BRDG-01 is whole in this phase, including the Windows Job Object and the MSBuild node-reuse env (`MSBUILDDISABLENODEREUSE=1`, `-nodeReuse:false`, `UseSharedCompilation=false`).
- Golden JSON-lines fixtures for the bridge tests. No protocol version field; protocol changes are additive only.
- In upstream's busy files (`porter/cli.py`, `porter/pipeline.py`, `gui/app.py`), edits stay limited to hook lines, and new logic goes in new files.

#### Errors, timeouts and logs
- **D-01:** Porter writes the full log of every long command (port and install, CLI runs included) to `<user dir>/logs/<time>-<command>[-<title ID>].log`. The GUI does not write logs. The path is reported in the protocol (on the `result` and `error` events, and early enough in the run that a killed or crashed run's log can still be opened).
- **D-02:** The log is readable text, not raw JSON-lines. It holds the same lines the GUI log pane shows (stage start and end with times, `say` lines, `[RED]` errors), plus porter's full traceback and the paths of the per-tool logs under `<tid>_build/logs/`. A tester can attach it as it is.
- **D-03:** Each one-shot call (`inspect`, `doctor`, `devices`, `profiles`, `tools --json`, `config`) gets its own timeout, sized to what it does. For example: `devices` 15 s (adb stalls on a bad cable), `doctor` 30 s, `inspect` 60 s (headers of a large XCI on a slow disk). At the limit the process is killed, and the view shows "porter didn't answer in N s", the last lines of stderr, and a Retry button. `call_json` keeps stderr from now on.
- **D-04:** A failed port or install shows its cause inline. The status line shows the real cause from a structured `error` event, replacing "failed after X (the log says why)". An **Open log** button opens the saved log in the system's viewer (`QDesktopServices`). The red line stays in the log pane. No modal dialog.

#### Cancel and close
- **D-05:** Cancel first asks the whole tree to stop: SIGTERM to the process group on POSIX, CTRL_BREAK to the group on Windows. While it stops, the status shows "stopping…" and Cancel is greyed out. After about 5 s, whatever is left is force-killed (killpg SIGKILL, or terminating the Job Object). "cancelled" appears only after every process is gone. Today `PortTab.cancel` prints it straight away, and that changes. During the grace period porter writes which stage it was in and closes its log, then exits with 130. The adb server must survive, so it is never started inside a port's process group.
- **D-06:** Closing the window during a run asks with two buttons, **Stop and quit** and **Keep running**. Stop and quit runs the D-05 stop; the window stays open showing "stopping…" and quits by itself when the tree is gone. During an install, the dialog text adds that the app on the device may be left half-installed.
- **D-07:** The close confirmation also covers a running toolchain download (the Setup tab's own `Porter` process, `self.fetch`), using the same dialog and stop. That leaves no orphaned download writing into `toolchains/`. The download Cancel button itself stays in Phase 3 (FRUN-01).
- **D-08:** A coarse "run in progress" marker covers cut-off builds until Phase 2's per-stage stamps (HARD-05) replace it. Porter writes the marker in `<tid>_build/` when a port starts and removes it when the run ends cleanly (success or a reported error). If the next port of that game finds the marker, it says "the last port of this game was cut off" and redoes every cached stage. This works even after a SIGKILL. Write it in new porter code, with a hook line in `pipeline.py`. — **Reversibility:** reversible — Phase 2 removes it when HARD-05 lands.

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

### Deferred Ideas (OUT OF SCOPE)
- A Cancel button for toolchain downloads (with resume): Phase 3, FRUN-01. Phase 1 only makes closing the window stop a download cleanly.
- Per-stage atomic stamps replacing the D-08 marker: Phase 2, HARD-05.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BRDG-01 | Cancel stops every child (dotnet, MSBuild nodes, clang, shader tools) on all OSes; adb server survives | Patterns 1–3: `CreateNewSession` + `killpg` (verified), Job Object `KILL_ON_JOB_CLOSE` (cited), stdin stop on Windows (D-05 deviation), adb `start-server` before the job, MSBuild env |
| BRDG-02 | Closing the window mid-port asks; confirm stops like Cancel | Pattern 6: `Window.closeEvent` covering `PortTab.porter` and `SetupTab.fetch` |
| BRDG-03 | Real cause shown, never swallowed stderr / "no game found" | Pattern 4: `error` event from `runlog`; `--json` one-shots wrap exceptions into `{"error": …}`; `call_json` keeps stderr |
| BRDG-04 | One-shot hang → timeout message + Retry | Pattern 5: per-call `QTimer`, tree kill, `fail` argument to `done` |
| BRDG-05 | Open the full saved log of any run | Pattern 4: `log` event first, `log` on `result`/`error`, `QDesktopServices.openUrl` |
| BRDG-06 | "cancelled" only after the run has stopped | Pattern 1: `finished` gated on group-gone (POSIX) / porter exit + job close (Windows) |
| PKG-01 | Windows zip runs without Python | Existing build + per-OS `build_bundle.py`; smoke test |
| PKG-02 | macOS 14+ notarized DMG opens from Finder without warnings | Pattern 8: BUNDLE, `info_plist`, per-binary signing, outer re-sign, DMG notarize + staple |
| PKG-03 | Linux x64 tar.gz under X11 and Wayland | Pattern 9: tarball, plugin presence check, xcb libs on the build runner, glibc report |
| PKG-04 | Linux arm64 tar.gz (glibc 2.39+) under X11 and Wayland | Same; `ubuntu-24.04-arm` |
| PKG-05 | Bundle never writes into itself | Pattern 7: resource root vs writable root, engine copy, cwd = user dir; RO smoke + listing diff + `codesign --verify` |
| PKG-06 | Hashed universal lockfile; build/dev declared separately | Pattern 10: `requirements.in` → `requirements.txt`, `requirements-build.in` → `requirements-build.txt` (verified) |
| CI-01 | Tests on Windows, macOS, Linux x64, Linux arm64 per push | Pattern 11: `fork-ci.yml` matrix, offscreen, apt libs |
| CI-02 | Release builds 4 bundles, signs+notarizes macOS, smoke-tests each | Pattern 12: `fork-release.yml` |
| CI-03 | Secrets in protected env; SHA-pinned actions; PRs can't reach secrets | Pattern 12 + Security Domain; SHAs resolved this session |
| CI-04 | glibc symbol floor check; `nxnative/` diff vs upstream report | Pattern 13: `objdump -T` scan; `git diff --stat upstream/main...HEAD -- nxnative/` |
| TEST-02 | Clear skip when optional engine modules are missing | Pattern 14: module-level `unittest.SkipTest` (verified loader behaviour) |
| TEST-03 | Bridge tests replay golden JSON-lines headless | Pattern 15: `PORTER` constant in runner, `fake_porter.py`, `QT_QPA_PLATFORM=offscreen` |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Upstream compatibility:** keep diffs to shared files small; new work in new or GUI-owned files. Busy files (`porter/cli.py`, `porter/pipeline.py`, `gui/app.py`) get hook lines only.
- **Engine subtree:** no edits to `nxnative/dm/{host,gfx,tools,third_party}` in this phase (none are needed by the recommendations below).
- **Architecture:** the GUI holds no pipeline logic; every rule lives in `porter/` and reaches the GUI through JSON. A new CLI flag goes in `porter/cli.py` first. Enforced by `tests/arch_rules.py`:
  - rule 5: gui files may not import `porter.upstream|pipeline|install|datapack` or name engine tools outside string literals;
  - `gui/runner.py` must contain the literal `'-m', 'porter'` `[VERIFIED: tests/arch_rules.py:95-96]`;
  - `requirements.txt` must contain `lz4`, `capstone`, `pillow`, `pyside6` (lower-cased) `[VERIFIED: tests/arch_rules.py:132-133]`;
  - `packaging/nx2android.py` may import only `{'multiprocessing', 'os', 'runpy', 'sys', 'ctypes', 'gui'}` `[VERIFIED: tests/arch_rules.py:137]`;
  - `packaging/build_bundle.py` must contain `tracked('nxnative')` `[VERIFIED: tests/arch_rules.py:138]`;
  - `porter/paths.py` must contain `frozen` `[VERIFIED: tests/arch_rules.py:139]`;
  - `porter/` may not import PySide6/`gui`.
- **No game-specific code in the Android runtime** (not touched by this phase).
- **Toolchains not bundled** (bundles carry no NDK/.NET/adb).
- **macOS distribution:** Developer ID + notarization, hardened runtime; secrets in GitHub Actions.
- **Python:** dev 3.11+; bundles ship 3.14. Tar safety needs `filter='data'` and the CVE-2025-4517 fix (3.11.13 / 3.12.11 / 3.13.4+). The CI floor job should use a patched 3.11.
- **Legal:** never ship keys, game files or FPSLocker configs. Golden fixtures must be scrubbed of local paths and must not contain key material.
- **Conventions:**
  - dense one-line Python style, with `[RED] ` prefix for problems;
  - English-only logs; comments state the why and cite evidence;
  - `unittest` only; `NX2A_HOME` isolates the player folder in tests;
  - LF line endings; no repo-wide formatting;
  - Conventional Commits; commit only when asked;
  - update `docs/ARCHITECTURE.md` in the same commit when the protocol (`log`, `error` events) or Distribution changes; extend `docs/RELEASE_CHECK.md` to four hosts.
- **GSD workflow:** file edits happen inside GSD commands (execution phase).

## Standard Stack

### Core
| Library / Tool | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PySide6-Essentials | `==6.12.*` (6.12.0) | GUI; `QProcess.setUnixProcessParameters(CreateNewSession)` | Locked; binding verified in the spike `[VERIFIED: local import of PySide6 6.12.0]` |
| PyInstaller | `==6.22.*` (6.22.3) | One-folder bundles; `BUNDLE()` on macOS; per-binary codesign | Already used; behaviour spiked `[VERIFIED: local build with 6.22.3]` |
| pyinstaller-hooks-contrib | `2026.9` | Hooks, pinned with PyInstaller | Resolves with PyInstaller in the build lock `[VERIFIED: uv compile output]` |
| Python (bundles) | 3.14.x on CI via `actions/setup-python` | Frozen interpreter | CLAUDE.md: bundles ship 3.14 |
| uv | ≥0.11 (dev/CI tool only) | `uv pip compile --universal --generate-hashes` | Spiked with uv 0.11.32 `[VERIFIED: local run]`; STACK.md names 0.13.6 as current `[CITED: .planning/research/STACK.md]` |
| `xcrun notarytool` / `stapler`, `codesign`, `hdiutil`, `security` | Xcode on `macos-15` | Notarize, staple, sign, DMG, temp keychain | Apple's supported tools; altool is retired `[CITED: STACK.md, Apple docs]` |

### Pipeline dependencies (pin in `requirements.in`, as tested today)
`lz4==4.4.5`, `capstone==5.0.9`, `pillow==13.0.*`, `pyyaml==6.0.3`, `backports.zstd==1.8.0; python_version < "3.14"`, `PySide6-Essentials==6.12.*`. These resolved to a 326-hash universal lock in the spike `[VERIFIED: uv pip compile run this session]`.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| stdin `stop` + Job Object on Windows | CTRL_BREAK via `GenerateConsoleCtrlEvent` (D-05 text) | Needs `CREATE_NEW_PROCESS_GROUP`, which PySide6 can't set, and requires a shared console. Group id 0 would signal the GUI too `[CITED: learn.microsoft.com/windows/console/generateconsolectrlevent]` |
| Engine copy to `user_dir()/engine/<id>` | `dotnet build --artifacts-path` / `BaseIntermediateOutputPath` | Needs edits to `build_nx_extract` (subtree) and `pipeline.translator`. A global `BaseIntermediateOutputPath` collides across project references `[ASSUMED]` |
| `MSBUILDDISABLENODEREUSE` etc. in porter's env | `-nodeReuse:false` / `--disable-build-servers` arguments | The arguments need edits in `build_nx_extract` (subtree) and `pipeline.py`. The env vars reach every `dotnet` with no shared-file edit |
| Single DMG notarization | Notarize the `.app`, staple it, then build and notarize the DMG | Two submissions; only buys an offline first launch after copying the app out |
| `objdump -T` glibc scan | `auditwheel`-style tooling | `objdump` is on every Ubuntu runner; 10 lines of Python |

**Installation:**
```bash
# requirements.in (human list; replaces the unpinned requirements.txt content, PySide6 -> PySide6-Essentials)
uv pip compile requirements.in --universal --python-version 3.11 --generate-hashes -o requirements.txt
uv pip compile requirements-build.in --universal --python-version 3.11 --generate-hashes -c requirements.txt -o requirements-build.txt
python -m pip install --require-hashes -r requirements.txt                      # dev, CI tests
python -m pip install --require-hashes -r requirements.txt -r requirements-build.txt   # bundle builds
```
`requirements-dev.in` (numpy, av for devtools) is optional and can stay unlocked or be locked the same way. CONCERNS.md lists it; PKG-06 only asks that build and dev be declared separately.

## Package Legitimacy Audit

`gsd-tools query package-legitimacy check --ecosystem pypi …` returned **SUS** for every package. The reasons are the same everywhere: `too-new` (the latest *release* is recent) and `unknown-downloads` (PyPI publishes no download counts). None returned SLOP, and none has a postinstall concept (PyPI). Every package except `uv` is already in the project's dependency tree today (`PySide6` pulls in `PySide6-Essentials` and `shiboken6`; `pyinstaller` pulls in `pyinstaller-hooks-contrib`).

| Package | Registry | Latest release | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| PySide6-Essentials | PyPI | 6.12.0 (2026-10-08) | n/a | pyside.org (Qt) | SUS (too-new, unknown-downloads) | Approved: already a transitive dep of `PySide6`; human-verify the lock diff |
| shiboken6 | PyPI | 6.12.0 | n/a | Qt | SUS | Approved (transitive) |
| pyinstaller | PyPI | 6.22.3 | n/a | github.com/pyinstaller/pyinstaller | SUS (unknown-downloads) | Approved (already used) |
| pyinstaller-hooks-contrib | PyPI | 2026.9 (2026-10-20) | n/a | github.com/pyinstaller/pyinstaller-hooks-contrib | SUS | Approved (transitive of pyinstaller) |
| uv | PyPI | 2026-10-27 | n/a | pypi.org/project/uv | SUS | Approved as a dev-only tool, never shipped |
| capstone, lz4, pillow, pyyaml, backports.zstd | PyPI | — | n/a | — | SUS (unknown-downloads / too-new) | Approved (existing deps, now pinned) |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** all of the above, for registry-metadata reasons only. The planner adds **one** `checkpoint:human-verify` on the generated `requirements.txt` / `requirements-build.txt` diff (names and versions match `requirements.in`), not one per package.

## Architecture Patterns

### System Architecture Diagram

```
 Cancel / window close / one-shot timeout
            │
 ┌──────────▼──────────────────────────────────────────────────────────┐
 │ GUI (gui/app.py hooks → gui/runner.py)                              │
 │  Porter.start(args) ──QProcess(sys.executable, '-m','porter',…)─────┼──► porter (new session on POSIX)
 │  cwd = user_dir(); env NX2A_GUI=1 (+PYTHONPATH=REPO when not frozen)│        │
 │  stop(): POSIX killpg(pgid,SIGTERM) │ Windows write "stop\n"        │        │ cli.main → runlog.run(a, cmd)
 │  +5 s: POSIX killpg SIGKILL │ Windows QProcess.kill()               │        │   procs.setup(a):
 │  finished(code) only when POSIX group empty / Windows porter exited │        │     adb start-server (detached) if adb used
 │  call_json(args, done, timeout): kill tree at limit, keep stderr    │        │     Windows: join Job Object (KILL_ON_JOB_CLOSE)
 └───────▲───────────────────────────────▲─────────────────────────────┘        │     POSIX: SIGTERM → KeyboardInterrupt
         │ stdout: JSON lines            │ stdout: one JSON doc               │     MSBuild env; stdin watcher
         │ {"ev":"log","path"} first     │ {"error":…} on any exception       │   runlog: <user dir>/logs/<time>-<cmd>.log
         │ stage/step/progress/say/…     │ stderr: traceback (kept)           │     mirrors PROG events as text
         │ {"ev":"error","msg","log"}    │                                    │   pipeline.inputs(): runlog.build_folder(work)
         │ {"ev":"result",…,"log"}       │                                    │     marker <tid>_build/.port-running
         │                               │                                    ▼
         │                               │                      children: dotnet (→MSBuild nodes), nx2android script.py
         │                               │                      (rewriter, shader split pool), NDK clang, adb client
         └───────────────────────────────┴──────────  all in porter's group / job; adb server is not
```

### Recommended file layout (new files marked NEW)
```
porter/
├── procs.py        # NEW: setup(a) for every porter run: SIGTERM handler, Job Object, stdin stop watcher, adb server outside the tree, MSBuild env
├── runlog.py       # NEW: run(a, fn): log file, `log`/`error` events, `--json` error docs, retention, D-08 marker (build_folder(work))
├── paths.py        # EDIT (quiet file): resource root vs writable engine copy
├── cli.py          # EDIT: 1 hook line in main()
└── pipeline.py     # EDIT: 1 hook line at the end of inputs()
gui/
├── runner.py       # EDIT (quiet file): PORTER constant, session, stop/grace/force, finished gating, call_json timeout + stderr
└── app.py          # EDIT: hook lines: cancel, on_event (log/error), on_finished, on_inspect + other call_json callbacks, Window.closeEvent
packaging/
├── nx2android.spec # EDIT: BUNDLE() on darwin, codesign_identity from env, info_plist
├── build_bundle.py # EDIT: per-OS layout and archive, is_local() only on Windows, ENGINE id, exclude dmsh_xlate_bin
├── smoke_gui.py    # NEW: run by the frozen exe: imports engine deps, starts Window offscreen, waits for profiles
└── glibc_floor.py  # NEW: newest GLIBC_ version any ELF in a bundle needs
requirements.in / requirements.txt (generated) / requirements-build.in / requirements-build.txt (generated)
.github/workflows/fork-ci.yml, fork-release.yml   # NEW (fork-prefixed names cannot collide with a future upstream ci.yml)
tests/test_bridge.py, tests/test_runlog.py, tests/test_workflows.py, tests/fixtures/bridge/*.jsonl + fake_porter.py  # NEW
```

### Pattern 1: Stop protocol (BRDG-01, BRDG-06, D-05)

**POSIX (verified mechanics):**
- The GUI starts porter with `CreateNewSession` and records `pgid = processId()` on `started`.
- `stop()` sends `os.killpg(pgid, SIGTERM)` and starts a 5 s timer. Porter's SIGTERM handler raises `KeyboardInterrupt`. The existing `_with_progress` turns that into `PROG.close(ok=False)`, `[RED] interrupted` and return code 130 `[VERIFIED: porter/cli.py:86-87]`. Upstream `run()` already terminates its direct child on `KeyboardInterrupt` `[VERIFIED: nxnative/scripts/build_ipa_from_nsp.py:330-331]`, and every other descendant got the group SIGTERM directly.
- When the timer fires, if the group is still alive (`os.killpg(pgid, 0)` succeeds), send SIGKILL.
- `finished` is emitted only once porter has exited **and** `killpg(pgid, 0)` raises `ProcessLookupError`. Poll every 200 ms after porter's own exit.

**Windows (the D-05 deviation):**
- PySide6 can't pass `CREATE_NEW_PROCESS_GROUP`: there is no `setCreateProcessArgumentsModifier` binding `[VERIFIED: pyside-setup typesystem_core_common.xml (6.10, 6.12, dev) — QProcess entry has only `UnixProcessFlag`/`UnixProcessParameters` under `<?if !windows?>`]`. And `GenerateConsoleCtrlEvent(CTRL_BREAK_EVENT, pid)` only targets a group created that way `[CITED: Microsoft Learn GenerateConsoleCtrlEvent]`.
- So the GUI writes `b'stop\n'` to porter's stdin. Porter's watcher thread (an `os.read(0, …)` loop, not `sys.stdin`; see Pitfall 4) runs `runlog.cut_off()`, which records the current stage and closes the log, then calls `TerminateJobObject(job, 130)`. That kills porter and every descendant with exit code 130.
- The force path is `QProcess.kill()` on porter: `TerminateProcess` closes porter's handle to the job, and `KILL_ON_JOB_CLOSE` "terminates all associated processes" `[CITED: learn.microsoft.com/windows/win32/procthread/job-objects]`.
- The same watcher treats EOF (the GUI died) as `stop` on both OSes. That is a free GUI-crash watchdog.

**Planner:** surface the Windows deviation as a `checkpoint:decision`. The recommended option is the stdin `stop` + Job Object. The alternative is "accept force-kill only on Windows (no grace)".

### Pattern 2: Windows Job Object created by porter itself
- At startup (GUI runs only, `NX2A_GUI=1`), after starting the adb server, porter calls `CreateJobObjectW`, then `SetInformationJobObject(JobObjectExtendedLimitInformation=9, LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE (0x00002000))`, then `AssignProcessToJobObject(job, GetCurrentProcess())`.
- **Do not set `JOB_OBJECT_LIMIT_BREAKAWAY_OK` (0x800)**, so no descendant can opt out `[CITED: learn.microsoft.com JOBOBJECT_BASIC_LIMIT_INFORMATION]`.
- Children are associated with the job automatically `[CITED: job-objects page]`.
- Nested jobs work on Windows 8+, so this also works when the GUI itself runs inside a job (a terminal, the CI runner) `[CITED: job-objects page]`.
- If assignment fails, keep running, log it, and the GUI falls back to `taskkill /T /F` (today's behaviour).

### Pattern 3: adb server outside the tree; MSBuild env
- **adb:** POSIX adb servers call `setsid()` themselves when started as a daemon `[VERIFIED: AOSP packages/modules/adb client/main.cpp:175-185 "Start a new session for the daemon … setsid()"]`. On Windows the server is created with `DETACHED_PROCESS` and no breakaway flag `[VERIFIED: AOSP adb.cpp:940-950]`, so it would join porter's job and die with it.
  - `procs.setup` runs `[adb, 'start-server']` (stdio `DEVNULL`, `start_new_session=True` on POSIX for older adbs, timeout 30 s) **before** joining the job, for `devices`, `install` and `port --install`. Find the adb with `toolchain.find_adb(config.load())`.
  - The GUI's startup `devices` call normally has the server up long before any install.
- **MSBuild:** set in `os.environ` at porter startup: `MSBUILDDISABLENODEREUSE=1`, `DOTNET_CLI_USE_MSBUILD_SERVER=0`, `UseSharedCompilation=false`. `Port.run` builds `self.env = dict(os.environ, …)` `[VERIFIED: porter/pipeline.py:95]`, so every `dotnet build` and `dotnet <dll>` inherits them. No edit to `build_nx_extract` (subtree) or `translator()`.
  - The MSBuild server is off by default before the .NET 11 SDK, and `DOTNET_CLI_USE_MSBUILD_SERVER=false` disables it `[CITED: learn.microsoft.com/visualstudio/msbuild/msbuild-server]`.
  - `MSBUILDDISABLENODEREUSE=1` is the env form of `/nr:false` `[CITED: secondary: Ed-Fi docs, WebKit bug; MSBuild repo not checked]`.
  - `UseSharedCompilation` as an env-derived MSBuild property `[ASSUMED]`.
  - Skip the `-nodeReuse:false` argument: the env var covers it. Note it in the plan as "env-equivalent" against the carried-forward decision text.

### Pattern 4: Run log, `log` and `error` events (BRDG-03, BRDG-05, D-01, D-02)

Hook (one line): `porter/cli.py` `main` ends with `return runlog.run(a, {…}[a.cmd])` in place of `return {…}[a.cmd](a)`.

`runlog.run(a, fn)`:
1. `procs.setup(a)`.
2. For long commands (`port`, `install`, `tools --download`):
   - prune `logs/` to the newest 29;
   - open `<user dir>/logs/<YYYYmmdd-HHMMSS>-<cmd>.log` (UTF-8);
   - if `a.progress == 'json'`, print `{"ev":"log","path":…}` as the **first** stdout line;
   - wrap the upstream `PROG` instance's `_json` and `_out` so every event is also written to the log as text: stage start `[hh:mm:ss] [k/n] name · step`, stage_end `✓/✗ [k/n] name (m:ss): summary`, `say` lines verbatim, `result` paths, no `progress` noise. The wrapped `_json` also adds `"log"` to the `result` event, and remembers the last `[RED] ` message.
3. Call `fn(a)`:
   - return 1 (a `BuildError` caught by `_with_progress`): emit `{"ev":"error","msg":<last [RED] text>,"type":"BuildError","log":path}`, write it, and remove the D-08 marker;
   - an uncaught exception (re-raised by `_with_progress` `[VERIFIED: porter/cli.py:88-91]`): write `traceback.format_exc()` to the log, emit `error` with `type` = the exception class name, remove the marker, re-raise (stderr traceback and exit code unchanged);
   - 130: log "cancelled during <stage>" and keep the marker;
   - 0: remove the marker.
4. Append the per-tool log folder (`<tid>_build/logs`, recorded by `build_folder`) to the log.
5. For one-shot `--json` commands, catch any exception, print `{"error": "<Type>: <msg>"}` to stdout, keep the traceback on stderr, and exit 1. Today a missing `lz4` makes `tools --json` look like a network failure (CONCERNS.md).

`[-<title ID>]` in the file name is optional per D-01's brackets. The title ID is only known after `inputs()`, and renaming an open file fails on Windows, so record the title ID inside the log instead.

### Pattern 5: One-shot timeouts (BRDG-04, D-03)
- `call_json(parent, args, done, timeout)` starts a single-shot `QTimer`. At the limit it kills the tree (POSIX `killpg(SIGKILL)`, since one-shots also get `CreateNewSession`; Windows `p.kill()`, and the job takes the children).
- On `finished` it reads stdout and stderr and calls `done(obj, code, fail)`. `fail` is `None` on success, otherwise `{'timeout': N or 0, 'stderr': last 8 lines}`.
- Recommended limits: `devices` 15 s, `doctor` 30 s, `inspect` 60 s, `profiles` 20 s, `tools --json` 60 s (network). `config` is not a porter call from the GUI: `gui/app.py` uses `porter.config` directly.
- Each callback in `gui/app.py` shows a red line: "porter didn't answer in N s" or the stderr tail, plus a `<a href="retry">Retry</a>` link (`QLabel.linkActivated`). That is the smallest Retry UI.
- Also handle `QProcess.errorOccurred(FailedToStart)`, which emits no `finished` (Pitfall 6).

### Pattern 6: Close confirmation (BRDG-02, D-06, D-07)
- `Window.closeEvent(e)`: if `self.port.porter.running()` or `self.setup.fetch.running()`, show a `QMessageBox` with the custom buttons **Stop and quit** (`DestructiveRole`) and **Keep running** (`RejectRole`). If an install is running (`PortTab` remembers `args[0] == 'install'` or `'--install' in args`), add the "may be left half-installed" sentence.
- On Stop: `e.ignore()`, set `self.quitting = True`, call `stop()` on each running `Porter`, and show "stopping…". Each Porter's `finished` handler calls `self.close()` again once nothing runs.

### Pattern 7: Read-only bundle (PKG-05)
- `porter/paths.py` today: `REPO = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent.parent`, `NXNATIVE = REPO / 'nxnative'` `[VERIFIED: porter/paths.py:5-6]`.
- New behaviour:
  - frozen + `darwin`: `REPO = Path(sys.executable).parent.parent / 'Resources'`. In the spike, `sys.executable` was `…/hello.app/Contents/MacOS/hello` and datas landed in `Contents/Resources` `[VERIFIED: local BUNDLE spike]`.
  - other frozen: `REPO = Path(sys.executable).parent`.
  - frozen: `NXNATIVE = _engine()`, which copies `REPO/'nxnative'` to `user_dir()/'engine'/<id>/nxnative` once. It copies to `<id>.tmp-<pid>`, then `os.rename` (the loser of a race deletes its temp; the GUI starts three porter one-shots at once on launch), then prunes other `engine/*`. `<id>` comes from a file `build_bundle.py` writes into the resource root (`ENGINE`: the first 16 hex of sha256 over the copied paths and bytes; this catches dirty trees, which `git rev-parse HEAD:nxnative` would not).
  - not frozen: unchanged (developers may write into the checkout).
- Bytecode: already off in frozen apps (`sys.dont_write_bytecode` True `[VERIFIED: spike]`). An explicit `sys.dont_write_bytecode = True` in `packaging/nx2android.py` is harmless and documents intent; it adds no import, so arch rule 10b passes. `PYTHONDONTWRITEBYTECODE` in the env does nothing for the frozen exe (`ignore_environment=1` `[VERIFIED: spike]`).
- cwd: `runner` uses `paths.user_dir()`. When not frozen it must add `PYTHONPATH=<checkout>`, because `python -m porter` found `porter` through cwd = REPO `[VERIFIED: gui/runner.py:30-31]`.
- `dmsh_xlate_bin/` (64 tracked files, one Mach-O, not used by the Android port) is excluded from every bundle in `build_bundle.py`.

### Pattern 8: macOS `.app`, signing and notarization (PKG-02)
- Spec (darwin only):
```python
exe = EXE(..., console=True, upx=False, codesign_identity=os.environ.get('MACOS_SIGN_IDENTITY'), entitlements_file=None)
coll = COLLECT(...)
if sys.platform == 'darwin':
    app = BUNDLE(coll, name='nx2android.app', bundle_identifier=BUNDLE_ID, version=VERSION,
                 info_plist={'LSBackgroundOnly': False, 'NSHighResolutionCapable': True, 'LSMinimumSystemVersion': '14.0'})
```
  - `LSBackgroundOnly: False` is required: with `console=True`, PyInstaller writes `True`, which hides the Dock icon, and `info_plist` overrides it `[VERIFIED: PyInstaller 6.22.3 building/osx.py:638-648]`.
  - With an identity, PyInstaller signs with `codesign -s ID --force --all-architectures --timestamp --options=runtime` `[VERIFIED: PyInstaller utils/osx.py:413-431]`.
  - Set `PYINSTALLER_STRICT_BUNDLE_CODESIGN_ERROR=1` in CI, or BUNDLE signing failures are only warnings `[VERIFIED: building/osx.py:714-720]`.
- `build_bundle.py` (darwin) copies `nxnative/` (tracked, minus `dmsh_xlate_bin/`), `VERSION` and `ENGINE` into `nx2android.app/Contents/Resources/`. That breaks the seal (verified), so it then re-signs only the outer bundle: `codesign --force --options runtime --timestamp --sign "$MACOS_SIGN_IDENTITY" nx2android.app`, ad-hoc `-` locally. Verify with `codesign --verify --deep --strict --verbose=2`.
- DMG staging: the `.app`, a symlink to `/Applications`, and `INSTALL.md`. Then:
  1. `hdiutil create -volname nx2android -srcfolder stage -ov -format UDZO out.dmg`
  2. `codesign --sign "$ID" --timestamp out.dmg`
  3. `xcrun notarytool submit out.dmg --key "$RUNNER_TEMP/key.p8" --key-id "$APPLE_API_KEY_ID" --issuer "$APPLE_API_ISSUER_ID" --wait --timeout 30m` (on failure, `notarytool log <id>`)
  4. `xcrun stapler staple out.dmg`
  5. `spctl -a -t open --context context:primary-signature -v out.dmg` `[CITED: STACK.md recipe]`
- Entitlements: none to start (locked). The signed-build smoke run (Pattern 12) imports capstone/lz4/PIL/yaml and runs a capstone disassembly under the hardened runtime, which settles empirically whether `allow-unsigned-executable-memory` is ever needed.
- Info.plist TCC purpose strings (`NSDocumentsFolderUsageDescription`, `NSDownloadsFolderUsageDescription`, `NSDesktopFolderUsageDescription`, `NSRemovableVolumesUsageDescription`, `NSNetworkVolumesUsageDescription`) are cheap to add now (Pitfall 9 of PITFALLS.md) `[ASSUMED: macOS shows a generic prompt without them]`.

### Pattern 9: Linux tarballs (PKG-03, PKG-04)
- `tar -C dist -czf nx2android-<v>-linux-<arch>.tar.gz nx2android`. Never zip on Linux or macOS: zip loses PyInstaller 6's symlinks `[CITED: STACK.md]`.
- PyInstaller's Linux excludes cover libGL/libEGL/libdrm/libxcb/libwayland-* but **not** libxcb-cursor, libxkbcommon(-x11), libfontconfig, libfreetype, libglib, libX11 `[VERIFIED: PyInstaller depend/dylib.py _unix_excludes]`. Those are collected from the build runner if present. Install them on the build runner (`libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xkb1 libxkbcommon-x11-0 libegl1 libgl1 libfontconfig1 libdbus-1-3`) so testers don't need `libxcb-cursor0`. List the libGL/EGL/xcb/wayland ones as tester prerequisites in INSTALL.md.
- `libQt6Gui.so.6` needs libEGL, libX11, libglib-2.0, libxkbcommon, libGL, libz, libfreetype, libfontconfig even for offscreen. `libQt6XcbQpa.so.6` needs the libxcb-* set including `libxcb-cursor.so.0` `[VERIFIED: objdump -p on the 6.12.0 aarch64 wheel]`.
- CI checks that `_internal/PySide6/Qt/plugins/platforms/libqwayland.so`, `libqxcb.so` and `wayland-shell-integration/libxdg-shell.so` exist in the bundle. Real X11/Wayland starts are manual (tester or VM) and recorded in RELEASE_CHECK.md. An optional CI `xvfb-run` xcb start catches missing xcb libs.

### Pattern 10: Lockfile (PKG-06)
- See Installation. `requirements.txt` becomes the generated file, which keeps `pip install -r requirements.txt` in README/INSTALL working and still satisfies arch rule `requirements.txt has … pyside6` (`pyside6-essentials` contains it).
- Upstream edited `requirements.txt` in only 2 commits (`git log upstream/main -- requirements.txt`), so a conflict is rare. When upstream adds a dependency, re-run the compile.

### Pattern 11: CI workflow (CI-01)
- `fork-ci.yml` triggers on `push` and `pull_request` (never `pull_request_target`), with `permissions: contents: read`.
- Matrix: `windows-2025`, `macos-15`, `ubuntu-22.04`, `ubuntu-24.04-arm` on Python 3.14, plus `ubuntu-22.04` on 3.11 (the floor; setup-python's newest 3.11 is past 3.11.13).
- `env: QT_QPA_PLATFORM=offscreen`. On Linux, `apt-get install libegl1 libgl1 libxkbcommon0 libfontconfig1 libglib2.0-0 libdbus-1-3`.
- Install with `pip install --require-hashes -r requirements.txt`, then run `python -m unittest discover -v tests`.

### Pattern 12: Release workflow (CI-02, CI-03)
- `fork-release.yml` triggers on `push: tags: ['v*-ns.*']` (see the tag decision) and `workflow_dispatch`. Top level: `permissions: contents: read`.
- Jobs:
  - `build` (matrix: windows-2025 → windows-x64; ubuntu-22.04 → linux-x64; ubuntu-24.04-arm → linux-arm64). Steps: checkout with `fetch-depth: 0` and `persist-credentials: false`; setup-python 3.14; apt libs (Linux); `pip install --require-hashes -r requirements.txt -r requirements-build.txt`; `python packaging/build_bootloader.py` (Windows only); `python packaging/build_bundle.py`; smoke; `glibc_floor.py` (Linux); upload the archive.
  - `macos` with `environment: release`: temp keychain (`security create-keychain`, `set-keychain-settings -lut 21600`, `unlock-keychain`, `import … -A -t cert -f pkcs12`, `set-key-partition-list -S apple-tool:,apple:`, `list-keychain -d user -s`) `[CITED: GitHub docs "sign-xcode-applications" via STACK.md]`; build with `MACOS_SIGN_IDENTITY` and `PYINSTALLER_STRICT_BUNDLE_CODESIGN_ERROR=1`; re-sign the outer bundle; DMG; notarize; staple; smoke from the **mounted** DMG (read-only by construction); `codesign --verify --deep --strict` on the mounted app afterwards; upload.
  - `upstream-diff` (report).
  - `release` (`needs: [build, macos]`, `if: startsWith(github.ref, 'refs/tags/')`, `permissions: contents: write`): `gh release create "$TAG" --draft …` with the four assets.
- Secrets live only in the `release` environment, whose deployment rule allows the `v*-ns.*` tags (plus `main` if dispatch should sign). Jobs "can only access these secrets after any configured rules … pass" `[CITED: docs.github.com manage-environments]`. Fork PRs never get secrets, and this workflow doesn't run on PRs anyway.
- Pin every `uses:` to a full SHA. Current pins resolved this session:

| Action | Tag | SHA |
|---|---|---|
| actions/checkout | v7.0.1 | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| actions/setup-python | v7.1.0 | `6d4fd22b20465ccc0f7354476588e8df7c9ca0e0` |
| actions/upload-artifact | v7.0.2 | `cf430e030ddbb5b0abf93d22962f4752f3646cd9` |
| actions/download-artifact | v8.0.2 | `9000827ccba6bdab643e8b6fd33ac0654aef8333` |

`[VERIFIED: gh api repos/<action>/releases/latest + commits/<tag>]`. The release upload uses the `gh` CLI preinstalled on runners, so no third-party release action is needed. Optionally turn on the repo setting "Require actions to be pinned to a full-length commit SHA" `[CITED: github.blog changelog 2025-08-15]`.

**Smoke (each bundle, `NX2A_HOME=$RUNNER_TEMP/home`):**
1. `nx2android -m porter doctor --json`: stdout parses as a JSON list (exit 0 or 1).
2. `nx2android -m porter profiles --json`: a non-empty list (proves the resource root, the engine copy and the profiles path).
3. `QT_QPA_PLATFORM=offscreen nx2android packaging/smoke_gui.py`: imports lz4.block/capstone/PIL/yaml/`compression.zstd`, disassembles a few AArch64 bytes, builds `gui.app.Window`, and waits up to 30 s for `games.table.rowCount() > 0`.
4. The bundle file listing is unchanged before and after the run. On Linux, run from `cp -a` + `chmod -R a-w`; on macOS, from the mounted DMG.

### Pattern 13: glibc floor and upstream diff (CI-04)
- `packaging/glibc_floor.py <bundle> <floor>`: for every regular ELF file, run `objdump -T` and regex `GLIBC_(\d+)\.(\d+)`. Print the maximum and the files needing it, and exit 1 above the floor. The arm64 `libQt6Gui.so.6` alone needs `GLIBC_2.38` `[VERIFIED: objdump on the wheel]`.
- The x64 floor value is an open question (2.34 in CONTEXT vs the 2.35 build runner).
- Upstream diff:
```bash
git fetch --no-tags https://github.com/shirai91/nx2android.git main
git diff --stat FETCH_HEAD...HEAD -- nxnative/ >> "$GITHUB_STEP_SUMMARY"
```
  Report only. Three dots mean "since the merge base", which is the fork's own divergence. Needs `fetch-depth: 0`.

### Pattern 14: TEST-02 skip
`unittest` discovery turns a module-level `SkipTest` into a skipped test `[VERIFIED: CPython unittest/loader.py "except case.SkipTest as e: return _make_skipped_test(...)"]`. Wrap only the imports in `tests/test_porter.py` (2–4 lines in an upstream test file):
```python
try: from porter import config, datapack, pipeline, profiles; from porter.upstream import android_profile, game
except ModuleNotFoundError as e:
    if e.name.split('.')[0] not in ('lz4', 'capstone', 'PIL', 'yaml', 'backports') or os.environ.get('CI'): raise   # CI installs the lock: a missing module there is a failure
    raise unittest.SkipTest(f'{e.name} is not installed (python -m pip install -r requirements.txt): the engine modules need it')
```
Today, locally, the suite fails at import with `No module named 'lz4'` (verified this session).

### Pattern 15: Bridge tests (TEST-03)
- `gui/runner.py` gets `PORTER = ['-m', 'porter']`, used for both long and one-shot calls. That literal also keeps arch rule 5 green.
- Tests set `runner.PORTER = [str(FAKE)]`, so the program stays `sys.executable` and runs `tests/fixtures/bridge/fake_porter.py`. Modes:
  - `replay <fixture.jsonl> [--exit N] [--stderr TEXT] [--hang]`;
  - `tree`: calls `porter.procs.setup` like real porter, spawns a sleeping grandchild, prints its pid, then sleeps.
- Use `QCoreApplication` (or `QApplication` for Window tests) and `QSignalSpy(...).wait(ms)`, which is bound `[VERIFIED: spike]`.
- Golden fixtures: real `porter port … --progress json` output from the dev Mac, trimmed, with local paths replaced by `<folder>`. Include `port_ok.jsonl`, `port_build_error.jsonl` (ends with an `error` event), `install_ok.jsonl` and `inspect_error.json`.
- Edge cases: a final line without `\n`, a non-JSON line, a JSON non-object line.

### Anti-Patterns to Avoid
- **Building the stop logic into `nxnative/scripts/build_ipa_from_nsp.py` `run()`**: that grows the subtree diff. The session/job at porter's root covers every descendant.
- **`GenerateConsoleCtrlEvent(CTRL_BREAK_EVENT, 0)` from the GUI**: it signals every process on the GUI's console, including the GUI.
- **Copying anything into `Contents/` after the final signature**: run `codesign --verify --deep --strict` last, and again after the smoke run.
- **`zip` / `shutil.make_archive('zip')` on macOS/Linux**: breaks symlinks.
- **`pull_request_target`, or interpolating `${{ github.* }}` straight into `run:`**: pass values through `env:`.
- **Showing the `error` message in a rich-text `QLabel` unescaped**: the message holds file paths and may contain `<`; use `html.escape` or `Qt.PlainText`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Process tree kill on POSIX | Walking `/proc` or `ps` for descendants | `CreateNewSession` + `os.killpg` | One syscall, covers grandchildren whose parent died; verified |
| Process tree kill on Windows | `taskkill /T` walking parent PIDs | Job Object `KILL_ON_JOB_CLOSE` | `taskkill /T` misses descendants whose parent already exited (PITFALLS 3) |
| psutil for tree handling | — | Built-ins above | No new dependency |
| Universal lock | Per-OS `pip freeze` | `uv pip compile --universal --generate-hashes` | One file, markers; verified |
| Notarization upload | `altool`, Apple ID passwords | `notarytool` + App Store Connect API key | altool retired; keys are revocable |
| Signing every Mach-O by hand | A `find … -exec codesign` script | PyInstaller `codesign_identity` + one outer re-sign | PyInstaller already signs each collected binary with runtime + timestamp |
| Linux xcb/Wayland plugin collection | Manual `datas` of plugin dirs | PyInstaller's Qt hook (already lists `wayland-*`) | Verified in `_modules_info.py` |
| A JSON protocol schema/version | `"v"` field, schema files | Additive fields + golden fixtures (locked) | — |

**Key insight:** each OS already has a "kill this whole subtree" primitive (session/process group, Job Object). The work is choosing *who creates it* (QProcess on POSIX, porter itself on Windows) and making sure adb starts outside it.

## Common Pitfalls

### Pitfall 1: The Windows grace path can't use CTRL_BREAK
**What goes wrong:** the plan implements D-05 literally and finds no way to set `CREATE_NEW_PROCESS_GROUP` from PySide6.
**How to avoid:** use the stdin `stop` line + `TerminateJobObject(job, 130)` (Pattern 1), and record it as a `checkpoint:decision`.
**Warning signs:** a plan task that names `setCreateProcessArgumentsModifier` or `CREATE_NEW_PROCESS_GROUP` in `gui/runner.py`.

### Pitfall 2: ctypes HANDLE truncation in the Job Object code
**What goes wrong:** without `restype = wintypes.HANDLE` and `argtypes`, 64-bit handles (and `GetCurrentProcess()`'s pseudo-handle `-1`) get truncated, and `AssignProcessToJobObject` fails or hits the wrong object.
**How to avoid:** declare `restype`/`argtypes` for `CreateJobObjectW`, `SetInformationJobObject`, `AssignProcessToJobObject`, `GetCurrentProcess`, `TerminateJobObject`, and check every return value. Test on the `windows-2025` runner with the `tree` fake.

### Pitfall 3: The adb server dies with the port on Windows
**What goes wrong:** the first adb command inside the job starts the server inside the job, and `KILL_ON_JOB_CLOSE` kills it at porter exit, so the device list empties after every install or cancel.
**How to avoid:** `adb start-server` before joining the job (Pattern 3). Don't "fix" it with `BREAKAWAY_OK`: that lets any descendant escape.

### Pitfall 4: A daemon thread reading `sys.stdin` can abort interpreter shutdown
**What goes wrong:** at exit, CPython can fail with "could not acquire lock for <_io.BufferedReader name='<stdin>'> at interpreter shutdown, possibly due to daemon threads" `[ASSUMED: known CPython behaviour, bpo-23309 family]`.
**How to avoid:** read the stop channel with `os.read(0, 64)` on the raw fd, never `sys.stdin`. Note that children inherit fd 0; none of the current tools read stdin in JSON mode (`nsp.ask` raises in JSON mode).

### Pitfall 5: D-08 "redo every cached stage" can delete game data
**What goes wrong:** stage reuse keys are `*.key` files: `aoc.key` at the build root; `<out>.key` beside outputs; `android/shaders.dmsv.key` `[VERIFIED: porter/pipeline.py:278]`; the font key; and others found by grepping the `reused(` call sites. Extracted RomFS under `<tid>_build/extract/` can also contain game files named `*.key`.
**How to avoid:** delete `<work>.rglob('*.key')` **excluding** anything under `extract/`. Extraction itself is atomic (`swap_in` renames a finished temp folder) `[VERIFIED: build_ipa_from_nsp.py swap_in]`. List a real build folder's `*.key` files during execution to confirm.

### Pitfall 6: QProcess `FailedToStart` never emits `finished`
**What goes wrong:** a missing or blocked executable (antivirus, quarantine) leaves `running()` false but the UI waiting forever.
**How to avoid:** connect `errorOccurred`; on `FailedToStart`, emit an `error` event and `finished(-1)`.

### Pitfall 7: Children still in the group after a successful run (POSIX)
**What goes wrong:** gating `finished` on "group empty" waits forever if something lingers (a misbehaving tool).
**How to avoid:** if porter exited and the group is non-empty, run the same `stop()` (TERM, then KILL at 5 s). The adb server is safe: it `setsid`s.

### Pitfall 8: The engine copy and "Application Support" spaces
**What goes wrong:** on macOS the engine copy lives under `~/Library/Application Support/…`, a path with a space. Tools taking paths in lists are fine, but any shell-joined or makefile path would break. The existing Windows bundle already runs from user paths with spaces, so it's probably fine `[ASSUMED]`.
**How to avoid:** do one full port on the dev Mac from the bundle (part of the manual RO check).

### Pitfall 9: The `console=True` .app is background-only
**What goes wrong:** no Dock icon, no menu bar, odd focus.
**How to avoid:** `info_plist={'LSBackgroundOnly': False}` (verified that the override wins).

### Pitfall 10: C-compiling tests on new CI hosts
**What goes wrong:** `tests/test_perf_adaptive.py` and `test_vk_present_timing.py` compile with `cc or clang` and `-pthread`. GitHub's Windows images put LLVM's `clang` on PATH `[ASSUMED]`, so these may *run* on `windows-2025` and fail to build. Linux and macOS results on the runners are also untested.
**How to avoid:** expect first-run failures. Fix with a `skipIf(os.name == 'nt')` (a small upstream-test edit), or install what they need. The first CI run is the discovery tool, so budget a task for it.

### Pitfall 11: Upstream tags trigger the fork's release
**What goes wrong:** `git fetch upstream --tags` + `git push --tags` pushes `v0.1.x`, and a `v*` trigger builds and drafts releases for upstream versions.
**How to avoid:** the trigger matches only the fork pattern (`v*-ns.*`); `git config remote.upstream.tagOpt --no-tags`; `build_bundle.py` uses `git describe --tags --match 'v*-ns.*'`.

### Pitfall 12: The Linux bundle picks up the build host's fontconfig
**What goes wrong:** `libfontconfig` isn't in PyInstaller's exclude list, so the bundle carries Ubuntu 22.04's copy. On newer distros that can print "Fontconfig error: unknown element" `[CITED: PITFALLS.md 6, MEDIUM]`.
**How to avoid:** the tester checks under X11 and Wayland in RELEASE_CHECK. If it appears, exclude `libfontconfig*` / `libfreetype*` in the spec (Linux) and list them as prerequisites.

## Code Examples

### porter/procs.py (core; Windows part not run on Windows this session)
```python
# Every porter run the GUI starts (NX2A_GUI=1) stops as one tree: POSIX by its session (gui/runner.py starts it with CreateNewSession), Windows by a Job Object
# porter joins here (PySide6 cannot start a process in a new console group, so CTRL_BREAK is not available). The adb server starts first, outside both.
import os, signal, subprocess, sys, threading

def _term(*_): raise KeyboardInterrupt   # SIGTERM from the GUI's killpg: _with_progress closes the stage and returns 130

def setup(a, on_stop):
    os.environ.update(MSBUILDDISABLENODEREUSE='1', DOTNET_CLI_USE_MSBUILD_SERVER='0', UseSharedCompilation='false')   # no MSBuild node outlives the port
    if a.cmd in ('devices', 'install') or getattr(a, 'install', False): adb_server()
    if not os.environ.get('NX2A_GUI'): return
    if os.name != 'nt': signal.signal(signal.SIGTERM, _term)
    job = _job() if os.name == 'nt' else None
    threading.Thread(target=_watch, args=(job, on_stop), daemon=True).start()

def adb_server():
    from porter import config, toolchain
    exe = toolchain.find_adb(config.load())
    if not exe: return
    try: subprocess.run([str(exe), 'start-server'], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30,
                        start_new_session=os.name != 'nt', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except (OSError, subprocess.TimeoutExpired): pass   # the first adb command reports the real problem

def _watch(job, on_stop):   # "stop\n" from the GUI, or EOF when the GUI is gone; os.read: a thread blocked in sys.stdin breaks interpreter shutdown
    buf = b''
    while b'stop' not in buf:
        try: chunk = os.read(0, 64)
        except OSError: chunk = b''
        if not chunk: break
        buf += chunk
    if os.name != 'nt': os.killpg(os.getpgid(0), signal.SIGTERM); return   # same as the GUI's own stop
    on_stop()   # runlog: "[RED] cancelled during <stage>", log closed
    if job: _k().TerminateJobObject(job, 130)
    else: os._exit(130)
```
The `_job()` / `_k()` ctypes helpers use the constants `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000` and `JobObjectExtendedLimitInformation = 9` `[CITED: Microsoft Learn JOBOBJECT_BASIC_LIMIT_INFORMATION]`. The struct order is `JOBOBJECT_BASIC_LIMIT_INFORMATION {LARGE_INTEGER PerProcessUserTimeLimit; LARGE_INTEGER PerJobUserTimeLimit; DWORD LimitFlags; SIZE_T MinimumWorkingSetSize; SIZE_T MaximumWorkingSetSize; DWORD ActiveProcessLimit; ULONG_PTR Affinity; DWORD PriorityClass; DWORD SchedulingClass}`, followed by `IO_COUNTERS` (6 × ULONGLONG) and 4 × SIZE_T for the extended struct `[CITED: same page; IO_COUNTERS layout ASSUMED]`.

### gui/runner.py stop and gating (sketch)
```python
PORTER = ['-m', 'porter']   # tests point this at a fake (tests/test_bridge.py)
GRACE_MS = 5000

def _process(parent, args):
    p = QProcess(parent); p.setProgram(sys.executable); p.setArguments([*PORTER, *args])
    p.setWorkingDirectory(str(paths.user_dir())); p.setProcessEnvironment(_env())   # never the bundle: it is read-only
    if os.name != 'nt': p.setUnixProcessParameters(QProcess.UnixProcessFlag.CreateNewSession)   # killpg then reaches dotnet, clang, the shader tools
    return p

def _alive(pgid):
    try: os.killpg(pgid, 0); return True
    except (ProcessLookupError, PermissionError): return False

class Porter(QObject):
    def stop(self):
        if not self.running() or self.stopping: return
        self.stopping = True
        if os.name == 'nt': self.p.write(b'stop\n')
        else: os.killpg(self.pgid, signal.SIGTERM)
        QTimer.singleShot(GRACE_MS, self._force)

    def _force(self):
        if os.name == 'nt': self.p.kill()   # porter's Job Object closes with it and takes every child along
        elif _alive(self.pgid): os.killpg(self.pgid, signal.SIGKILL)

    def _reap(self):   # finished only when nothing of the run is left
        if os.name != 'nt' and _alive(self.pgid):
            self.stop(); QTimer.singleShot(200, self._reap); return
        self.finished.emit(self.code)
```

### packaging/glibc_floor.py
```python
# The newest glibc symbol version any ELF in a Linux bundle needs: python packaging/glibc_floor.py dist/nx2android 2.35 (exit 1 above the floor)
import re, subprocess, sys
from pathlib import Path
root, floor = Path(sys.argv[1]), tuple(int(x) for x in sys.argv[2].split('.'))
need = {}
for f in root.rglob('*'):
    if f.is_file() and not f.is_symlink() and f.open('rb').read(4) == b'\x7fELF':
        for v in set(re.findall(r'GLIBC_(\d+)\.(\d+)', subprocess.run(['objdump', '-T', str(f)], capture_output=True, text=True).stdout)):
            need.setdefault(tuple(map(int, v)), set()).add(f.name)
top = max(need, default=(0, 0))
print(f'glibc floor {top[0]}.{top[1]}: {", ".join(sorted(need.get(top, ()))[:5])}')
sys.exit(top > floor)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `setChildProcessModifier(os.setsid)` / porter-side `setsid` | `QProcess.setUnixProcessParameters(CreateNewSession)` | Qt 6.6/6.7; bound in PySide6 6.12 | No porter-side setsid fallback needed |
| `altool` notarization | `notarytool` + API key | altool off since 2023-11-01 | — |
| MSBuild server opt-in | MSBuild server on by default | .NET 11 SDK `[CITED: MS Learn msbuild-server]` | The env opt-out matters as soon as a tester has a .NET 11 SDK |
| Tag-pinned actions | SHA pins + repo policy | GitHub policy 2025-08-15 | — |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `UseSharedCompilation=false` as an env var disables VBCSCompiler for the SDK's Csc task | Pattern 3 | A VBCSCompiler process may outlive a run; still killed by session/job |
| A2 | `MSBUILDDISABLENODEREUSE=1` is honoured by `dotnet build` in SDK 10 | Pattern 3 | Nodes linger ~10 min on Windows; the job still kills them on cancel, but not after a *successful* port. Add `-nodeReuse:false` to `translator()` if so |
| A3 | MSBuild/dotnet never use `CREATE_BREAKAWAY_FROM_JOB` | Pattern 2 | A build inside a no-breakaway job fails to start nodes. Check with the first Windows CI port test or a manual Windows run |
| A4 | Job Object ctypes struct (IO_COUNTERS layout) and handle signatures, untested on Windows here | Code Examples | Assignment fails; fallback is `taskkill /T` |
| A5 | Daemon-thread `sys.stdin` shutdown abort applies | Pitfall 4 | Low; `os.read` avoids it either way |
| A6 | GitHub Windows images put `clang` on PATH, so C tests run there | Pitfall 10 | Tests may pass or skip instead; no harm |
| A7 | macOS shows a generic TCC prompt without purpose strings | Pattern 8 | Possibly a denied access with no prompt; adding the strings is cheap either way |
| A8 | A space in the `Application Support` engine path breaks no tool | Pitfall 8 | A port fails on macOS; fix by quoting or another engine root (`~/Library/Caches`?) |
| A9 | No entitlement needed for ctypes/capstone under the hardened runtime (libffi static trampolines on Apple arm64) | Pattern 8 | The signed smoke fails; add `com.apple.security.cs.allow-unsigned-executable-memory` |
| A10 | Old adb releases (29.x, Debian 12) also `setsid` their server | Pattern 3 | Covered anyway by `start_new_session=True` in `adb_server()` |

## Open Questions (RESOLVED)

1. **Windows stop channel (D-05 deviation): `checkpoint:decision`.**
   - What we know: CTRL_BREAK needs `CREATE_NEW_PROCESS_GROUP`, which PySide6 can't set (verified typesystem).
   - Recommendation: stdin `stop` + `TerminateJobObject(job, 130)`; force = `QProcess.kill()`.
   - **RESOLVED:** D-09 (CONTEXT.md) adopts the recommendation: stdin `stop`, kill-on-close Job Object created after `adb start-server`, exit 130; force-kill is a plain kill of porter. Planned in 01-02 Task 2 (porter side) and 01-03 Task 2 (GUI side).
2. **Fork tag scheme: `checkpoint:decision` (one-way).**
   - Recommendation: `v<upstream version>-ns.<n>` (e.g. `v0.1.2-ns.1`), trigger `tags: ['v*-ns.*']`, assets `nx2android-0.1.2-ns.1-<os>-<arch>.<ext>`.
   - Alternative: a separate prefix (`nx2a-0.1.2.1`), which avoids looking like a semver pre-release.
   - **RESOLVED:** D-10 (CONTEXT.md, one-way, decided) takes `v<upstream version>-ns.<n>`, trigger `v*-ns.*` plus `workflow_dispatch`, assets `nx2android-<version>-<os>-<arch>.<ext>`. Planned in 01-06 (asset names) and 01-08 Task 1 (trigger).
3. **macOS bundle identifier and app name: `checkpoint:decision` (one-way).**
   - Recommendation: `io.github.namelesssaint8.nx2android`, display name `nx2android` (matches the GitHub Pages reverse-DNS convention for the fork owner) `[CITED: STACK.md]`.
   - **RESOLVED:** D-11 (CONTEXT.md, one-way, decided) takes `io.github.namelesssaint8.nx2android`, display name `nx2android`. Planned in 01-06 Task 1 (`packaging/nx2android.spec` BUNDLE).
4. **x64 glibc floor value.**
   - What we know: CONTEXT says 2.34 (the PySide6 wheel tag); the build runner `ubuntu-22.04` has 2.35, and RHEL/Rocky 9 ship 2.34 `[ASSUMED]`.
   - Recommendation: let the first release run report the real maximum. Set the gate at 2.34 and only relax it if the measured floor is 2.35 (then update CONTEXT/INSTALL to "2.35+").
   - **RESOLVED:** the x64 gate is 2.34 (arm64 2.39), enforced by `packaging/glibc_floor.py` (01-06 Task 2) in the release build matrix (01-08 Task 1). The first release run measures the real floor; if x64 is above 2.34 the executor does not relax the gate but stops at a checkpoint for the developer, because PKG-03 names 2.34 (01-08 Task 3).
5. **Per-push unsigned artifacts in `fork-ci.yml`.**
   - Recommendation: no, at first; testers get drafts from `fork-release.yml` via `workflow_dispatch`. This keeps CI fast on the arm64 runner.
   - **RESOLVED:** no per-push bundles; `fork-ci.yml` uploads none and testers get bundles from `fork-release.yml` dispatch runs or draft releases (01-07 objective, 01-08).
6. **Wayland check depth in CI.**
   - Recommendation: plugin presence check in CI; real X11/Wayland starts manual (tester / VM), recorded in RELEASE_CHECK. Optional `weston --backend=headless` later.
   - **RESOLVED:** CI checks plugin presence (`libqxcb.so`, `libqwayland*.so`, `libxdg-shell.so`) in `packaging/smoke_bundle.py` (01-06 Task 2); real X11 and Wayland starts are manual rows in `docs/RELEASE_CHECK.md` (01-08 Task 3). A headless weston run is not part of this phase.
7. **Apple Developer ID identity is not in the local keychain** (0 identities found).
   - STATE.md says the certificate is ready, so it only needs exporting as a `.p12` for the `release` environment secrets. The planner adds a `checkpoint:human-action` to create the environment and secrets (`MACOS_CERT_P12_BASE64`, `MACOS_CERT_PASSWORD`, `KEYCHAIN_PASSWORD`, `APPLE_API_KEY_P8_BASE64`, `APPLE_API_KEY_ID`, `APPLE_API_ISSUER_ID`, `MACOS_SIGN_IDENTITY`).
   - **RESOLVED:** 01-08 Task 2 is a blocking `checkpoint:human-action` that creates the protected `release` environment and all seven secrets, with a `gh api` check that lists them; the values never pass through the session.

## Environment Availability

| Dependency | Required By | Available (dev Mac) | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.14 | Bundle builds, spike | ✓ (Homebrew) | 3.14.5 | CI uses setup-python |
| Python 3.12 (default) | Dev tests | ✓ | 3.12.9 (below the CVE floor 3.12.11) | Fine for tests; not for tar extraction work |
| Python 3.11 | Floor check | ✗ locally | — | CI `ubuntu-22.04` job |
| uv | Lock generation | ✓ | 0.11.32 | `pip install uv` |
| PySide6 / PyInstaller in the dev Python | GUI dev, local bundle | ✗ in pyenv 3.12 (installed only in the scratch spike venv) | — | `pip install --require-hashes -r requirements.txt -r requirements-build.txt` |
| lz4 etc. in the dev Python | `tests/test_porter.py` | ✗ (`No module named 'lz4'`) | — | Install the lock; TEST-02 skip otherwise |
| Xcode tools (`codesign`, `notarytool` 1.1.3, `stapler`, `hdiutil`) | macOS signing | ✓ | — | — |
| Developer ID Application identity | Signing | ✗ in local keychain | — | Export .p12 for CI secrets (Open Q 7) |
| Docker | Optional floor-distro smoke | ✓ | 28.3.2 | — |
| gh CLI | Release upload, SHA lookup | ✓ | — | — |
| dotnet / adb | Manual full-port check | ✓ | 10.0.403 / 1.0.41 | — |
| GitHub-hosted runners (all four, public repo) | CI | ✓ repo is public (`gh api`: `"private":false`) | — | — |

**Missing dependencies with no fallback:** none. **With fallback:** the Developer ID .p12 export (human action) and a local Python 3.11.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Python `unittest` (stdlib) + PySide6 QtTest `QSignalSpy` for bridge tests |
| Config file | none (discovery) |
| Quick run command | `QT_QPA_PLATFORM=offscreen python -m unittest tests.test_bridge tests.test_runlog -v` |
| Full suite command | `QT_QPA_PLATFORM=offscreen python -m unittest discover -v tests` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BRDG-01 | `stop()` leaves no grandchild (fake `tree`), adb-like detached child survives; POSIX + Windows | integration (QProcess) | `python -m unittest tests.test_bridge.Stop -v` | ❌ Wave 0 |
| BRDG-01 | Real cancel during a port: no dotnet/MSBuild/clang left; adb still serves devices | manual per host | `ps -ef \| grep -E 'dotnet\|clang\|MSBuild'` / Task Manager; `adb devices` | RELEASE_CHECK.md row |
| BRDG-02 | `Window.closeEvent` with a running Porter → dialog (patched) → stop → window closes after finished | GUI offscreen | `python -m unittest tests.test_bridge.Close -v` | ❌ Wave 0 |
| BRDG-03 | Replay `port_build_error.jsonl` → `error` event reaches the status; crash fake → stderr tail; `porter tools --json` with a broken import → `{"error":…}` | unit + integration | `python -m unittest tests.test_bridge.Errors tests.test_runlog -v` | ❌ Wave 0 |
| BRDG-04 | `call_json` with `--hang` fake → `fail.timeout` within limit+1 s, process tree gone | integration | `python -m unittest tests.test_bridge.Timeout -v` | ❌ Wave 0 |
| BRDG-05 | `install /nonexistent --progress json` → first line `log` event, log file has stage lines + traceback, `error.log` matches | porter subprocess | `python -m unittest tests.test_runlog -v` | ❌ Wave 0 |
| BRDG-06 | `finished` fires only after the grandchild is gone; status shows "stopping…" then "cancelled" | integration | `python -m unittest tests.test_bridge.Stop -v` | ❌ Wave 0 |
| PKG-01..04 | Frozen bundle: doctor JSON, profiles non-empty, offscreen Window with games rows, from RO location, listing unchanged | CI smoke | `fork-release.yml` smoke steps | ❌ Wave 0 (`packaging/smoke_gui.py`) |
| PKG-02 | Notarized DMG opens from Finder after a browser download on macOS 14+ | manual | Finder; `spctl -a -t open --context context:primary-signature -v *.dmg` | RELEASE_CHECK.md |
| PKG-03/04 | Starts under X11 and Wayland | manual (tester/VM) | `QT_QPA_PLATFORM=xcb` / `wayland` launch | RELEASE_CHECK.md |
| PKG-05 | Full port from the mounted DMG / RO copy; `codesign --verify --deep --strict` after | CI smoke (partial) + manual full port | `codesign --verify --deep --strict --verbose=2 /Volumes/nx2android/nx2android.app` | RELEASE_CHECK.md |
| PKG-06 | Every requirement line carries `--hash`; CI installs with `--require-hashes` | unit + CI | `python -m unittest tests.test_workflows -v` | ❌ Wave 0 |
| CI-01 | 4-OS matrix green | CI | GitHub Actions run | ❌ Wave 0 (`fork-ci.yml`) |
| CI-03 | No `pull_request_target`; every `uses:` pinned to 40-hex SHA; secrets only referenced in jobs with `environment: release` | unit (YAML text regex) | `python -m unittest tests.test_workflows -v` | ❌ Wave 0 |
| CI-04 | glibc floor printed and gated; nxnative diff in the step summary | CI | `python packaging/glibc_floor.py dist/nx2android 2.34` | ❌ Wave 0 |
| TEST-02 | Without lz4: skip with the install hint; with `CI` set: failure | unit | `python -m unittest tests.test_porter -v` (in a venv without lz4) | edit existing |
| TEST-03 | Golden replays produce exact event sequences headless | integration | `QT_QPA_PLATFORM=offscreen python -m unittest tests.test_bridge.Replay -v` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** quick run command (bridge + runlog, under 30 s)
- **Per wave merge:** full suite locally + push to trigger `fork-ci.yml`
- **Phase gate:** `fork-ci.yml` green on all four OSes, one `fork-release.yml` `workflow_dispatch` run green (draft not published), manual RELEASE_CHECK rows (macOS RO full port + codesign, per-host cancel, X11/Wayland) before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/fixtures/bridge/fake_porter.py` + golden `*.jsonl` (recorded and scrubbed from a real run on the dev Mac)
- [ ] `tests/test_bridge.py` (Replay, Errors, Timeout, Stop, Close), skips cleanly when PySide6 is absent locally
- [ ] `tests/test_runlog.py` (log file, `log`/`error` events, retention, D-08 marker incl. the `extract/*.key` exclusion)
- [ ] `tests/test_workflows.py` (SHA pins, no `pull_request_target`, secrets only under `environment: release`, lock lines hashed)
- [ ] `requirements.in` / lock regeneration (PySide6-Essentials) so tests can import Qt in CI
- [ ] `packaging/smoke_gui.py`, `packaging/glibc_floor.py`

## Security Domain

### Applicable ASVS Categories (Level 1)

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | yes (CI) | GitHub `release` environment with deployment rules; job-level `permissions`; `contents: write` only in the release job |
| V5 Validation, Sanitization and Encoding | yes | GUI parses porter's JSON defensively (non-dict → `say`); `html.escape` / `Qt.PlainText` for `error.msg` and log lines in rich-text widgets |
| V6 Cryptography | no new crypto | Apple codesign/notarytool; never hand-rolled |
| V10 Malicious Code / supply chain | yes | Hashed lock (`--require-hashes`); SHA-pinned actions; no third-party actions beyond `actions/*` |
| V12 Files and Resources | yes | Bundle read-only; logs only under `user_dir()/logs`; no keys in logs (porter logs key *paths*, never contents) |
| V14 Configuration | yes | Secrets decoded to `$RUNNER_TEMP`, never echoed; temp keychain per job |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Developer ID p12 / API key exfiltrated via a PR workflow | Information disclosure | Release workflow not triggered by PRs; secrets only in the `release` environment; no `pull_request_target` (test-enforced) |
| Re-pointed action tag (tj-actions style) | Tampering | Full-SHA pins (test-enforced); optional repo SHA-pin policy |
| Workflow script injection via `${{ github.* }}` in `run:` | Elevation | Pass through `env:`; tag names come only from repo writers |
| Dependency substitution | Tampering | `pip install --require-hashes` from the universal lock |
| Markup injection into status labels from error text / paths | Spoofing | Escape or plain text |
| Bundle tampering after notarization (writes into `.app`) | Tampering | Read-only bundle design; `codesign --verify --deep --strict` after the smoke run |
| Orphaned processes writing into the build folder after cancel | Tampering (integrity of cache) | Tree kill + D-08 marker forcing a redo |

## Sources

### Primary (HIGH confidence)
- Local spike, this session: PySide6-Essentials 6.12.0 + PyInstaller 6.22.3 on Python 3.14.5 (macOS arm64): QProcess bindings, CreateNewSession + killpg kills a grandchild, BUNDLE layout, frozen `sys.*` flags, codesign seal break and outer re-sign, PyInstaller `osx.py` / `utils/osx.py` / `qt/_modules_info.py` / `depend/dylib.py` source
- `pyside6_essentials-6.12.0-cp310-abi3-manylinux_2_39_aarch64.whl` contents and `objdump -p` / `objdump -T` of its Qt libraries
- `uv pip compile --universal --generate-hashes` run on the proposed `requirements.in` / `requirements-build.in`
- pyside-setup `sources/pyside6/PySide6/QtCore/typesystem_core_common.xml` (branches 6.10, 6.12, dev) and `typesystem_core_win.xml`
- AOSP `packages/modules/adb` `client/main.cpp`, `adb.cpp` (main branch)
- CPython `unittest/loader.py` (local 3.12)
- `gh api` for action release SHAs and repo visibility
- Repo files read this session: `gui/runner.py`, `gui/app.py`, `porter/cli.py`, `porter/paths.py`, `porter/pipeline.py`, `porter/adb.py`, `porter/upstream.py`, `packaging/*`, `tests/arch_rules.py`, `tests/test_porter.py`, `nxnative/scripts/build_ipa_from_nsp.py`, `docs/RELEASE_CHECK.md`, `docs/ARCHITECTURE.md`

### Secondary (MEDIUM confidence)
- https://learn.microsoft.com/en-us/windows/console/generateconsolectrlevent
- https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information
- https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
- https://learn.microsoft.com/en-us/visualstudio/msbuild/msbuild-server
- https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet-build (`--disable-build-servers`)
- https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments
- https://github.blog/changelog/2025-08-15-github-actions-policy-now-supports-blocking-and-sha-pinning-actions/
- `.planning/research/STACK.md`, `PITFALLS.md`, `ARCHITECTURE.md` (prior research, cited where reused)

### Tertiary (LOW confidence)
- `MSBUILDDISABLENODEREUSE` semantics from Ed-Fi docs and WebKit bug 127002 (not the MSBuild repo)
- startdebugging.net post on the .NET 11 MSBuild server default (matches MS Learn)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH (versions resolved and installed this session)
- Architecture: HIGH for POSIX and macOS mechanics (spiked); MEDIUM for Windows (documented APIs, code not executed on Windows)
- Pitfalls: MEDIUM-HIGH (several verified in source; Windows and CI-runner ones assumed)

**Research date:** 2026-10-29
**Valid until:** 2026-11-28 (pins and action SHAs move; re-resolve SHAs when writing the workflows)
