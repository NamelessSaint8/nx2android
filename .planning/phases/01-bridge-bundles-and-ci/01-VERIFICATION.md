---
phase: 01-bridge-bundles-and-ci
verified: 2026-10-29T20:45:00Z
status: human_needed
score: 3/5 roadmap success criteria verified (SC1 and SC2 need host checks); plan must-haves 58/59 verified (1 by override), 1 waits on the same host checks
covered_files: [".github/workflows/fork-ci.yml", ".github/workflows/fork-release.yml", ".planning/phases/01-bridge-bundles-and-ci/01-01-PLAN.md", ".planning/phases/01-bridge-bundles-and-ci/01-01-SUMMARY.md", ".planning/phases/01-bridge-bundles-and-ci/01-02-PLAN.md", ".planning/phases/01-bridge-bundles-and-ci/01-02-SUMMARY.md", ".planning/phases/01-bridge-bundles-and-ci/01-03-PLAN.md", ".planning/phases/01-bridge-bundles-and-ci/01-03-SUMMARY.md", ".planning/phases/01-bridge-bundles-and-ci/01-04-PLAN.md", ".planning/phases/01-bridge-bundles-and-ci/01-04-SUMMARY.md", ".planning/phases/01-bridge-bundles-and-ci/01-05-PLAN.md", ".planning/phases/01-bridge-bundles-and-ci/01-05-SUMMARY.md", ".planning/phases/01-bridge-bundles-and-ci/01-06-PLAN.md", ".planning/phases/01-bridge-bundles-and-ci/01-06-SUMMARY.md", ".planning/phases/01-bridge-bundles-and-ci/01-07-PLAN.md", ".planning/phases/01-bridge-bundles-and-ci/01-07-SUMMARY.md", ".planning/phases/01-bridge-bundles-and-ci/01-08-PLAN.md", ".planning/phases/01-bridge-bundles-and-ci/01-08-SUMMARY.md", "docs/ARCHITECTURE.md", "docs/RELEASE_CHECK.md", "gui/__main__.py", "gui/app.py", "gui/runner.py", "packaging/INSTALL.md", "packaging/build_bundle.py", "packaging/glibc_floor.py", "packaging/nx2android.py", "packaging/nx2android.spec", "packaging/smoke_bundle.py", "packaging/smoke_gui.py", "porter/cli.py", "porter/paths.py", "porter/pipeline.py", "porter/procs.py", "porter/runlog.py", "requirements-build.in", "requirements-build.txt", "requirements-dev.in", "requirements-dev.txt", "requirements.in", "requirements.txt", "tests/fixtures/bridge/fake_porter.py", "tests/fixtures/bridge/record.py", "tests/test_bridge.py", "tests/test_packaging.py", "tests/test_paths.py", "tests/test_porter.py", "tests/test_porter_guard.py", "tests/test_runlog.py", "tests/test_workflows.py"]
covered_digest: "v4:sha256:ede038144caa3f3416f03a6898dff98347c50e1ec4f1f81676cf491e9598d207"
behavior_unverified: 0
overrides_applied: 1
overrides:
  - must_have: "Each Linux build job reports the bundle's GLIBC_ symbol floor in the step summary and fails above 2.34 (x64) or 2.39 (arm64)"
    reason: "The ubuntu-22.04 runner's own libpython3.14, libgcc_s, cairo, tcl and tk need GLIBC_2.35. The developer chose to raise the x64 gate to 2.35 (option B at the 01-08 Task 3 checkpoint) over a container build or trimming those libraries. PKG-03 in REQUIREMENTS.md now says glibc 2.35+, and fork-release.yml, glibc_floor.py, INSTALL.md and the Release test say the same. The arm64 gate stays 2.39 (measured 2.38)."
    accepted_by: "NamelessSaint8 (developer, 01-08 Task 3 checkpoint)"
    accepted_at: "2026-10-29T19:23:05Z"
