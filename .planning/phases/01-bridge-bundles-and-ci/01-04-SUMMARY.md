---
phase: 01-bridge-bundles-and-ci
plan: 04
subsystem: gui
tags: [pyside6, qprocess, json-lines, golden-fixtures, timeouts]

requires:
  - phase: 01-bridge-bundles-and-ci
    provides: "01-02 one-shot {\"error\"} documents and runlog events; 01-03 _process (cwd, NX2A_GUI, own session), Porter.stop, fake_porter.py, test_bridge Errors/Stop/Close"
provides:
  - "runner.TIMEOUTS and call_json(parent, args, done, timeout=None) calling done(obj, code, fail) once; tree kill at the limit; FailedToStart handled; no callback or RuntimeError once the owner is destroyed"
  - "gui/app.py cause(fail) and failed(fail) (escaped red HTML plus a Retry link); fail-aware inspect card, device combo, SetupTab.check_msg, download list and Games note"
  - "Golden JSON-lines fixtures (port_ok, port_build_error, install_ok, edge, inspect_error) and their recorder tests/fixtures/bridge/record.py"
  - "fake_porter.py --hang, --pid-file, --fixture, escaped --stderr; test_bridge Timeout, Replay, extended Errors"
affects: [01-07 windows-2025 bridge tests, 01-08 release check, phase 3 GUI shell (reuses call_json and failed)]

actuals:
  tokens: 11600
  tasks: 3
  commits: 5
plan_head_before: bae7aaf39cec9aae544241d72c4d97101a964f1d
plan_head_after: 8c87b61c56febf0d0e7d654158c32ca1f369e223

tech-stack:
  added: []
  patterns:
    - "One-shot porter calls report done(obj, code, fail): fail is a dict {timeout, error, stderr}; the exit code alone is not a failure"
    - "Inline failures with a Retry link (href=\"retry\") in a rich-text label; the slot replaces the text before the new call, so one click is one call"
    - "Golden protocol fixtures come from porter's own emitter, scrubbed of paths, and are replayed by fake_porter --fixture"

key-files:
  created:
    - tests/fixtures/bridge/record.py
    - tests/fixtures/bridge/port_ok.jsonl
    - tests/fixtures/bridge/port_build_error.jsonl
    - tests/fixtures/bridge/install_ok.jsonl
    - tests/fixtures/bridge/edge.jsonl
    - tests/fixtures/bridge/inspect_error.json
  modified:
    - gui/runner.py
    - gui/app.py
    - tests/fixtures/bridge/fake_porter.py
    - tests/test_bridge.py
    - docs/ARCHITECTURE.md

key-decisions:
  - "01-04: a hung one-shot in the stand-in is fake_porter --hang, not --tree: --tree on one-shots would make every Fake-based Window's start-up checks hang to their limits"
  - "01-04: a one-shot whose owner widget is destroyed mid-call calls nothing and kills its own session (shiboken6.isValid guard), closing the RuntimeError handed over by 01-03"
  - "01-04: port_build_error.jsonl records a port of a missing folder, whose error is the same on every machine and names the folder; an empty folder fails on prod.keys or the tools first"

patterns-established:
  - "failed(fail): every porter-supplied string goes through html.escape(quote=False) before the Retry link is appended"
  - "Regenerate the bridge fixtures with .venv/bin/python tests/fixtures/bridge/record.py; edge.jsonl stays hand-written"

requirements-completed: [BRDG-03, BRDG-04, TEST-03]

