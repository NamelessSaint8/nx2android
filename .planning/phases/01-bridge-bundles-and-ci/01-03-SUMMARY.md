---
phase: 01-bridge-bundles-and-ci
plan: 03
subsystem: gui
tags: [gui, qprocess, cancel, process-group, close-confirmation, run-log, pyside6]

requires:
  - phase: 01-bridge-bundles-and-ci
    provides: "01-02 porter side of the bridge: NX2A_GUI stop channel (SIGTERM / stdin stop / EOF -> 130), ev:log first, ev:error, result.log; 01-05 paths.user_dir / FROZEN"
provides:
  - "gui/runner.py: PORTER, GRACE_MS, _process(parent, args), _alive(pgid), Porter.stop()/_force()/_reap()/_kill(), Porter.pgid/stopping/ended; Porter.cancel() removed"
  - "Every porter (long and one-shot) runs from the player's folder, NX2A_GUI=1, PYTHONPATH=checkout when not frozen, POSIX new session"
  - "gui/app.py: PortTab.log_btn/open_log/log_path/error/args, stopping… state; Window.quitting/runs/run_ended/ask_stop/closeEvent; SetupTab inline download error with Open log link"
  - "tests/fixtures/bridge/fake_porter.py stand-in (--tree, --ignore-stop, --exit, --stderr; one-shots print [])"
  - "tests/test_bridge.py: Errors (2), Stop (6), Close (6)"
affects: [01-04 call_json timeouts and one-shot errors, 01-07 windows-2025 bridge tests, 01-08 RELEASE_CHECK per-host cancel check]

actuals:
  tokens: 8828
  tasks: 3
  commits: 6
plan_head_before: c8c35e461d8e3267ef0bee7058f3b108797344d6
plan_head_after: 810da2427ffe4eb44e42ae8c8806174034c18386

tech-stack:
  added: []
  patterns:
    - "Per-run token: timers and QProcess slots capture the QProcess they belong to and do nothing once it is not self.p or the run has ended (no signal to a reused group id)"
    - "Porter.running() means 'not ended': true from start() until finished, including the POSIX reap of a session that outlives porter"
    - "Test windows wait for their start-up one-shots before and after the test, so no QProcess is destroyed mid-call"

key-files:
  created:
    - tests/test_bridge.py
    - tests/fixtures/bridge/fake_porter.py
  modified:
    - gui/runner.py
    - gui/app.py
    - docs/ARCHITECTURE.md

key-decisions:
  - "Porter._kill never signals a pgid <= 1; stop() before started falls back to QProcess.kill, so the GUI's own group (killpg(0)) can never be hit"
  - "A stopped run that ends by a signal (CrashExit) reports 130 even when its exit code reads 0; an unstopped CrashExit with code 0 reports -1"
  - "A failed or cancelled download shows 'cancelled' for 130 and the escaped cause plus an Open log link otherwise; dl_step goes back to plain text when a download starts"
  - "test_bridge sets NX2A_HOME in setUpModule, not at import: test_porter sets its own at import during discovery"

patterns-established:
  - "GUI status line takes the error event's msg, else the last [RED] say line; it is Qt.PlainText"

requirements-completed: [BRDG-02, BRDG-05, BRDG-06]

coverage:
  - id: D1
    description: "A failed port shows its cause in the status line and Open log opens the saved log; porter runs from the player's folder with NX2A_GUI=1"
    requirement: BRDG-05
    verification:
      - kind: integration
        ref: "tests/test_bridge.py#Errors.test_failed_port_shows_cause_and_log"
        status: pass
      - kind: integration
        ref: "tests/test_bridge.py#Errors.test_process_env"
        status: pass
    human_judgment: false
  - id: D2
    description: "Cancel stops the whole session, keeps detached processes, forces after the grace period, and finished (cancelled) only after the tree is gone; idle and after-exit stop are no-ops; events precede finished"
    requirement: BRDG-06
    verification:
      - kind: integration
        ref: "tests/test_bridge.py#Stop (6 tests, macOS)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Closing the window mid-port, mid-install or mid-download asks Stop and quit / Keep running; Stop and quit stops and closes once nothing runs; failed downloads show inline"
    requirement: BRDG-02
    verification:
      - kind: integration
        ref: "tests/test_bridge.py#Close (6 tests)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Real port cancelled mid shader/host stage on all four hosts leaves no dotnet/clang/MSBuild and the adb server up; Windows stop path"
    requirement: BRDG-01
    verification: []
    human_judgment: true
    rationale: "Needs a real port and device per host; the Windows path runs on windows-2025 in plan 01-07, the per-host check goes into docs/RELEASE_CHECK.md (plan 01-08)"

duration: 10min
completed: 2026-10-29
status: complete
---

# Phase 1 Plan 03: GUI Stop, Open Log and Close Confirmation Summary

**The GUI now runs every porter from the player's folder in its own session with `NX2A_GUI=1`. A failed run shows its real cause in the status line with an Open log button. Cancel and Stop and quit send SIGTERM to the session (or a `stop` line on Windows), force-kill after 5 s, and say "cancelled" only once nothing of the run is left. A failed tool download shows its cause inline instead of in a dialog.**

## Performance