human_verification:
  - test: "On a Windows x64 PC with no Python installed, unzip nx2android-<ver>-windows-x64.zip (fork-release run 40940461343 artifact) and double-click nx2android.exe"
    expected: "The window opens with Port, Setup and Games tabs, the Games tab lists the profiles, and the console window is hidden"
    why_human: "The CI smoke runs on a runner where setup-python is installed, and it starts the GUI only offscreen. A first start on Windows also copies about 150 MB of engine files while Defender scans them (review WR-03), which only a real PC shows"
  - test: "On a macOS 14+ Apple Silicon Mac, download the DMG in a browser (so it carries the quarantine flag), open it from Finder, drag nx2android.app to Applications and start it"
    expected: "No Gatekeeper warning; the app starts with a Dock icon"
    why_human: "CI proves notarization Accepted, stapler validate, and spctl 'accepted, source=Notarized Developer ID' on the DMG. The Finder open of a quarantined download is a GUI interaction that CI cannot do"
  - test: "On Linux x64 (glibc 2.35+) and on Linux arm64 (glibc 2.39+), unpack the tarball and start ./nx2android once with QT_QPA_PLATFORM=xcb and once with QT_QPA_PLATFORM=wayland"
    expected: "The window appears under both, with no Fontconfig or platform-plugin errors"
    why_human: "CI checks only that the xcb and Wayland plugins are present and that the GUI starts offscreen. A real display server is needed"
  - test: "On the Mac, mount the DMG, start /Volumes/nx2android/nx2android.app from the mount, port a playable title with your own prod.keys, then run codesign --verify --deep --strict --verbose=2 /Volumes/nx2android/nx2android.app"
    expected: "The port succeeds, the engine copy is under ~/Library/Application Support/nx2android/engine/, and codesign still passes"
    why_human: "Needs real keys and a game dump. CI smoke covers doctor, profiles and the GUI start from the read-only mount only, not a full port with dotnet and the NDK"
  - test: "On each host, start a real port from the GUI, press Cancel during the shader or host stage, then list processes (ps -ef | grep -E 'dotnet|clang|MSBuild|shader', or Task Manager on Windows) and run adb devices"
    expected: "The status shows 'stopping…' then 'cancelled'; no dotnet, MSBuild, clang or shader-tool process is left; adb devices still lists the device and does not restart the server"
    why_human: "Bridge tests prove the mechanism with stand-in processes on Windows, macOS and Linux in CI: the grandchild dies, a detached process survives, and 'cancelled' appears only after finished. Real dotnet/MSBuild node trees and a real adb server need a real toolchain and device"
---

# Phase 1: Bridge, Bundles and CI Verification Report

**Phase Goal:** Today's GUI controls runs reliably and reaches testers as a CI-built bundle on Windows x64, macOS Apple Silicon, Linux x64 and Linux arm64
**Verified:** 2026-10-29T20:45:00Z
**Status:** human_needed
**Re-verification:** No (initial verification)

## Goal Achievement

The code, tests and CI behind every requirement exist and work. Evidence: the local suite passed (104 tests, 1 skipped for missing NDK headers), and so did fork-ci run 40940462470 (five jobs) and fork-release run 40940461343 (four bundles, notarized). What is left is the end-of-phase host checks that only real machines can do. Roadmap SC1 and SC2 name them explicitly.

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A tester on each host starts the GUI without Python: the Windows zip runs, the notarized DMG opens from Finder with no Gatekeeper warning, the Linux tarballs run under X11 and Wayland, and a full port from a read-only location leaves the bundle unchanged with codesign still passing | ? UNCERTAIN (human) | CI release run 40940461343: all four bundles built. smoke_bundle.py passed on each from a read-only copy or mount: doctor, profiles, offscreen Window with 14 profiles, and "nothing was written into the bundle". On macOS: notarytool "Accepted", stapler validate, spctl "accepted, source=Notarized Developer ID", and codesign --deep --strict after the smoke. Linux bundles hold libqxcb and libqwayland. Still to do by hand: Finder open, X11/Wayland, Windows PC without Python, full port (see Human Verification) |
| 2 | Cancel leaves no dotnet/MSBuild/clang/shader-tool process while the adb server keeps running; "cancelled" only once the run stopped; closing mid-port asks and stops the same way | ? UNCERTAIN (human) | Mechanism verified by tests that ran in CI on windows-2025, macos-15 and ubuntu: test_runlog.Stop (grandchild dies through the Job Object on Windows and the session on POSIX), test_bridge.Stop (test_stop_kills_tree_keeps_detached, test_force_after_grace, test_events_before_finished), and test_bridge.Close (6). The Windows CI log shows them ok. Real toolchain and real adb still need a check by hand |
| 3 | A failing, crashing or hanging porter command shows the real cause or a timeout with Retry, never a swallowed stderr or "no game found"; the saved log of any run opens from the GUI | ✓ VERIFIED | runlog.run emits ev:log first, then ev:error with msg/type/log, plus the one-shot {"error"} document (RunLog, OneShot, RunLogInProcess tests). runner.call_json has TIMEOUTS, kills the tree at the limit, and returns a fail dict (Timeout ×4, Errors ×9). app.failed() adds Retry, and every view uses it. "No game found" was removed from on_inspect. Open log is wired through QDesktopServices (Errors.test_failed_port_shows_cause_and_log) |
| 4 | Every push runs the suite on four OSes from the hashed lock, including headless bridge tests that replay golden JSON-lines fixtures; a missing lz4 is a clear skip | ✓ VERIFIED | fork-ci.yml runs on push and pull_request on windows-2025, macos-15, ubuntu-22.04 and ubuntu-24.04-arm (3.14), plus ubuntu-22.04 (3.11). It installs with `--require-hashes` under QT_QPA_PLATFORM=offscreen. Run 40940462470 passed all five jobs. Replay ×5 uses the fixtures port_ok, port_build_error, install_ok and edge. test_porter's setUpModule gives a named skip, and test_porter_guard proves a skip locally and a failure under CI |
| 5 | The release workflow builds all four bundles, signs and notarizes macOS, smoke-tests each, reports the glibc floor and the nxnative/ diff; secrets sit in a protected environment that PR workflows cannot reach; actions are pinned by SHA | ✓ VERIFIED | fork-release.yml has the build matrix, the macos job (environment: release), upstream-diff and the release job (tags only). The environment 'release' has deployment policies `main` (branch) and `v*-ns.*` (tag). Secrets are referenced only on lines 97-118, inside the macos job. There is no PR trigger, and every `uses:` is pinned to a 40-hex SHA. CI step summaries report glibc floors 2.35 (x64) and 2.38 (arm64). The Release (7) and Ci (5) tests pass |

