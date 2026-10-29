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
| 1-xx-xx | — | — | BRDG-01, BRDG-06 | — | Stop leaves no grandchild; adb-like detached child survives; `finished` only after the tree is gone | integration | `python -m unittest tests.test_bridge.Stop -v` | ❌ W0 | ⬜ pending |
| 1-xx-xx | — | — | BRDG-02 | — | Close during a run asks, then stops the tree before quitting | GUI offscreen | `python -m unittest tests.test_bridge.Close -v` | ❌ W0 | ⬜ pending |
| 1-xx-xx | — | — | BRDG-03 | — | Real cause reaches the status; crash shows stderr tail | unit + integration | `python -m unittest tests.test_bridge.Errors tests.test_runlog -v` | ❌ W0 | ⬜ pending |
| 1-xx-xx | — | — | BRDG-04 | — | One-shot timeout kills the tree and offers Retry | integration | `python -m unittest tests.test_bridge.Timeout -v` | ❌ W0 | ⬜ pending |
| 1-xx-xx | — | — | BRDG-05 | — | Run log written with stage lines + traceback; path reported in protocol | porter subprocess | `python -m unittest tests.test_runlog -v` | ❌ W0 | ⬜ pending |
| 1-xx-xx | — | — | PKG-06, CI-03 | T-1-xx | Lock lines hashed; no `pull_request_target`; actions SHA-pinned; secrets only under `environment: release` | unit (YAML text) | `python -m unittest tests.test_workflows -v` | ❌ W0 | ⬜ pending |
| 1-xx-xx | — | — | CI-04 | — | glibc floor printed and gated | CI | `python packaging/glibc_floor.py dist/nx2android 2.34` | ❌ W0 | ⬜ pending |
| 1-xx-xx | — | — | TEST-02 | — | Missing lz4 → skip with hint; with `CI` set → failure | unit | `python -m unittest tests.test_porter -v` | edit existing | ⬜ pending |
| 1-xx-xx | — | — | TEST-03 | — | Golden replays produce exact event sequences headless | integration | `QT_QPA_PLATFORM=offscreen python -m unittest tests.test_bridge.Replay -v` | ❌ W0 | ⬜ pending |
| 1-xx-xx | — | — | PKG-01..05, CI-01, CI-02 | — | Frozen bundle doctor JSON, profiles, offscreen GUI start from a read-only copy; listing unchanged | CI smoke | `fork-release.yml` smoke steps (`packaging/smoke_gui.py`) | ❌ W0 | ⬜ pending |

*Task IDs are filled in by the planner. Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/fixtures/bridge/fake_porter.py` + golden `*.jsonl` (recorded and scrubbed from a real run on the dev Mac)
- [ ] `tests/test_bridge.py` (Replay, Errors, Timeout, Stop, Close), skips cleanly when PySide6 is absent locally
- [ ] `tests/test_runlog.py` (log file, `log`/`error` events, retention, D-08 marker incl. the `extract/*.key` exclusion)
- [ ] `tests/test_workflows.py` (SHA pins, no `pull_request_target`, secrets only under `environment: release`, lock lines hashed)
- [ ] `requirements.in` / lock regeneration (PySide6-Essentials) so tests can import Qt in CI
- [ ] `packaging/smoke_gui.py`, `packaging/glibc_floor.py`

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
