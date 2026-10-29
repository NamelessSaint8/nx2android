---
phase: 01-bridge-bundles-and-ci
plan: 02
subsystem: infra
tags: [porter, run-log, json-protocol, process-tree, job-object, sigterm, msbuild]

requires:
  - phase: 01-bridge-bundles-and-ci
    provides: "01-01 hashed dependency locks in .venv (lz4, capstone for the tests); 01-05 porter.paths.REPO / user_dir"
provides:
  - "porter/runlog.py: run(a, fn), build_folder(work, logs), cut_off(), reset(), MARKER = '.port-running', LOGS_KEPT = 30"
  - "porter/procs.py: setup(a, on_stop), adb_server(), _job(), _watch(job, on_stop), _term()"
  - "Protocol (additive): {ev: log, path} first; {ev: error, msg, type, log} on failure; log on result; one-shot {error: '<Type>: <message>'}"
  - "NX2A_GUI=1 stop channel: SIGTERM to the group (POSIX), 'stop' or EOF on stdin (all OSes) -> exit 130, log records 'cancelled during <stage>'"
  - "MSBuild env set by every run; -nodeReuse:false on the translator's dotnet build"
affects: [01-03 gui runner stop and Open log, 01-04 one-shot errors and timeouts, 01-07 windows-2025 Stop tests, Phase 2 HARD-05 per-stage stamps replace the marker]

actuals:
  tokens: 6627
  tasks: 3
  commits: 5
plan_head_before: 8d17efb37619b34def5a6df9eb3f2c62fc7672d9
plan_head_after: 9cfb3ec573fc161c45c3ae95db8b940dc62ce6d4

tech-stack:
  added: []
  patterns:
    - "Instance-attribute wrappers on upstream PROG (stage/end/say/_json) mirror every mode into the log; unwrapped after the run"
    - "New logic in new porter modules; porter/cli.py and porter/pipeline.py get hook lines only"
    - "Stop driver tests run in their own session (start_new_session) because the watcher signals its own process group"

key-files:
  created:
    - porter/runlog.py
    - porter/procs.py
    - tests/test_runlog.py
  modified:
    - porter/cli.py
    - porter/pipeline.py
    - docs/ARCHITECTURE.md

key-decisions:
  - "The error and log events are printed by runlog itself (not through PROG._json), so a run whose porter.upstream import fails still names its log and reports the error"
  - "A KeyboardInterrupt that arrives before _with_progress takes over (during imports) is also exit 130 with the cut-off line"
  - "The cut-off key sweep walks the build folder with os.walk and prunes the top-level extract/ folder, so it never walks or touches the extracted RomFS"
  - "LOGS_KEPT = 30 counts the new log: 29 old logs stay beside it"
  - "procs.setup returns a note ('Windows job: not available (...)') that runlog writes into the log; porter keeps running without the job"

patterns-established:
  - "Run log lines: '[hh:mm:ss] [k/n] stage · step', '[hh:mm:ss] ✓/✗ [k/n] stage (m:ss): summary', say lines verbatim, then 'done'/'failed'/'[RED] cancelled during <stage>', 'ended after N s', 'per-tool logs: <path>'"

requirements-completed: [BRDG-01, BRDG-03, BRDG-05]