**Score:** 3/5 roadmap truths verified; 2 wait on host checks by hand (0 present-but-behavior-unverified).

### Plan must-haves (59 truths across 8 plans)

| Plan | Truths | Result | Notes |
|------|--------|--------|-------|
| 01-01 PKG-06 locks | 5 | ✓ 5/5 | Lock ×5 tests pass. The .venv is Python 3.14 with the locks installed by hash. The lock review is the user's approval recorded at the blocking checkpoint |
| 01-02 runlog/procs | 8 | ✓ 7/8, 1 human | All behaviour tests pass, including on Windows CI. The "adb server started before the Job Object" truth holds in code order (`setup()` calls `adb_server()` before `_job()`), but its survival is checked only with a stand-in, so it goes to the SC2 host check |
| 01-03 GUI stop/close | 8 | ✓ 8/8 | Errors, Stop and Close pass on three OSes. The adjacency, empty and ordering edges are covered by tests (stop_after_exit, stop_when_idle, events_before_finished) |
| 01-04 timeouts/replay | 8 | ✓ 8/8 | Timeout, Errors and Replay pass, including the empty answer, undecodable stderr, Retry idempotency and concurrent calls |
| 01-05 read-only bundle | 6 | ✓ 6/6 | Engine ×7 and Launcher ×1 pass. CI smoke on all four bundles reports "nothing was written into the bundle" |
| 01-06 bundles | 6 | ✓ 6/6 | All four D-10 asset names come from the CI run. The spec holds the D-11 identity, LSMinimumSystemVersion 14.0 and LSBackgroundOnly False. INSTALL.md covers all four hosts, the Linux libraries and the Open log/log folders |
| 01-07 fork-ci | 7 | ✓ 7/7 | All five jobs passed at f443063. The concurrency group cancels in progress, fail-fast is false, and the `Ran [1-9]` gate is in place |
| 01-08 fork-release | 11 | ✓ 11/11 (1 override) | The Linux x64 gate is 2.35, not the 2.34 the plan wrote: a developer decision, now in PKG-03 (see overrides). The draft is created only on tags and needs build, macos and upstream-diff. The exact-four-assets check, the keychain cleanup in always() and `cancel-in-progress: false` are all present |

### Prohibitions

