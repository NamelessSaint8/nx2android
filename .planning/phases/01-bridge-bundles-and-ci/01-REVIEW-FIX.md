---
phase: 01-bridge-bundles-and-ci
fixed_at: 2026-10-29T21:09:47Z
review_path: .planning/phases/01-bridge-bundles-and-ci/01-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 1: Code Review Fix Report

**Fixed at:** 2026-10-29T21:09:47Z
**Source review:** .planning/phases/01-bridge-bundles-and-ci/01-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 6 (WR-01 to WR-06; Info findings are out of scope)
- Fixed: 6
- Skipped: 0

**Where verification ran:** in the main checkout (`/Volumes/Data/Dev/nx2android`, branch `main`), on macOS. No worktree was used, because the orchestrator's root-pin guard requires commits from the main checkout. The suite ran with `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover tests`: 104 tests before the fixes, 109 after, all OK with 1 skipped. `tests/arch_rules.py` reports all checks passed. Windows-only behaviour (WR-01, WR-02) is covered by tests that run on every OS, but it has not been run on a Windows host.

## Fixed Issues

### WR-01: Windows stop without a Job Object orphans the whole tree

**Files modified:** `porter/procs.py`, `gui/runner.py`, `tests/test_runlog.py`
**Commit:** 42373ef
**Applied fix:** When there is no Job Object, `_watch` now runs `taskkill /T /F /PID <own pid>` before `os._exit(130)`. The GUI comment at `_force` now describes the path that can still be reached: a porter that did not end its own tree. New test `Stop.test_windows_stop_without_job_kills_tree` mocks `os.name='nt'`, `os.read`, `subprocess.run` and `os._exit`, and checks the taskkill command.
**Status:** fixed: requires human verification (logic change on Windows, not run on a Windows host)

### WR-02: Child processes inherit the stop channel (porter's stdin), and `adb shell` can swallow "stop"

**Files modified:** `porter/procs.py`, `tests/test_runlog.py`
**Commit:** bf29f1f
**Applied fix:** `setup()` gives the watcher its own `os.dup(0)` copy of the pipe, which is non-inheritable, and points fd 0 at the null device before the watcher starts. `_watch` reads from that fd. New test `Stop.test_children_get_no_stop_channel` checks that a child started without `stdin=` reads an empty stdin. It fails without the fix (the child blocks on the pipe) and passes with it.
**Status:** fixed: requires human verification (whether UCRT `_dup2` updates the Windows standard input handle needs a check on a Windows runner)

### WR-03: The frozen engine copy runs at import time and has no recovery when it fails

**Files modified:** `porter/paths.py`, `tests/test_paths.py`, `packaging/nx2android.py`, `gui/__init__.py`, `tests/test_bridge.py`
**Commit:** 5db6832
**Applied fix:**
- The rename into place is retried 5 times, 0.5 s apart.
- A `dst` folder without `nxnative/` is renamed aside to `<eid>.old-<pid>`, and the existing prune loop removes it. This avoids an in-place `rmtree` that could race another porter's successful rename.
- Any `OSError` makes the temp copy writable, removes it (a partial copy keeps the bundle's read-only folders, so `rmtree` alone failed), and raises `OSError('[RED] could not copy the engine to … then start nx2android again')`.
- The bundle's GUI branch catches that error and shows it through the new `gui.fatal()`, which puts up a `QMessageBox`. It lives in `gui/` because the arch rule allows `packaging/nx2android.py` to import only dispatch modules.

New tests: `Engine.test_replaces_copy_without_nxnative` (all OSes), `Engine.test_failed_copy_says_why_and_cleans_up` (POSIX, not root) and `Errors.test_fatal_shows_start_failure`. The two `Engine` tests fail without the fix.
**Not addressed:** the first launch still blocks the GUI's main thread during the roughly 153 MB copy. Fixing that is a design change, not a small fix.
**Status:** fixed: requires human verification (Defender retry timing on Windows)

### WR-04: `upstream-diff` is described as "a report, not a gate", but the release job needs it

**Files modified:** `.github/workflows/fork-release.yml`, `tests/test_workflows.py`
**Commit:** 5d7ec90
**Applied fix:** Added `continue-on-error: true` to the `upstream-diff` job. `needs: [build, macos, upstream-diff]` and the four-asset check are unchanged. `Release.test_write_scope` now also checks the `continue-on-error` flag. actionlint is not installed here; the YAML parses and `tests/test_workflows.py` passes.

### WR-05: The GUI's `devices` limit (15 s) is shorter than porter's own adb timeouts (30 s)

**Files modified:** `porter/procs.py`, `gui/runner.py`, `tests/test_bridge.py`, `docs/ARCHITECTURE.md`
**Commit:** 4b38014
**Applied fix:** `adb start-server` now times out after 10 s, which is safe because the next adb command starts the server itself. `TIMEOUTS['devices']` is now 45 s, above porter's worst case of 10 s + 30 s. The comments, `test_default_limits` and the `TIMEOUTS` line in `docs/ARCHITECTURE.md` were updated to match.

### WR-06: Unit tests start the developer machine's real adb server

**Files modified:** `tests/test_runlog.py`, `tests/test_bridge.py`
**Commit:** 79d7f5a
**Applied fix:** `InProcess.setUp` patches `procs.adb_server` to a no-op. `Errors.test_failed_port_shows_cause_and_log` lets the stand-in porter answer the Window's start-up one-shots, so the `devices` call never reaches real adb; the port run itself still uses the real porter. To confirm, both tests ran with a logging fake `adb` first on `PATH`: before the fix it recorded `start-server` twice and `devices -l` once, and after the fix it recorded nothing.

---

_Fixed: 2026-10-29T21:09:47Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
