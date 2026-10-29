---
phase: "1"
slug: "bridge-bundles-and-ci"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-10-29"
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python `unittest` (stdlib) + PySide6 QtTest `QSignalSpy` for bridge tests |
| **Config file** | none (discovery) |
| **Quick run command** | `QT_QPA_PLATFORM=offscreen python -m unittest tests.test_bridge tests.test_runlog -v` |
| **Full suite command** | `QT_QPA_PLATFORM=offscreen python -m unittest discover -v tests` |
| **Estimated runtime** | ~30 seconds (quick), longer for the full suite |

---

## Sampling Rate

- **After every task commit:** Run the quick run command (bridge + runlog)
- **After every plan wave:** Run the full suite command locally, then push to trigger `fork-ci.yml`
- **Before `/gsd-verify-work`:** `fork-ci.yml` green on all four OSes, one `fork-release.yml` `workflow_dispatch` run green (draft not published), and the manual RELEASE_CHECK rows below done
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1-02-02, 1-03-02 | 01-02, 01-03 | 2, 3 | BRDG-01, BRDG-06 | T-1-04, T-1-09 | Stop leaves no grandchild; adb-like detached child survives; `finished` only after the tree is gone | integration | `python -m unittest tests.test_runlog.Stop tests.test_bridge.Stop -v` | ❌ W0 | ⬜ pending |
| 1-03-03 | 01-03 | 3 | BRDG-02 | — | Close during a run asks, then stops the tree before quitting | GUI offscreen | `python -m unittest tests.test_bridge.Close -v` | ❌ W0 | ⬜ pending |
| 1-02-01, 1-03-01, 1-04-02 | 01-02, 01-03, 01-04 | 2, 3, 4 | BRDG-03 | T-1-08, T-1-12 | Real cause reaches the status; crash shows stderr tail | unit + integration | `python -m unittest tests.test_bridge.Errors tests.test_runlog -v` | ❌ W0 | ⬜ pending |
| 1-04-01 | 01-04 | 4 | BRDG-04 | T-1-13 | One-shot timeout kills the tree and offers Retry | integration | `python -m unittest tests.test_bridge.Timeout -v` | ❌ W0 | ⬜ pending |
| 1-02-01, 1-02-03 | 01-02 | 2 | BRDG-05 | T-1-02, T-1-07 | Run log written with stage lines + traceback; path reported in protocol; no key material | porter subprocess | `python -m unittest tests.test_runlog -v` | ❌ W0 | ⬜ pending |
| 1-01-01, 1-01-03, 1-07-01, 1-08-01 | 01-01, 01-07, 01-08 | 1, 5, 6 | PKG-06, CI-03 | T-1-SC, T-1-20, T-1-21, T-1-22, T-1-23, T-1-27 | Lock lines hashed; no privileged PR trigger; actions SHA-pinned; secrets only under `environment: release` | unit (YAML) | `python -m unittest tests.test_workflows -v` | ❌ W0 | ⬜ pending |
| 1-05-01, 1-05-02 | 01-05 | 1 | PKG-05 | T-1-14, T-1-16 | Frozen resource root unchanged after a read-only start; engine copy writable, race-safe, pruned | subprocess | `python -m unittest tests.test_paths -v` | ❌ W0 | ⬜ pending |
| 1-06-02, 1-08-03 | 01-06, 01-08 | 2, 6 | CI-04 | — | glibc floor printed and gated (2.34 x64, 2.39 arm64); nxnative/ diff in the step summary | unit + CI | `python -m unittest tests.test_packaging -v`; `python packaging/glibc_floor.py dist/nx2android 2.34` | ❌ W0 | ⬜ pending |
| 1-07-01 | 01-07 | 5 | TEST-02 | — | Missing lz4 → skip with hint (setUpModule); with `CI` set → failure | unit | `python -m unittest tests.test_porter -v` | edit existing | ⬜ pending |
| 1-04-03 | 01-04 | 4 | TEST-03 | T-1-10 | Golden replays produce exact event sequences headless; fixtures scrubbed | integration | `QT_QPA_PLATFORM=offscreen python -m unittest tests.test_bridge.Replay -v` | ❌ W0 | ⬜ pending |
| 1-06-01, 1-06-03, 1-07-03, 1-08-03 | 01-06, 01-07, 01-08 | 2, 5, 6 | PKG-01..05, CI-01, CI-02 | T-1-17, T-1-26 | Frozen bundle doctor JSON, profiles, offscreen GUI start from a read-only copy; listing unchanged; codesign after (macOS); four-OS CI green | local + CI smoke | `python packaging/smoke_bundle.py <archive>` (and `fork-release.yml`, `fork-ci.yml` runs) | ❌ W0 | ⬜ pending |

*Task IDs are filled in by the planner. Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/fixtures/bridge/fake_porter.py` + golden `*.jsonl` (recorded and scrubbed from a real run on the dev Mac)
- [ ] `tests/test_bridge.py` (Replay, Errors, Timeout, Stop, Close), skips cleanly when PySide6 is absent locally
- [ ] `tests/test_runlog.py` (log file, `log`/`error` events, retention, D-08 marker incl. the `extract/*.key` exclusion)
- [ ] `tests/test_workflows.py` (SHA pins, no `pull_request_target`, secrets only under `environment: release`, lock lines hashed)
- [ ] `requirements.in` / lock regeneration (PySide6-Essentials) so tests can import Qt in CI
- [ ] `packaging/smoke_gui.py`, `packaging/smoke_bundle.py`, `packaging/glibc_floor.py`
- [ ] `tests/test_paths.py` (plan 01-05), `tests/test_packaging.py` (plan 01-06)
- [ ] Test guards for optional modules use `setUpModule()` raising `SkipTest`: a module-level `SkipTest` only skips under `discover` and crashes `python -m unittest tests.<module>` (checked on Python 3.12 while planning)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real cancel during a port leaves no dotnet/MSBuild/clang; adb still serves devices | BRDG-01 | Needs a real title, keys and a device on each host | Cancel mid-port; `ps -ef \| grep -E 'dotnet\|clang\|MSBuild'` (Task Manager on Windows); `adb devices` |
| Notarized DMG opens from Finder after a browser download on macOS 14+ | PKG-02 | Gatekeeper quarantine path only exists for a real download | Download from the draft release; open in Finder; `spctl -a -t open --context context:primary-signature -v *.dmg` |
| GUI starts under X11 and Wayland | PKG-03, PKG-04 | No real display server in CI | Launch with `QT_QPA_PLATFORM=xcb` and `wayland` on a tester machine or VM |
| Full port from the mounted DMG / read-only copy; `codesign --verify --strict` after | PKG-05 | CI has no game files or keys | Port a real title from `/Volumes/nx2android/nx2android.app`; then `codesign --verify --deep --strict --verbose=2 /Volumes/nx2android/nx2android.app` |

*Record each in `docs/RELEASE_CHECK.md`.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