| Plan | Prohibition | Tier | Status | Evidence |
|------|-------------|------|--------|----------|
| 01-02 | MUST NOT write prod.keys contents into a run log or event | test | ✓ VERIFIED | RunLogInProcess.test_no_key_material passes: the log names the keys path and does not contain SECRETVALUE. runlog writes only argv |
| 01-03 | MUST NOT signal or kill any process outside the run's session or Job Object | test | ✓ VERIFIED (main path) | test_stop_kills_tree_keeps_detached passes on three OSes. `_kill` refuses pgid <= 1. Note: the Windows force path (`taskkill /T` after the grace period) follows parent-pid links and is not bounded by the Job Object. No test covers this prohibition on that path (Warning below) |
| 01-04 | MUST NOT commit fixtures holding local paths, homes, keys or game data | test | ✓ VERIFIED | Replay.test_fixtures_are_scrubbed passes. A grep of tests/fixtures/bridge/ for /Users/, /home/ and C:\Users finds nothing |

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `porter/runlog.py` | ✓ VERIFIED | 144 lines: run/build_folder/cut_off/_prune, wired from cli.main |
| `porter/procs.py` | ✓ VERIFIED | 84 lines: MSBuild env, adb_server, Job Object with restype/argtypes, os.read(0) watcher, wired from runlog.run |
| `porter/cli.py`, `porter/pipeline.py` | ✓ VERIFIED | Hook lines only: the dispatch line, the build_folder hook, `-nodeReuse:false`, and the 3.11 f-string fix |
| `porter/paths.py` | ✓ VERIFIED | FROZEN, per-layout REPO, `_engine()` copy and prune |
| `gui/runner.py` | ✓ VERIFIED | GRACE_MS, TIMEOUTS, `_process` (cwd user_dir, NX2A_GUI, new session), stop/_force/_reap, call_json |
| `gui/app.py` | ✓ VERIFIED | log/error events, Open log, stopping…/cancelled, closeEvent/ask_stop, failed()/Retry in all views |
| `packaging/*` (build_bundle, spec, smoke_bundle, smoke_gui, glibc_floor, INSTALL.md) | ✓ VERIFIED | All exercised by fork-release run 40940461343 |
| `.github/workflows/fork-ci.yml`, `fork-release.yml` | ✓ VERIFIED | Both runs green at f443063 |
| `requirements*.in/.txt` | ✓ VERIFIED | Hashed uv locks; the Lock tests pass |
| `tests/test_bridge.py`, `test_runlog.py`, `test_paths.py`, `test_packaging.py`, `test_workflows.py`, `test_porter_guard.py`, `tests/fixtures/bridge/*` | ✓ VERIFIED | All run in the suite (104 tests) |

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| cli.main | runlog.run | `return runlog.run(a, {...}[a.cmd])` | ✓ WIRED |
| runlog.run | procs.setup | `note = procs.setup(a, cut_off)` | ✓ WIRED |
| runlog | upstream PROG | `_wrap(PROG, nsp)` instance wrappers, unwrapped after the run | ✓ WIRED |
| pipeline.inputs | runlog.build_folder | one hook line after the mkdir loop | ✓ WIRED |
| PortTab.on_event | error/log events | `elif e == 'log'` / `elif e == 'error'` branches | ✓ WIRED |
| Porter.stop | procs SIGTERM handler / _watch | `os.killpg(pgid, SIGTERM)` (POSIX) / `write(b'stop\n')` (Windows) | ✓ WIRED |
| Window.closeEvent | Porter.stop | Stop and quit stops porter and fetch; run_ended closes | ✓ WIRED |
| call_json | porter {"error"} | becomes `fail['error']` | ✓ WIRED |
| card/check_msg/note/dl_step linkActivated | inspect/check/load/download | Retry link | ✓ WIRED |
| paths.NXNATIVE | build_bundle ENGINE file | `_engine()` reads `<REPO>/ENGINE` | ✓ WIRED |
| build_bundle | spec | NX2A_VERSION, PYINSTALLER_STRICT_BUNDLE_CODESIGN_ERROR | ✓ WIRED |
| smoke_bundle | smoke_gui | `<exe> smoke_gui.py` offscreen | ✓ WIRED |
| fork-ci / fork-release | requirements*.txt | `pip install --require-hashes` | ✓ WIRED |
| fork-release macos | environment release secrets | `environment: release`, secrets only via env: | ✓ WIRED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite (run once) | `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -v tests` | Ran 104 tests, OK (skipped=1: NDK Vulkan headers) | ✓ PASS |
| Arch rules | `.venv/bin/python tests/arch_rules.py` | all checks passed | ✓ PASS |
| Windows stop tree | fork-ci job 123682188291 log | test_runlog.Stop grandchild/stdin_stop/eof ok, test_bridge.Stop ×6 ok, Close ×6 ok; Ran 102, OK (skipped=2) | ✓ PASS |
| macOS notarized bundle | fork-release job 123682191028 log | Accepted; validate worked; spctl accepted Notarized Developer ID; smoke 13 PASS incl. codesign after | ✓ PASS |
| Linux bundles | jobs 123682190996 / 123682190882 | smoke all PASS incl. xcb/Wayland plugins; glibc 2.35 / 2.38 | ✓ PASS |
| Windows bundle | job 123682190810 | smoke all PASS (read-only copy, no writes) | ✓ PASS |
| Release environment | `gh api .../environments/release/deployment-branch-policies` | main (branch), v*-ns.* (tag) | ✓ PASS |