coverage:
  - id: D1
    description: "A one-shot call is killed at its own limit with its children and reports fail['timeout']; limits are devices 15, doctor 30, inspect 60, profiles 20, tools 60"
    requirement: BRDG-03
    verification:
      - kind: integration
        ref: "tests/test_bridge.py#Timeout.test_kills_tree_at_limit"
        status: pass
      - kind: unit
        ref: "tests/test_bridge.py#Timeout.test_default_limits"
        status: pass
      - kind: integration
        ref: "tests/test_bridge.py#Errors.test_concurrent_calls"
        status: pass
    human_judgment: false
  - id: D2
    description: "The inspect card shows the timeout, error document, empty answer or stderr tail with a Retry link that starts exactly one new call; no 'No game found' for a crash"
    requirement: BRDG-04
    verification:
      - kind: automated_ui
        ref: "tests/test_bridge.py#Timeout.test_inspect_card_retry"
        status: pass
      - kind: automated_ui
        ref: "tests/test_bridge.py#Errors.test_error_document"
        status: pass
      - kind: automated_ui
        ref: "tests/test_bridge.py#Errors.test_empty_answer"
        status: pass
      - kind: automated_ui
        ref: "tests/test_bridge.py#Errors.test_undecodable_stderr"
        status: pass
    human_judgment: false
  - id: D3
    description: "Setup check, device combo, download list and Games note show the real cause of a failed call with a way to retry, and no download dialog"
    requirement: BRDG-04
    verification:
      - kind: automated_ui
        ref: "tests/test_bridge.py#Errors.test_doctor_crash_shows_stderr"
        status: pass
      - kind: automated_ui
        ref: "tests/test_bridge.py#Errors.test_devices_and_games"
        status: pass
    human_judgment: false
  - id: D4
    description: "FailedToStart and an owner destroyed mid-call (app quit) are handled: one done call, or none and no RuntimeError"
    requirement: BRDG-04
    verification:
      - kind: integration
        ref: "tests/test_bridge.py#Errors.test_failed_to_start"
        status: pass
      - kind: integration
        ref: "tests/test_bridge.py#Timeout.test_owner_gone_mid_call"
        status: pass
    human_judgment: false
  - id: D5
    description: "Golden JSON-lines replays (full port, failing port, install, edge lines) through runner.Porter give the exact event sequence and exit code; fixtures hold no user paths or key material"
    requirement: TEST-03
    verification:
      - kind: integration
        ref: "tests/test_bridge.py#Replay"
        status: pass
    human_judgment: false
  - id: D6
    description: "The inline failure text reads well in the real window (layout of the red text, the Retry link, the device combo tooltip)"
    verification: []
    human_judgment: true
    rationale: "Tests check the label text and links headless; how it looks and wraps in the real window on each host needs a person"

duration: 11min
completed: 2026-10-29
status: complete
---

# Phase 01 Plan 04: One-shot timeouts, inline failures and golden replays Summary

**One-shot porter calls now have per-command timeouts that kill the call's whole session, every view shows the real cause of a failed call inline with a Retry link, and golden JSON-lines streams from porter's own emitter pin the protocol the GUI parses.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-10-29T09:20:21Z
- **Completed:** 2026-10-29T09:31:12Z
- **Tasks:** 3
- **Files modified:** 11 (5 code, test or doc files, 6 new fixture files)