coverage:
  - id: D1
    description: "Every long run writes a readable log under <user dir>/logs; its path is the first JSON event, failures end with an error event"
    requirement: BRDG-03
    verification:
      - kind: integration
        ref: "tests/test_runlog.py#RunLog.test_port_error_has_log_and_error_event"
        status: pass
      - kind: integration
        ref: "tests/test_runlog.py#RunLog.test_cli_run_writes_log_too"
        status: pass
      - kind: unit
        ref: "tests/test_runlog.py#RunLogInProcess.test_traceback_in_log"
        status: pass
      - kind: unit
        ref: "tests/test_runlog.py#RunLogInProcess.test_tool_logs_listed"
        status: pass
      - kind: integration
        ref: "tests/test_runlog.py#RunLogInProcess.test_no_key_material"
        status: pass
    human_judgment: false
  - id: D2
    description: "A crashing one-shot --json command answers {\"error\": \"<Type>: <message>\"}, traceback on stderr, exit 1"
    requirement: BRDG-03
    verification:
      - kind: integration
        ref: "tests/test_runlog.py#OneShot.test_broken_import_is_a_json_error"
        status: pass
    human_judgment: false
  - id: D3
    description: "Under NX2A_GUI=1 porter stops as one tree with exit 130 (POSIX: SIGTERM, stdin stop, EOF; grandchild dies); CLI runs install no watcher; MSBuild env set"
    requirement: BRDG-01
    verification:
      - kind: integration
        ref: "tests/test_runlog.py#Stop (6 tests, macOS)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Windows Job Object path (kill-on-close, TerminateJobObject 130) and adb server surviving a stop"
    requirement: BRDG-01
    verification: []
    human_judgment: true
    rationale: "Written but not run: no Windows host in this session. Plan 01-07 runs the Stop tests on windows-2025; adb server survival needs a real adb"
  - id: D5
    description: "The .port-running marker forces every cached stage to redo after a cut-off port; the newest 30 logs are kept"
    requirement: BRDG-05
    verification:
      - kind: unit
        ref: "tests/test_runlog.py#Marker.test_written_and_removed_on_success"
        status: pass
      - kind: unit
        ref: "tests/test_runlog.py#Marker.test_cut_off_redoes_stages"
        status: pass
      - kind: unit
        ref: "tests/test_runlog.py#Retention.test_keeps_newest_30"
        status: pass
    human_judgment: false

duration: 7min
completed: 2026-10-29
status: complete
---

# Phase 1 Plan 02: Run Log, Error Events and Stop Channel Summary

**Porter writes a readable log of every port, install and tool download to `<user dir>/logs`, names it in the first JSON event, reports failures as `error` events, stops as one process tree with exit 130 under `NX2A_GUI=1` (session signal on POSIX, stdin `stop` plus a kill-on-close Job Object on Windows), and redoes every cached stage after a cut-off port**

## Performance

- **Duration:** 7 min
- **Started:** 2026-10-29T08:45:43Z
- **Completed:** 2026-10-29T08:53:12Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments
- `porter/runlog.py`: one dispatch point for every command. Long runs get a line-buffered UTF-8 log with the argv header, version, platform, stage and say lines, tracebacks and the per-tool log folder. The protocol gains `log`, `error` and `result.log`. A crashing one-shot `--json` command now prints a JSON error, so a missing `lz4` no longer looks like a network failure.
- `porter/procs.py`: the MSBuild env is set for every run, `adb start-server` runs before the tree is fenced, and under `NX2A_GUI=1` there is a SIGTERM handler (POSIX), an `os.read(0)` stdin watcher (all OSes, EOF counts as a stop) and a Windows Job Object with typed ctypes signatures.
- D-08 marker: `<tid>_build/.port-running` is set when `inputs()` makes the build folder and removed on a clean or reported end. If a port finds it, every stage `*.key` outside `extract/` is deleted. Log retention keeps the newest 30.
- `docs/ARCHITECTURE.md` documents the additive protocol, the stop channel, the logs folder and the marker.

## Task Commits

1. **Task 1: failing port writes its log, announces it first, ends with an error event** - `477fb07` (feat, tracer)
2. **Task 2: stop channel, Job Object, adb outside the tree, MSBuild env** - `b68d8da` (test, RED), `6f87a1a` (feat, GREEN)
3. **Task 3: cut-off marker, retention, traceback and per-tool logs, docs** - `15865bd` (test, RED), `9cfb3ec` (feat, GREEN)

## TDD Gate Compliance