### Probe Execution

Step 7c: no `scripts/*/tests/probe-*.sh` exist and no plan declares one. The phase's runnable checks are smoke_bundle.py and glibc_floor.py, which ran inside fork-release (above).

### Requirements Coverage

All 18 phase IDs are claimed by at least one plan. REQUIREMENTS.md maps no other ID to Phase 1, so nothing is orphaned.

| Requirement | Source Plan | Status | Evidence |
|-------------|-------------|--------|----------|
| BRDG-01 | 01-02, 01-03 | ? NEEDS HUMAN | Mechanism tested on three OSes; the real-toolchain cancel is open (REQUIREMENTS.md still says Pending) |
| BRDG-02 | 01-03 | ✓ SATISFIED | Close ×6 |
| BRDG-03 | 01-02, 01-03, 01-04 | ✓ SATISFIED | RunLog, OneShot, Errors |
| BRDG-04 | 01-04 | ✓ SATISFIED | Timeout ×4, Errors (empty answer, undecodable stderr, concurrent) |
| BRDG-05 | 01-02, 01-03 | ✓ SATISFIED | run logs and Open log, Retention ×1 |
| BRDG-06 | 01-03 | ✓ SATISFIED | Stop.test_port_tab_status, _reap gates finished on an empty session |
| PKG-01 | 01-06 | ? NEEDS HUMAN | Windows bundle built and smoked in CI; a start on a PC without Python is open |
| PKG-02 | 01-06, 01-08 | ? NEEDS HUMAN | Notarized, stapled, spctl accepted in CI; the Finder open is open |
| PKG-03 | 01-06 | ? NEEDS HUMAN | Built, plugins present, glibc 2.35; X11/Wayland start is open |
| PKG-04 | 01-06 | ? NEEDS HUMAN | Built, plugins present, glibc 2.38 (≤ 2.39); X11/Wayland start is open |
| PKG-05 | 01-05, 01-06 | ? NEEDS HUMAN | Read-only smoke on all four with no writes; the full port + codesign is open |
| PKG-06 | 01-01 | ✓ SATISFIED | Lock ×5; build and dev locks kept apart |
| CI-01 | 01-07 | ✓ SATISFIED | fork-ci run 40940462470 |
| CI-02 | 01-08 | ✓ SATISFIED | fork-release run 40940461343 |
| CI-03 | 01-08 | ✓ SATISFIED | Protected environment, SHA pins, no PR trigger on release, Release/Ci tests |
| CI-04 | 01-08 | ✓ SATISFIED | glibc floors in the step summary; the upstream-diff job passed |
| TEST-02 | 01-07 | ✓ SATISFIED | setUpModule skip plus test_porter_guard (skip locally, fail under CI) |
| TEST-03 | 01-04 | ✓ SATISFIED | Replay ×5 offscreen, on four OSes in CI |

### Anti-Patterns Found

