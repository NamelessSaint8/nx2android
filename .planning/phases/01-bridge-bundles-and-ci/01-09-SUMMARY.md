---
phase: 01-bridge-bundles-and-ci
plan: 09
subsystem: infra
tags: [tls, ssl, openssl, urllib, pyinstaller, ca-certificates]

requires:
  - phase: 01-bridge-bundles-and-ci
    provides: the frozen macOS and Linux bundles (plans 01-01..01-08) whose OpenSSL carries the CI runner's CA path
provides:
  - porter/tls.py context(), the SSL context of every HTTPS call in porter/
  - tests/test_tls.py pinning the fallback, the no-downgrade rule and the wiring of every urlopen
affects: [01-10 frozen-bundle proof, Setup tab downloads, --fps60]

actuals:
  tokens: 2300
  tasks: 2
  commits: 3
plan_head_before: 5ba4c02363e45efc20b487a03e42e48acb0373a6
plan_head_after: 947266e23a91d5c76799929f2e2c7edf06b1fc9c

tech-stack:
  added: []
  patterns:
    - "Every urllib.request.urlopen in porter/ passes context=tls.context(); tests/test_tls.py scans porter/*.py for a call without it"

key-files:
  created: [porter/tls.py, tests/test_tls.py, tests/fixtures/tls/test-ca.pem]
  modified: [porter/fetch.py, porter/fpslocker.py]

key-decisions:
  - "TLS trust: one stdlib SSL context that loads the first host CA file only when the default store holds no CA; no truststore dependency, no process-wide SSL_CERT_FILE (dotnet's NuGet restore and the other children keep their own trust)"

patterns-established:
  - "Fork-owned module plus one-line hooks in upstream files (porter/fetch.py, porter/fpslocker.py differ only by an import and context= arguments)"

requirements-completed: [PKG-02, PKG-03, PKG-04]

coverage:
  - id: D1
    description: "With an empty default CA store, porter loads the NDK, .NET and adb lists, the .NET HEAD size, downloads and checks platform-tools, and fpslocker.fetch gets a verified 404"
    requirement: PKG-02
    verification:
      - kind: integration
        ref: "SSL_CERT_FILE=/nonexistent SSL_CERT_DIR=/nonexistent python -m porter tools --only ndk,dotnet,adb --json; ... tools --download --only adb; fpslocker.fetch('0100000000000000', '0'*16) -> None"
        status: pass
    human_judgment: false
  - id: D2
    description: "tls.context() never lowers verification, keeps a working default, leaves the environment alone, and every porter urlopen passes it"
    requirement: PKG-03
    verification:
      - kind: unit
        ref: "tests/test_tls.py#Context (5 tests)"
        status: pass
    human_judgment: false
  - id: D3
    description: "The notarized DMG on a player's Mac and the Linux bundles on Fedora 44 download the tools"
    requirement: PKG-04
    verification: []
    human_judgment: true
    rationale: "Needs the frozen bundles from a release build; scheduled in plan 01-10 Task 3"

duration: 2min
completed: 2026-10-30
status: complete
---

# Phase 01 Plan 09: Downloads trust the host's CA file Summary

**porter/tls.py gives every porter HTTPS call a verifying stdlib SSL context that loads the host's CA file (Apple's /etc/ssl/cert.pem, Fedora's tls-ca-bundle.pem, ...) only when the frozen OpenSSL's store is empty, closing UAT gap G-01-6**

## Performance

- **Duration:** 2 min (measured from the recorded start, after the plan was read)
- **Started:** 2026-10-30T06:21:26Z
- **Completed:** 2026-10-30T06:23:35Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- With SSL_CERT_FILE=/nonexistent SSL_CERT_DIR=/nonexistent (the bundles' empty store, which failed at HEAD with UAT test 6's CERTIFICATE_VERIFY_FAILED), `porter tools --only ndk,dotnet,adb --json` prints the 3 items, `--download --only adb` fetches platform-tools 37.0.1, passes its check and unpacks an executable adb, and `fpslocker.fetch` of a build with no config returns None (a verified handshake and a 404)
- Without the variables the dev Python's own store is used unchanged
- The context stays CERT_REQUIRED with hostname checking when no host file exists; no environment variable is set, no dependency added

## Task Commits

1. **Task 1: Google download list loads through porter's own SSL context (tracer)** - `c1d4793` (fix)
2. **Task 2 RED: tests pin the context of every download** - `c7ac1ef` (test)
3. **Task 2 GREEN: plan HEAD, _download and fpslocker.fetch pass the context** - `947266e` (fix)

No REFACTOR commit: nothing to clean up.

## TDD Gate Compliance

- **RED:** `NO_COLOR=1 .venv/bin/python -m unittest tests.test_tls -v` exited 1; target `test_every_urlopen_passes_the_context` failed with `['porter/fetch.py:89', 'porter/fetch.py:95', 'porter/fpslocker.py:29'] != []`. `gsd-tools check tdd-red-evidence` returned RED_EVIDENCE_OK (5 tests, 4 pass, 1 fail). Semantic assessment: the target ran and failed on its planned assertion for the intended reason, the three urlopen calls Task 1 left without context=; the other four pass because tls.context() exists since the Task 1 tracer.
- **GREEN:** 5/5 pass after the three context= arguments and the fpslocker import.

## Files Created/Modified
- `porter/tls.py` - CA_FILES (truststore 0.10.5's order) and context()
- `porter/fetch.py` - import line plus context= on _get, plan's HEAD and _download
- `porter/fpslocker.py` - `from porter import tls` plus context= on fetch's urlopen
- `tests/test_tls.py` - class Context, 5 tests, standard library only
- `tests/fixtures/tls/test-ca.pem` - public self-signed P-256 CA (CA:TRUE), key sent to /dev/null

## Verification
- `python -m unittest discover -v tests` (QT_QPA_PLATFORM=offscreen): Ran 114 tests, OK
- `tests/arch_rules.py`: all checks passed
- `git show -U0` of each task commit: fetch.py changes only the import line and the three urlopen lines; fpslocker.py only the import and its urlopen line

## Decisions Made
- The macOS keychain is not read: the shortcut comment on CA_FILES names the limit (an admin-added root, e.g. a TLS-inspecting proxy, is not trusted; SSL_CERT_FILE still works) and when to switch to truststore.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 01-10 Task 3 proves it in the frozen bundles (notarized DMG on a Mac, Linux bundles in Fedora 44 containers). The Windows zip relies on CPython reading the Windows ROOT/CA stores, so the fallback never runs there (not run).

---
*Phase: 01-bridge-bundles-and-ci*
*Completed: 2026-10-30*