- Task 2 RED: target `tests.test_runlog.Stop.test_sigterm_to_group` failed with `-15 != 130`. With no SIGTERM handler, the driver died of the signal. The classifier verdict was `RED_EVIDENCE_OK`. Semantic check: the target ran and failed on the planned exit-code assertion. The `procs` ImportError and the 10 s timeouts in the sibling tests come from the same missing module.
- Task 3 RED: target `tests.test_runlog.Retention.test_keeps_newest_30` failed with `36 != 30` because nothing pruned yet. The classifier verdict was `RED_EVIDENCE_OK`. Semantic check: the target failed on the planned count assertion. The Marker and tool-log tests errored on the missing `build_folder`. `test_no_key_material` and `test_traceback_in_log` already passed because Task 1 covered them.
- Both GREEN commits follow their RED commits. No REFACTOR commit was needed.

## Files Created/Modified
- `porter/runlog.py` - run log, protocol events, one-shot JSON errors, D-08 marker, retention
- `porter/procs.py` - stop channel, Windows Job Object, adb server start, MSBuild env
- `tests/test_runlog.py` - RunLog, RunLogInProcess, OneShot, Stop, Marker, Retention (15 tests)
- `porter/cli.py` - `main()` dispatches through `runlog.run` (+2/-1)
- `porter/pipeline.py` - `runlog.build_folder` hook in `inputs()`, `-nodeReuse:false` on the translator build (+2/-1)
- `docs/ARCHITECTURE.md` - protocol additions, stop channel, `logs/` in the player's folder

## Decisions Made
See `key-decisions` in the frontmatter. In short: runlog prints its own `log` and `error` events, so a broken `porter.upstream` import is still reported. A stop during imports also ends with exit 130. The key sweep never walks the extracted RomFS. "Keep 30" counts the new log.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Retention test arithmetic**
- **Found during:** Task 3 (GREEN)
- **Issue:** The plan's behaviour says "35 old logs, a new run leaves 30 files including the new one, and the 5 oldest gone". That is impossible: 35 - 5 + 1 = 31.
- **Fix:** Kept the rule the truths state (at most 30 logs, the new one included), so 6 old logs go. The test asserts that `000006` is the oldest log left.
- **Files modified:** tests/test_runlog.py
- **Verification:** `Retention.test_keeps_newest_30` passes.
- **Committed in:** 9cfb3ec

**2. [Rule 1 - Bug] Nested stdout capture in test_traceback_in_log**
- **Found during:** Task 3 (RED)
- **Issue:** The helper's own `redirect_stdout` swallowed the error event the test wanted to see.
- **Fix:** The test calls `runlog.run` directly under a single redirect.
- **Files modified:** tests/test_runlog.py
- **Committed in:** 15865bd (before the RED commit)

---

**Total deviations:** 2 auto-fixed (2 bugs, both in tests).
**Impact on plan:** None on the shipped behaviour.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- 01-03 can use `NX2A_GUI=1`, start porter in a new session, send `stop\n` or SIGTERM, read the `log` and `error` events, and open the log.
- 01-04 can rely on the `{"error": ...}` document from one-shot commands.
- The Windows Job Object and the adb-survives-stop path have not been run. Plan 01-07 runs the Stop tests on windows-2025.

---
*Phase: 01-bridge-bundles-and-ci*
*Completed: 2026-10-29*

## Self-Check: PASSED
- Files: porter/runlog.py, porter/procs.py and tests/test_runlog.py are on disk.
- Commits 477fb07, b68d8da, 6f87a1a, 15865bd and 9cfb3ec are ancestors of HEAD.
- Acceptance greps: `runlog.run(a,` 1, `nodeReuse:false` 1, `runlog.build_folder(self.work, self.logs)` 1, Job Object constant 1, `os.read(0` 1, `restype` 6. `NX2A_GUI` and `port-running` are both in ARCHITECTURE.md. The cli.py and pipeline.py diffs are each +2/-1.
- Verification: `tests.test_runlog` passes (15 tests). `arch_rules.py` reports all checks passed. The full suite (`QT_QPA_PLATFORM=offscreen`) ran 55 tests: OK, 1 skipped.