No TBD, FIXME, XXX, TODO or HACK markers in any file this phase changed. The one shortcut comment, in porter/paths.py, uses the project's `shortcut:` form.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| porter/procs.py / gui/runner.py | 77-85 / 79-84 | WR-01: if `_job()` fails on Windows, a stop ends porter alone and the GUI's taskkill fallback can never run | ⚠️ Warning | Leaves the tree orphaned only on the degraded no-Job-Object path. The main path is tested on windows-2025 |
| porter/procs.py | 69-76 | WR-02: children inherit the stop pipe; `adb shell` during install can swallow "stop" (Windows) | ⚠️ Warning | Windows cancel during install falls to the 5 s force kill and leaves no "cancelled during" line in the log |
| porter/paths.py | 24-50 | WR-03: the frozen engine copy runs at import time with no retry or cleanup (Defender locks on rename) | ⚠️ Warning | Could make the first Windows start fail with a hidden console. Watch for it during the PKG-01 check |
| .github/workflows/fork-release.yml | 161-176 | WR-04: the "report, not a gate" upstream-diff job gates the release job | ⚠️ Warning | An upstream fetch failure would block a draft release |
| gui/runner.py | 16 | WR-05: the devices limit (15 s) is below porter's adb timeouts (30 s) | ⚠️ Warning | A slow adb start shows a timeout instead of adb's own error |
| tests/test_runlog.py, tests/test_bridge.py | 128, 83-97 | WR-06: tests can start the developer's real adb server | ⚠️ Warning | Test side effect only |
| gui/app.py | 236-247 | UI-REVIEW: a stage row stays at "▶" after a cancel or failure that sends no stage_end (Windows os._exit path) | ⚠️ Warning | Cosmetic. The status line still says "cancelled" correctly |
| gui/runner.py | 79-84 | The Windows force path's `taskkill /T` follows parent pids and is not bounded by the Job Object | ⚠️ Warning | Only after the 5 s grace period. A process porter starts directly and detaches would be killed. The adb daemon, started through an exited client, is not reached |
| tests/test_porter_guard.py | — | The only non-planning change since f443063. It passes locally but has not run in fork-ci (HEAD not pushed) | ℹ️ Info | Push to get it on four OSes |
| .claude/CLAUDE.md | — | The constraint says "Python 3.11+ for dev runs", but the GUI now needs 3.12+ (user decision in 01-07) | ℹ️ Info | Doc drift. The orchestrator was to raise it with the user |
| fork-release macos job | — | Developer ID certificate expires 2027-02-01 | ℹ️ Info | Renew the secret before then |

All 10 review findings (WR-01..06, IN-01..04) are recorded `open` in 01-REVIEW-DISPOSITION.md. None stops a must-have from holding on the main path, so none is a gap. They need triage (fix or defer) before Phase 2 or the first tag.

### Human Verification Required

These are the "not run" rows of docs/RELEASE_CHECK.md's Host checks table. Use the artifacts of fork-release run 40940461343 (or a newer one), and record each result in that table.

1. **Windows zip on a PC without Python (PKG-01).** Unzip and double-click nx2android.exe. The window opens, the console is hidden and the Games tab lists the profiles. Why by hand: CI has Python and starts the GUI only offscreen. The first start copies the engine while Defender scans it (WR-03).
2. **DMG from a browser download (PKG-02).** Open it from Finder, drag the app to Applications and start it. Expected: no Gatekeeper warning. Why by hand: CI proved notarization, stapling and spctl, but not the Finder open of a quarantined file.
3. **Linux x64 and arm64 under X11 and Wayland (PKG-03, PKG-04).** Start with QT_QPA_PLATFORM=xcb, then with =wayland. Expected: the window appears with no Fontconfig or plugin errors. Why by hand: needs a real display server.
4. **Full port from the mounted DMG, then codesign (PKG-05).** Expected: the port succeeds, the engine copy is under ~/Library/Application Support (a path with a space), and `codesign --verify --deep --strict` still passes. Why by hand: needs your keys and a game.
5. **Real cancel mid-port on each host (BRDG-01, SC2).** Expected: "stopping…" then "cancelled", no dotnet, MSBuild, clang or shader-tool process left, and `adb devices` still answers without a server restart. Why by hand: CI proves the mechanism with stand-ins, not with real MSBuild node trees and a real adb server.

### Gaps Summary

No blocking gaps. Every requirement has substantive, wired code with passing tests locally, plus green fork-ci and fork-release runs at f443063, the last commit with source changes. The x64 glibc deviation is the developer's own decision, recorded as an override. The status is human_needed because roadmap SC1 and SC2 promise host behaviour that only real machines can show: a Gatekeeper open of a quarantined DMG, X11 and Wayland starts, a start on a PC without Python, a full port from the read-only DMG, and a real cancel with real toolchains and adb. The six open review warnings are worth fixing before the first `v*-ns.*` tag, WR-01 and WR-03 most of all, since they touch the Windows paths of BRDG-01 and PKG-01.

---

_Verified: 2026-10-29T20:45:00Z_
_Verifier: Claude (gsd-verifier)_