- **Duration:** about 10 min
- **Started:** 2026-10-29T09:06Z
- **Completed:** 2026-10-29T09:17Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments
- `gui/runner.py`: `_process()` is the only place a porter QProcess is built. It runs `[*PORTER, *args]` from `paths.user_dir()`, with `NX2A_GUI=1`, `PYTHONPATH` set to the checkout when not frozen, and `CreateNewSession` on POSIX. `Porter.stop()`, `_force()` and `_reap()` replace `cancel()`. `finished` waits for porter's exit and, on POSIX, an empty session, and is emitted exactly once. `FailedToStart` becomes an error event plus `finished(-1)`.
- `gui/app.py`, hook lines only: the Open log button, the `log`/`error` event branches, `failed after X: <cause>`, `stopping…` with Cancel greyed out, `cancelled` after finished, `Window.closeEvent` with `ask_stop(installing)` as the test seam, and the inline download error with an Open log link.
- `tests/fixtures/bridge/fake_porter.py` calls the real `porter.procs.setup`. It holds one child inside the tree and one detached process outside it.
- `docs/ARCHITECTURE.md`: one bullet on the GUI side of the stop channel.

## Task Commits

1. **Task 1: failing port shows its cause, Open log** - `76548d0` (feat, tracer)
2. **Task 2: Cancel stops the tree, cancelled after it is gone** - `9341afb` (test, RED), `7234ce1` (feat, GREEN)
3. **Task 3: close confirmation, inline download errors** - `3a4614e` (test, RED), `2bd5ec9` (feat, GREEN)
4. **Docs:** `810da24` (ARCHITECTURE.md)

## TDD Gate Compliance

- Task 2 RED: the target `tests.test_bridge.Stop.test_port_tab_status` failed with `'[1/1] waiting' != 'stopping…'`. The classifier returned `RED_EVIDENCE_OK` (target_test_failed). Semantic check: the target ran a real stand-in tree and failed on the planned status assertion. The other five Stop tests errored on the missing `Porter.stop`. An earlier run was INVALID_RED: every test errored in `setUp` on the missing `GRACE_MS`. It was not committed. `setUp` was made tolerant and the tests were run again.
- Task 3 RED: the target `tests.test_bridge.Close.test_stop_and_quit` failed with `True is not false`, because the window closed at once during a port. The classifier returned `RED_EVIDENCE_OK`. Semantic check: this is the planned close-return assertion. The sibling Close tests failed on their own planned assertions. `test_idle_close_quits` already passed, as expected.
- Both GREEN commits follow their RED commits. No REFACTOR commit was needed.

## Decisions Made
See `key-decisions` in the frontmatter.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Force-killed run reported as success**
- **Found during:** Task 2 (GREEN)
- **Issue:** The plan maps a stopped run's code to 130 only when `code != 0`. A run that dies by a signal can report CrashExit with exit code 0, so a force-killed run would read as done.
- **Fix:** A stopped run reports 130 when `code != 0` or the status is CrashExit.
- **Files modified:** gui/runner.py
- **Commit:** 7234ce1

**2. [Rule 2 - Critical] No signal to group 0 or a stale group**
- **Found during:** Task 2
- **Issue:** `stop()` pressed before `started` would call `killpg(0, …)`, which signals the GUI's own group. A grace timer firing after `finished` could also signal a pgid that has been reused.
- **Fix:** `_kill` ignores pgid <= 1. `stop()` falls back to `QProcess.kill()` before start. `_force` and `_reap` check the run token and `ended` (T-1-09).
- **Commit:** 7234ce1

**3. [Rule 1 - Bug] Test isolation**
- **Found during:** Task 3 (full-suite run)
- **Issue:** `test_porter` sets `NX2A_HOME` at import, which overrode the value `test_bridge` set at import. Windows that were destroyed while their start-up one-shots ran printed `RuntimeError` tracebacks from `call_json`.
- **Fix:** `NX2A_HOME` is now set in `setUpModule`. Test windows wait for their one-shots before and after each test.
- **Commit:** 2bd5ec9

---

**Total deviations:** 3 auto-fixed.
**Impact on plan:** None on scope. The fixes make the stop safer.

## Issues Encountered
- `call_json`'s `fin` reads stdout from a QProcess that is being destroyed when its parent goes away mid-call, which raises a `RuntimeError` on stderr. The tests avoid it, but a real app quit during a one-shot could still print it. Plan 01-04 rewrites `call_json` and should guard this.

## User Setup Required
None.

## Next Phase Readiness
- 01-04 can change the `call_json` contract. It already runs through `_process`, so it has the new cwd, environment and session.
- Not run in this session: the Windows stop path (stdin `stop`, `taskkill` fallback, kill-on-close job), the check that the adb server survives a stop, and a real port cancelled mid-stage. These are for plan 01-07 (windows-2025) and the per-host human check in plan 01-08.

---
*Phase: 01-bridge-bundles-and-ci*
*Completed: 2026-10-29*

## Self-Check: PASSED
- Files: gui/runner.py, gui/app.py, tests/test_bridge.py and tests/fixtures/bridge/fake_porter.py are on disk.
- Commits 76548d0, 9341afb, 7234ce1, 3a4614e, 2bd5ec9 and 810da24 are ancestors of HEAD.
- Acceptance greps: `PORTER = ['-m', 'porter']` 1, `user_dir()` 1, `setUnixProcessParameters` 1, `Open log` present, `the log says why` 0, `GRACE_MS` 5, `def stop` 1, `def cancel` 0, `stopping` present, `self.porter.stop()` 1, `def closeEvent` 1, `Stop and quit` and `Keep running` present, `half-installed` 1, `QMessageBox.warning(self, 'Download'` 1.
- Verification: `tests.test_bridge` passes (14 tests, three runs in a row). `arch_rules.py` reports all checks passed. The full suite (`QT_QPA_PLATFORM=offscreen`) ran 74 tests: OK, 1 skipped.
