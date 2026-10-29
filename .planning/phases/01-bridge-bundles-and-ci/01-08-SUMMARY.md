---
phase: 01-bridge-bundles-and-ci
plan: 08
subsystem: ci
tags: [github-actions, release, notarization, codesign, glibc, pyinstaller]
status: complete

requires:
  - phase: 01-bridge-bundles-and-ci
    provides: "01-01 hashed lock; 01-06 build_bundle.py, smoke_bundle.py, glibc_floor.py, the spec's bundle id; 01-07 fork-ci.yml and the Ci workflow rules"
provides:
  - ".github/workflows/fork-release.yml: Windows x64 zip, Linux x64 and arm64 tar.gz, macOS arm64 DMG (Developer ID, hardened runtime, notarized, stapled) from v*-ns.* tags and workflow_dispatch; the draft release only on tags"
  - "tests/test_workflows.py class Release: triggers, secret scoping, write scope, notarization, keychain cleanup, four assets, glibc floors, concurrency"
  - "The Linux x64 floor is glibc 2.35 (PKG-03), arm64 stays gated at 2.39"
  - "docs/RELEASE_CHECK.md Host checks table; docs/ARCHITECTURE.md names fork-release.yml"
affects: [phase 1 end-of-phase verification (manual host rows), later releases (v*-ns.* tag drafts a release)]

actuals:
  tokens: 4941
  tasks: 3
  commits: 4
plan_head_before: 5cff24f12c671ba508dbb0228bed8e911c84bc61
plan_head_after: 78d7e2b

tech-stack:
  added: []
  patterns:
    - "Signing secrets reach only the macos job, through env:, inside the protected release environment"
    - "stapler staple retries with a backoff: the ticket fetch from CloudKit can drop right after an Accepted notarization"

key-files:
  created:
    - .github/workflows/fork-release.yml
  modified:
    - tests/test_workflows.py
    - packaging/glibc_floor.py
    - packaging/INSTALL.md
    - docs/RELEASE_CHECK.md
    - docs/ARCHITECTURE.md
    - .planning/REQUIREMENTS.md

key-decisions:
  - "Linux x64 floor is glibc 2.35, not 2.34 (user decision, option B): supersedes RESEARCH Open Question 4's 2.34 choice"
  - "stapler staple is retried up to 4 times; notarization itself is not retried"

requirements-completed: [CI-02, CI-03, CI-04, PKG-02]

duration: "across three sessions (checkpoints at Task 2 and Task 3)"
completed: 2026-10-29
---

# Phase 1 Plan 08: Release workflow for the four bundles Summary

**fork-release.yml builds all four bundles, signs and notarizes the macOS DMG in the protected `release` environment, smoke-tests each frozen bundle from a read-only location, and gates the Linux glibc floors (x64 2.35, arm64 2.39). The dispatch run for 9e947b8 passed with four artifacts.**

## Tasks

| Task | Name | Commit |
|------|------|--------|
| 1 | fork-release.yml and its Release tests | e5ebcfc |
| 2 | 'release' environment and its seven secrets | none (the user did this step) |
| 3 | A green dispatch run on all four bundles, and the four-host release docs | 4599c0a, 9e947b8, 78d7e2b |

## Runs

| Run | HEAD | Result |
|-----|------|--------|
| 40937559241 | e5ebcfc | failure: `stapler staple` lost its CloudKit link (-1005, error 68) right after an Accepted notarization |
| 40938434317 | 4599c0a | macOS, Windows, arm64 and upstream-diff passed; notarization Accepted (id 2222a4b1-a55a-4ac6-b056-4a0ed17bf130), staple and validate OK, spctl "Notarized Developer ID". linux-x64 failed the 2.34 gate at 2.35 |
| 40939602080 | 9e947b8 | success: build (3), macos and upstream-diff passed, release skipped (not a tag); 4 artifacts `nx2android-9e947b8-{windows-x64.zip, linux-x64.tar.gz, linux-arm64.tar.gz, macos-arm64.dmg}`; notarization Accepted (id 3b15abde-7b3d-4001-b951-a211e3b158e1) |

A final dispatch confirms the metadata HEAD (see the completion report).

## Findings

- **RESEARCH A9 answered:** capstone, loaded through ctypes, loads and runs under the hardened runtime with no entitlements, in the signed and notarized build (smoke_bundle.py passed from the read-only DMG mount).
- **Measured glibc floors:** Linux x64 2.35 (libcairo, libgcc_s, libpython3.14, libtcl8.6, libtk8.6 from the ubuntu-22.04 runner); Linux arm64 2.38 (the PySide6 Qt libraries and libicu), under its 2.39 gate.
- **Developer ID certificate expires 2027-02-01.** The signing secret must be renewed before then or the macOS job fails.

## Decisions Made

- **Linux x64 floor raised to glibc 2.35 (supersedes RESEARCH Open Question 4).** The plan set the gate at 2.34 and said to stop and ask if the measured floor was higher. It measured 2.35, because the ubuntu-22.04 runner's own libpython, libgcc_s, cairo, tcl and tk need it. The user picked 2.35 over a container build (option A) and over trimming those libraries (option C). PKG-03 now reads glibc 2.35+: Ubuntu 22.04, Debian 12 and Fedora 36 or later. RHEL 9, Alma 9 and Rocky 9 (glibc 2.34) are no longer supported on x64. The history files (RESEARCH, CONTEXT, 01-06 and 01-08 plans, 01-06 summary, VALIDATION) are left as written.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] stapler staple failed on a dropped CloudKit link**
- **Found during:** Task 3, run 40937559241
- **Issue:** Notarization was Accepted, but `xcrun stapler staple` failed with -1005 / error 68 while fetching the ticket.
- **Fix:** Retry staple up to 4 times with a growing sleep, logged as `stapler staple failed, retry N`; `stapler validate` still has to pass afterwards.
- **Files modified:** .github/workflows/fork-release.yml
- **Commit:** 4599c0a

### Decision change (not a fix round)

**2. Linux x64 glibc gate 2.34 → 2.35:** user decision at the Task 3 checkpoint (above). Changed the workflow gate, the glibc_floor.py comments, the Release test, INSTALL.md and PKG-03. tests/test_packaging.py keeps 2.34 because there it is only fixture data. Commit 9e947b8.

Fix rounds used: 1 of 4.

## Auth gates

Task 2 (human-action, blocking-human): the user created the `release` environment (deployment tags `v*-ns.*`, branch main) and its seven secrets. No secret values passed through the session.

## Known Stubs

None. The Host checks table's manual rows (PKG-01 to PKG-05, cancel) say "not run" on purpose: they wait for the end-of-phase human check.

## Next

The end-of-phase check runs the manual Host checks rows on real machines using a run's artifacts. Pushing the first `v*-ns.*` tag, which drafts a GitHub Release, is the user's call.

## Self-Check: PASSED
