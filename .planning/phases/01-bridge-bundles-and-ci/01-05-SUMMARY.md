---
phase: 01-bridge-bundles-and-ci
plan: 05
subsystem: infra
tags: [pyinstaller, frozen, macos-app, read-only-bundle, porter-paths]

requires: []
provides:
  - "porter.paths.FROZEN and a per-layout resource root (REPO = Contents/Resources in a macOS .app, the executable's folder elsewhere)"
  - "porter.paths._engine(): writable per-version engine copy at <user dir>/engine/<ENGINE id>/nxnative, race-safe, prunes other versions"
  - "packaging/nx2android.py main() sets sys.dont_write_bytecode = True"
  - "tests/test_paths.py: Engine (7) and Launcher (1) tests on read-only fake bundles"
affects: [01-06 build_bundle ENGINE file, 01-03 gui runner cwd, PKG-05 manual RO check]

actuals:
  tokens: 2600
  tasks: 2
  commits: 3
plan_head_before: 50839545a7cd078764d455ddb408989b01d0cd7d
plan_head_after: 6b190f920b969774c409674a406d81bcd6589134

tech-stack:
  added: []
  patterns:
    - "Copy aside to <id>.tmp-<pid>, then one os.rename; the race loser deletes its temp"
    - "Frozen-layout tests: subprocess sets sys.frozen/executable/platform before importing porter.paths"

key-files:
  created:
    - tests/test_paths.py
  modified:
    - porter/paths.py
    - packaging/nx2android.py

key-decisions:
  - "An ENGINE file that is missing, empty or not alphanumeric falls back to <resource root>/nxnative (a bundle from before the copy existed)"
  - "Other engine versions are pruned only by the start that put its own copy in place, so a running older bundle is not pulled out from under it on every start"
  - "The copy walk adds owner-write to every non-symlink entry, since copytree/copystat keep a DMG's or chmod a-w bundle's read-only modes"

patterns-established:
  - "Frozen porter never writes under REPO; engine writes go to user_dir()/engine/<id>"

requirements-completed: [PKG-05]

coverage:
  - id: D1
    description: "Frozen macOS .app reads resources from Contents/Resources, plain bundle from the executable's folder, checkout unchanged"
    requirement: PKG-05
    verification:
      - kind: unit
        ref: "tests/test_paths.py#Engine.test_macos_layout"
        status: pass
      - kind: unit
        ref: "tests/test_paths.py#Engine.test_plain_layout"
        status: pass
      - kind: unit
        ref: "tests/test_paths.py#Engine.test_checkout_unchanged"
        status: pass
      - kind: unit
        ref: "tests/test_paths.py#Engine.test_missing_engine_id"
        status: pass
    human_judgment: false
  - id: D2
    description: "Writable per-version engine copy, resource listing unchanged, safe concurrent first starts, reuse on second start, old versions pruned"
    requirement: PKG-05
    verification:
      - kind: unit
        ref: "tests/test_paths.py#Engine.test_concurrent_first_start"
        status: pass
      - kind: unit
        ref: "tests/test_paths.py#Engine.test_second_start_reuses"
        status: pass
      - kind: unit
        ref: "tests/test_paths.py#Engine.test_prunes_other_versions"
        status: pass
    human_judgment: false
  - id: D3
    description: "Launcher sets sys.dont_write_bytecode before dispatching"
    requirement: PKG-05
    verification:
      - kind: unit
        ref: "tests/test_paths.py#Launcher.test_no_bytecode_flag"
        status: pass
      - kind: other
        ref: "python3 tests/arch_rules.py (PASS packaging/nx2android.py only dispatches)"
        status: pass
    human_judgment: false
  - id: D4
    description: "A full port from a read-only signed .app leaves codesign --verify --deep --strict passing"
    requirement: PKG-05
    verification: []
    human_judgment: true
    rationale: "Needs a real bundle (plan 01-06), game files and keys; CI has none. Planned as the 01-06 manual check."

duration: 3min
completed: 2026-10-29
status: complete
---

# Phase 01 Plan 05: Read-only bundle and engine copy Summary

**Frozen porter reads Contents/Resources (macOS) or the exe folder as a read-only root and builds from a race-safe, per-version writable copy of nxnative in <user dir>/engine/<ENGINE id>; the launcher turns bytecode off.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-10-29T08:39:36Z
- **Completed:** 2026-10-29T08:42:23Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- `porter/paths.py`: `FROZEN`; `REPO` per layout; `NXNATIVE = _engine()` when frozen. Importers (`porter/upstream.py`, `porter/pipeline.py`) did not change.
- `_engine()` copies into `<id>.tmp-<pid>`, makes the copy owner-writable, then does a single `os.rename`. The loser of a race deletes its temp folder. Copies of other versions are pruned, and a same-id temp folder is left alone.
- `packaging/nx2android.py` `main()` now starts with `sys.dont_write_bytecode = True`, with no new import.
- `tests/test_paths.py`: 8 stdlib-only tests on chmod a-w fake bundles. They check the resource listing (path, size, mtime_ns) stays the same.

## Task Commits

1. **Task 1: read-only resource root and engine copy (tracer)** - `2a3472e` (feat)
2. **Task 2 RED: pruning, concurrency, reuse, bytecode tests** - `4f0b50f` (test)
3. **Task 2 GREEN: prune other versions, launcher bytecode flag** - `6b190f9` (feat)

No REFACTOR was needed.

## TDD Gate Compliance

- RED: `NO_COLOR=1 python3 -m unittest tests.test_paths -v` exited 1 with 8 tests, 2 failing. `gsd-tools check tdd-red-evidence` returned `RED_EVIDENCE_OK` for both targets (records in `.planning/phases/01-bridge-bundles-and-ci/.red/`).
  - `Engine.test_prunes_other_versions` failed on its assertion (`old999` still present). That is the planned behaviour gap. semanticAssessment: valid RED.
  - `Launcher.test_no_bytecode_flag` failed on its assertion (main's first statement was `multiprocessing.freeze_support()`). semanticAssessment: valid RED.
  - `test_concurrent_first_start` and `test_second_start_reuses` already passed at RED. Task 1's action specified the rename-race handling and the reuse check, so they guard behaviour that already existed.
- GREEN: all 8 pass, full suite 40 OK (1 skipped), arch rules all passed. The concurrent test passed 5 out of 5 repeated runs.

## Files Created/Modified
- `porter/paths.py` - resource root per layout, `FROZEN`, `_engine()` copy and prune
- `packaging/nx2android.py` - `sys.dont_write_bytecode = True` in `main()`
- `tests/test_paths.py` - `Engine` and `Launcher` test classes

## Decisions Made
- An ENGINE id must be alphanumeric. If it is missing, empty or malformed, porter falls back to the bundle's own nxnative, which is the plan's case for an older bundle.
- Pruning runs only on the start that installs a copy, not on every start, so fewer older-bundle copies get deleted while still in use.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## Known Stubs
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 01-06 must write `<resource root>/ENGINE`, holding one alphanumeric line (16 hex), and `<resource root>/nxnative/`.
- Plan 01-03's runner cwd change pairs with this.
- Still open (RESEARCH A8 / Pitfall 8): the space in `~/Library/Application Support` in the engine path. Only a real port from the bundle can show whether it breaks anything.

---
*Phase: 01-bridge-bundles-and-ci*
*Completed: 2026-10-29*

## Self-Check: PASSED
