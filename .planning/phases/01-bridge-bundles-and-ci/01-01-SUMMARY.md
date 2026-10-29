---
phase: 01-bridge-bundles-and-ci
plan: 01
subsystem: infra
tags: [uv, pip, lockfile, supply-chain, pyside6, pyinstaller]
status: complete
requires: []
provides:
  - Hashed universal runtime lock (requirements.txt from requirements.in)
  - Hashed build lock (requirements-build.txt) and dev lock (requirements-dev.txt), declared apart
  - tests/test_workflows.py class Lock (5 tests) and entries(path) helper
  - Local Python 3.14 .venv with runtime + build locks installed via --require-hashes
affects: [01-02, 01-03, 01-04, 01-05, 01-06, 01-07, 01-08, fork-ci, release]
actuals:
  tokens: 13849
  tasks: 3
  commits: 3
plan_head_before: 883703e8609bdc6e0791451d604c74c7619c8385
plan_head_after: 08e52efcbd32c9eb7cf4ce1d1e45e5db71249cb0
tech-stack:
  added: [PySide6-Essentials 6.12.0 (replaces the PySide6 meta package), uv 0.11.32 (lock generation)]
  patterns: [".in file holds the pins and the exact uv compile command in its header; the .txt is generated, never hand-edited", "build and dev locks are constrained by requirements.txt (-c) so shared packages stay on the runtime pins"]
key-files:
  created: [requirements.in, requirements-build.in, requirements-build.txt, requirements-dev.in, requirements-dev.txt, tests/test_workflows.py]
  modified: [requirements.txt, README.md]
key-decisions:
  - "Runtime, build and dev dependencies each get their own .in and hashed uv lock; build/dev locks are constrained by the runtime lock"
  - "User approved the runtime and build lock package list (Task 2 legitimacy gate) before the first install"
  - "Plan 01-01 commits land on main by user choice (git.allow_default_branch_commits: true)"
patterns-established:
  - "Lock pattern: edit requirements*.in, regenerate with the uv command in its header, install with --require-hashes"
requirements-completed: [PKG-06]
coverage:
  - id: D1
    description: "Runtime and build locks are hashed, uv-generated, and keep build tools out of the runtime lock"
    requirement: PKG-06
    verification:
      - kind: unit
        ref: "python3 -m unittest tests.test_workflows.Lock -v"
        status: pass
  - id: D2
    description: "Dev lock (numpy, av, uv) declared and locked apart from the runtime lock"
    requirement: PKG-06
    verification:
      - kind: unit
        ref: "tests/test_workflows.py#Lock.test_dev_apart"
        status: pass
  - id: D3
    description: "Python 3.14 .venv installs requirements.txt + requirements-build.txt with --require-hashes and runs the suite"
    requirement: PKG-06
    verification:
      - kind: other
        ref: "QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover tests"
        status: pass
duration: resumed run (Task 1 done in a prior session)
completed: 2026-10-29
---

# Phase 1 Plan 1: Hashed Dependency Locks Summary

Every Python dependency is now pinned in uv-generated hashed universal locks: runtime (requirements.txt), build (requirements-build.txt, PyInstaller) and dev (requirements-dev.txt, numpy/av/uv). Each lock comes from its own `.in` file, tests/test_workflows.py checks the locks, and a Python 3.14 `.venv` was installed from the runtime and build locks with `--require-hashes`.

## Tasks

| Task | Name | Commit |
| ---- | ---- | ------ |
| 1 | Runtime and build locks from .in files, checked by tests/test_workflows.py | 3f8f998 |
| 2 | Package legitimacy review of the generated locks (checkpoint, blocking-human) | approved by user, no files |
| 3 | Dev lock, README install lines, hash-installed .venv (TDD: RED 4e96c0c, GREEN 08e52ef) | 4e96c0c, 08e52ef |

## Verification

- `python3 -m unittest tests.test_workflows.Lock -v`: 5 tests OK (system Python, stdlib only)
- `python3 tests/arch_rules.py`: all checks passed
- `.venv/bin/python --version`: Python 3.14.5; `pip check`: no broken requirements
- `.venv/bin/python -c "import lz4.block, capstone, PIL, yaml, PySide6.QtWidgets, PySide6.QtTest, PyInstaller"`: ok
- `.venv` full suite (`unittest discover tests`, offscreen): 32 tests OK, 1 skipped (`test_vk_layout_cache.LayoutCache.test_layout_identity`: "NDK Vulkan headers are required"; environment, not this plan; 01-07 owns cross-host test fixes)

## TDD Gate Compliance

- RED: 4e96c0c `test(01-01)` added `test_dev_apart` and `requirements-dev.txt` to the hash check; suite failed (3 errors, missing file).
- GREEN: 08e52ef `feat(01-01)` added requirements-dev.in/.txt; 5/5 Lock tests pass.
- REFACTOR: none needed.

## Deviations from Plan

None in the code. Process notes:
- Task 1 was finished in an earlier session but could not be committed there because of the protected-branch guard. The user chose to commit on main, so it was committed in this run after its verification was run again.
- requirements-dev.in lists numpy, av and uv without version pins (the plan gave none). requirements-dev.txt pins them: av 18.1.0/19.0.2 and numpy 2.4.6/2.5.4, split by Python version, and uv 0.13.6. The Task 2 gate did not review the dev lock. Nothing in this phase installs it.

## Known Stubs

None.

## Self-Check: PASSED

- FOUND: requirements.in, requirements.txt, requirements-build.in, requirements-build.txt, requirements-dev.in, requirements-dev.txt, tests/test_workflows.py
- FOUND commits: 3f8f998, 4e96c0c, 08e52ef
