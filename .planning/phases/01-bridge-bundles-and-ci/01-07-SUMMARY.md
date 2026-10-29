---
phase: 01-bridge-bundles-and-ci
plan: 07
subsystem: ci
tags: [github-actions, matrix, unittest, pyside6, python-floor]
status: complete

requires:
  - phase: 01-bridge-bundles-and-ci
    provides: "01-01 hashed lock; 01-02/01-03 Windows Job Object and stdin stop; 01-04 bridge tests and golden fixtures"
provides:
  - ".github/workflows/fork-ci.yml: the whole suite on windows-2025, macos-15, ubuntu-22.04, ubuntu-24.04-arm (3.14) and ubuntu-22.04 (3.11 CLI floor), from the hashed lock, headless"
  - "tests/test_workflows.py class Ci: read-only token, SHA-pinned actions, no credentials, no expressions in run scripts, concurrency, fail-fast off, the matrix"
  - "TEST-02 guard: a missing optional module skips outside CI and fails in CI"
  - "The GUI floor: Python 3.12+ (python -m gui exits with a [RED] line on 3.11); the CLI keeps 3.11"
affects: [01-08 release workflow (held to the same Ci rules), phase 3 GUI shell (3.12+)]

actuals:
  tokens: 4741
  tasks: 3
  commits: 6
plan_head_before: b38b9e43d0ce5cb8f250fc28e6a0094d03c4cb79
plan_head_after: ed1d2ee0a1007a4d3e46fbcdf3feb68f94d93828

tech-stack:
  added: []
  patterns:
    - "A declared version floor skips in CI too; a missing module from the lock fails in CI"
    - "Every gh run call names -R NamelessSaint8/nx2android (gh defaults to upstream)"

key-files:
  created:
    - .github/workflows/fork-ci.yml
  modified:
    - tests/test_workflows.py
    - tests/test_porter.py
    - tests/test_perf_adaptive.py
    - tests/test_bridge.py
    - porter/pipeline.py
    - porter/procs.py
    - gui/__main__.py
    - requirements.in
    - requirements.txt
    - README.md
    - docs/ARCHITECTURE.md

key-decisions:
  - "The GUI needs Python 3.12+; the CLI keeps 3.11+ (user decision, option C). PySide6-Essentials 6.12 stays the only Qt pin, with a python_version >= 3.12 marker; one universal lock"

metrics:
  duration: "two fix rounds after the first run"
  completed: 2026-10-29
---

# Phase 01 Plan 07: fork-ci on four hosts Summary

fork-ci.yml runs the whole suite from the hashed lock on Windows, macOS, Linux x64 and Linux arm64 with Python 3.14, plus the Python 3.11 CLI floor. All five jobs are green for ed1d2ee (run 40907463731). The GUI now declares a Python 3.12 floor, because PySide6 6.12 aborts 3.11.

## Tasks

| Task | Name | Commit |
| ---- | ---- | ------ |
| 1 | fork-ci.yml on four hosts, its rules as tests, and the TEST-02 skip | a3da49d |
| 2 | Authorise pushing main to origin | none (checkpoint; the user authorised it) |
| 3 | Make fork-ci green on all five jobs, round 1: an f-string 3.11 cannot parse | 69911a6 |
| 3 | Round 1: a Windows stop prints [RED] interrupted | 4c8904c |
| 3 | Round 1: skip the POSIX-only C harness on Windows | 8fba116 |
| 3 | Round 2: PySide6 only on Python 3.12+ in the lock | 1d71feb |
| 3 | Round 2: the GUI needs Python 3.12+, and the bridge tests skip on 3.11 | ed1d2ee |

Run 40901615873 (8fba116) was 4/5 green. On ubuntu-22.04 with Python 3.11, the suite printed `Ran 95 tests ... OK` and then aborted with `Fatal Python error: bool_dealloc` (exit 134). PySide6 6.12.0 drops a reference to True on each Python-signal emit. From 3.12 on, True is immortal, which hides the bug.

Run 40907463731 (ed1d2ee): all five jobs passed. The 3.11 job ran 65 tests and skipped one, the test_bridge module, with the reason "the GUI needs Python 3.12+ (PySide6 6.12 refcount bug on 3.11)".

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] f-string with nested quotes in porter/pipeline.py**: Python 3.11 cannot parse it. Commit 69911a6.

**2. [Rule 1 - Bug] Windows stop did not print `[RED] interrupted`**: the POSIX stop does. Fixed in porter/procs.py. Commit 4c8904c.

**3. [Rule 3 - Blocking] tests/test_perf_adaptive.py drives a POSIX-only C harness (setenv, unsetenv)**: it now skips on Windows. Commit 8fba116.

### User decision (checkpoint in Task 3)

**4. Option C: the GUI needs Python 3.12+.** The user made this choice.
- requirements.in now marks PySide6-Essentials `==6.12.*; python_version >= "3.12"`. The regenerated requirements.txt changes only two lines. pyside6-essentials 6.12.0 and shiboken6 6.12.0 gain `; python_full_version >= '3.12'`. No package version changed. requirements-build.txt and requirements-dev.txt came out of uv unchanged.
- gui/__main__.py checks the version before it imports PySide6. On Python older than 3.12 it exits with `[RED] the GUI needs Python 3.12 or later (this is X); the CLI, python -m porter, runs on 3.11`. The frozen launcher (packaging/nx2android.py) is unchanged, because the bundles ship 3.14.
- tests/test_bridge.py skips on Python older than 3.12, in CI too. **This is a deliberate exception to the TEST-02 rule that a missing module fails in CI.** The skip comes from a declared version floor, not from a missing module, and the code says so in a one-line comment. The 3.11 job still runs and passes the CLI and porter tests, and the `Ran [1-9]` check still applies.
- README.md and docs/ARCHITECTURE.md now say "3.11+ for the CLI, 3.12+ for the GUI". packaging/INSTALL.md states no Python floor, so it is unchanged. The comment on the fork-ci.yml 3.11 matrix row now reads "the CLI floor (the GUI tests skip there)". The matrix itself and the Ci tests are unchanged.
- **This supersedes the GUI part of the project constraint "Python: 3.11+ for dev runs".** .claude/CLAUDE.md was not edited; the orchestrator will raise it with the user.

## Verification

- Local suite (.venv, Python 3.14, offscreen): 95 tests passed, 1 skipped.
- Docker python:3.11 (3.11.18, CI=1) on the working tree: 65 tests ran, test_bridge skipped, and there was no abort. `python -m gui` printed the [RED] floor line and exited with code 1. test_architecture failed there only because the tarball has no git repo (arch_rules runs `git ls-files`). In CI it passes.
- fork-ci run 40907463731: success on all five jobs.

## Known Stubs

None.

## Self-Check: PASSED