## Accomplishments
- `call_json(parent, args, done, timeout=None)` keeps stderr and calls `done(obj, code, fail)` exactly once. `fail` covers an `{"error"}` document, an empty or garbled answer, a timeout (the call's session gets SIGKILL; on Windows porter is killed and its Job Object takes the rest) and FailedToStart.
- The handed-over 01-03 issue is fixed. When the owner widget is destroyed mid-call, `call_json` calls nothing and kills the call's session instead of raising `RuntimeError`.
- `failed(fail)` turns a failure into escaped red HTML with Retry. It is used on the inspect card, in the new `SetupTab.check_msg`, in `dl_step` (replacing the dialog that blamed the network for every failure) and in the Games note. The device combo shows "porter: <cause>" with stderr as its tooltip.
- `record.py` builds `port_ok.jsonl` and `install_ok.jsonl` from upstream PROG inside `runlog.run`, and `port_build_error.jsonl` from a real failing port. `Replay` plays all four streams through `runner.Porter`, and a scrub test keeps paths and keys out of the fixtures.

## Task Commits

1. **Task 1: hung inspect shows "porter didn't answer in N s" and Retry** - `b934c0a` (feat, tracer; its gate ran the automated verify again and it passed)
2. **Task 2: devices, Setup check, download list, Games show the cause**: RED `d735cba` (test), GREEN `3c08b0c` (feat)
3. **Task 3: golden JSON-lines replays (TEST-03)** - `18aa2a6` (test)
4. **Docs:** `8c87b61` (docs: ARCHITECTURE.md protocol section)

**Plan metadata:** this SUMMARY's commit (docs: complete plan)

## Files Created/Modified
- `gui/runner.py`: `TIMEOUTS`, `_kill_tree`, and the rewritten `call_json` (timer, stderr tail, fail dict, FailedToStart, the destroyed-owner guard)
- `gui/app.py`: `cause()`, `failed()`, the card's Retry link, and fail-aware `on_inspect`, `refresh_devices.got`, `SetupTab.check_msg`/`check.got`, `confirm_download`, the `dl_step` retry route and `GamesTab.load`/`got`
- `tests/fixtures/bridge/fake_porter.py`: new `--hang`, `--pid-file` and `--fixture` options; `--stderr` takes `\n`/`\xff` escapes; one-shots answer `[]` only when the exit code is 0
- `tests/fixtures/bridge/record.py`: regenerates the three recorded fixtures with paths scrubbed
- `tests/fixtures/bridge/{port_ok,port_build_error,install_ok,edge}.jsonl`, `inspect_error.json`: the golden inputs
- `tests/test_bridge.py`: `Timeout` (4 tests), `Replay` (5) and 7 new `Errors` tests
- `docs/ARCHITECTURE.md`: the one-shot timeouts, the inline failures and the replays

## Decisions Made
- A hung one-shot in the stand-in comes from `--hang`. Putting `--tree` on one-shots would also apply to every `Fake`-based Window's start-up checks.
- `port_build_error.jsonl` records a port of a missing folder. That error is the same on every machine and names the folder. An empty folder fails first on prod.keys or on whichever tools the machine is missing.
- `cause()` puts the error in one line for the device combo. For a stderr-only failure it uses stderr's last line, while `failed()` titles it "porter failed" and shows the tail below.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `--tree` on one-shots hung every stand-in Window**
- **Found during:** Task 1 (full bridge suite)
- **Issue:** The plan had `--tree` also hold one-shots. `Fake.setUp` uses `--tree` for all its tests, so each Window's doctor, devices and profiles hung to their limits and the suite ran past two minutes.
- **Fix:** I added a separate `--hang` option. A plain `--tree` one-shot still answers `[]`.
- **Files modified:** tests/fixtures/bridge/fake_porter.py, tests/test_bridge.py
- **Verification:** The full `tests.test_bridge` suite runs in about 6 s.
- **Committed in:** b934c0a

**2. [Rule 2 - Missing critical] RuntimeError when the owner is destroyed mid-call**
- **Found during:** Task 1 (handed over by 01-03)
- **Fix:** A `shiboken6.isValid` guard: no `done` call, and the call's session is killed. Covered by `Timeout.test_owner_gone_mid_call`, which patches `sys.excepthook` and fails at HEAD's `call_json`. I reproduced that failure before the fix.
- **Committed in:** b934c0a

**3. [Rule 1 - Bug] `port_build_error.jsonl` would not name the folder**
- **Found during:** Task 3
- **Issue:** A port of an empty folder with an empty NX2A_HOME fails on prod.keys, which never names the folder, so the `<folder>` acceptance check could not pass. Supplying keys moves the failure to the machine-dependent tools check.
- **Fix:** The recorder ports `<tmp>/missing`, whose "not a folder: <folder>/missing" error is the same on every machine. The scrub now replaces the longer of `/var/...` and `/private/var/...` first.
- **Committed in:** 18aa2a6

**4. [Rule 1 - Bug] Scrub rule flagged porter's own error text**
- **Found during:** Task 3
- **Issue:** The rule `prod.keys` followed by `:` and any text matched "no prod.keys: give -k".
- **Fix:** The rule now needs hex after `prod.keys =`/`:`. The 32-hex rule still catches key values.
- **Committed in:** 18aa2a6

---

**Total deviations:** 4 auto-fixed (3 bugs, 1 missing critical).
**Impact on plan:** All four were needed for correctness or for the tests to be useful. Nothing was added beyond the plan's scope.

## TDD Gate Compliance
- Task 2: the RED commit `d735cba` came before the GREEN commit `3c08b0c`. `gsd-tools check tdd-red-evidence` returned RED_EVIDENCE_OK (target_test_failed) for `test_doctor_crash_shows_stderr` and `test_devices_and_games`. Semantic check: both ran and failed on their first assertion about the new view behaviour ("SetupTab has no check_msg"; the combo still read "no device connected"). There was no load or import error. The evidence is in `.red/01-04-*.json`. The other new Errors tests (error document, empty answer, undecodable stderr, FailedToStart, concurrency) already passed at RED, because they exercise the `call_json` contract that Task 1 built.
- Task 3 adds tests and fixtures only, with no production code, so it has no GREEN step. It is one `test(01-04)` commit.

## Issues Encountered
- While writing my RED evidence I moved `.planning/.../.red/` aside, which took the two tracked 01-05 evidence files with it. I restored both with `git checkout -- <file>` before any commit, and no commit contains the deletion.

## User Setup Required
None.

## Next Phase Readiness
- 01-07 can run `tests.test_bridge` (Timeout and Replay included) on windows-2025. Not run in this session: the Windows timeout kill (`p.kill()` plus porter's Job Object for one-shots).
- A child process that outlives porter after a one-shot timeout on Windows is not covered by a test; on POSIX the session kill is tested.

---
*Phase: 01-bridge-bundles-and-ci*
*Completed: 2026-10-29*

## Self-Check: PASSED
- All 10 key files exist; commits b934c0a, d735cba, 3c08b0c, 18aa2a6 and 8c87b61 are ancestors of HEAD.
- Plan verification: `tests.test_bridge tests.test_runlog tests.test_architecture` ran 46 tests, OK; `tests/arch_rules.py` reported "all checks passed".
