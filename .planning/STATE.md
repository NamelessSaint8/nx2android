---
gsd_state_version: "1.0"
current_phase: 01
current_phase_name: Bridge, Bundles and CI
status: executing
stopped_at: Completed 01-07-PLAN.md
last_updated: "2026-10-29T16:03:58.778Z"
last_activity: 2026-10-29
last_activity_desc: Phase 01 execution started
state_head: 4d9e2132d27daa87a610315db2254a076fc1115e
progress:
  total_phases: 6
  completed_phases: 0
  total_plans: 8
  completed_plans: 7
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-29)

**Core value:** A tester on any supported host (Windows x64, macOS Apple Silicon, Linux x64, Linux arm64) can take their own Switch dump and get a working port onto their Android device through the GUI, without help.
**Current focus:** Phase 01 — Bridge, Bundles and CI

## Current Position

Phase: 01 (Bridge, Bundles and CI) — EXECUTING
Plan: 8 of 8
Status: Ready to execute
Last activity: 2026-10-29 — Phase 01 execution started

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: -
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 01 P01 | resumed | 3 tasks | 8 files |
| Phase 01 P05 | 3 min | 2 tasks | 3 files |
| Phase 01 P02 | 7 min | 3 tasks | 6 files |
| Phase 01 P06 | 9 min | 3 tasks | 9 files |
| Phase 01 P03 | 10min | 3 tasks | 5 files |
| Phase 01 P04 | 11min | 3 tasks | 11 files |
| Phase 01 P07 | 2 fix rounds | 3 tasks | 12 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: PySide6 6.12 on every host (Linux arm64 tester on glibc 2.39+, macOS testers on 14+), so no PySide6 6.8 fallback or per-arch lock
- [Roadmap]: BRDG-01 is whole in Phase 1, including the Windows Job Object and MSBuild node-reuse env that research had put in Phase 2
- [Roadmap]: GUI features are vertical slices (porter JSON command + view per phase); the new shell starts in Phase 3 beside `gui/app.py` and becomes the default in Phase 6
- [Roadmap]: DEV-06 (launch on device) and DEV-07 (logcat) stay in v1 per REQUIREMENTS.md, although research listed them as v1.x
- [Phase 01]: Runtime, build and dev deps each get their own .in and hashed uv lock; build/dev locks constrained by requirements.txt
- [Phase 01]: 01-05: frozen porter builds from <user dir>/engine/<ENGINE id>/nxnative; a missing or non-alphanumeric ENGINE id falls back to the bundle's own nxnative
- [Phase 01]: 01-05: other engine versions are pruned only by the start that installs a copy
- [Phase 01]: 01-02: runlog prints its own log and error events, so a failed porter.upstream import still names its log
- [Phase 01]: 01-02: the cut-off key sweep prunes the top-level extract/ folder and never walks the extracted RomFS
- [Phase 01]: 01-02: LOGS_KEPT = 30 counts the new log (29 old ones stay)
- [Phase 01]: 01-06: CFBundleShortVersionString is the dotted numeric prefix of the fork tag (0.1.2 of 0.1.2-ns.1), 0.0.0 for hash builds
- [Phase 01]: 01-06: build_bootloader.py is required on Windows only; macOS and Linux bundles use PyInstaller's own bootloader
- [Phase 01]: 01-06: smoke_gui.py runs from the checkout through the frozen exe, so the bundle is not changed for the smoke test
- [Phase 01]: Porter._kill never signals a pgid <= 1; stop() before started falls back to QProcess.kill
- [Phase 01]: A stopped run ending by signal (CrashExit) reports 130 even with exit code 0; unstopped CrashExit with code 0 reports -1
- [Phase 01]: Failed downloads show their escaped cause and an Open log link inline; 130 shows cancelled
- [Phase 01]: test_bridge sets NX2A_HOME in setUpModule because test_porter sets its own at import
- [Phase 01]: 01-04: one-shot calls report done(obj, code, fail); the exit code alone is no failure (inspect exits 2 for an unportable game)
- [Phase 01]: 01-04: a one-shot whose owner is destroyed mid-call calls nothing and kills its own session (shiboken6.isValid guard)
- [Phase 01]: 01-04: port_build_error.jsonl records a port of a missing folder (machine-independent, names the folder); fake_porter --hang makes a one-shot hang
- [Phase 01]: The GUI needs Python 3.12+ (PySide6 6.12 drops a ref on True per signal emit, aborting 3.11); the CLI keeps 3.11+. Supersedes the GUI part of 'Python 3.11+ for dev runs'
- [Phase 01]: test_bridge skips on Python < 3.12 in CI too: a declared version floor, a deliberate exception to TEST-02's fail-in-CI rule

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1]: Apple Developer ID certificate is ready; secrets get added to the protected release environment when the release job needs them
- [Phase 1]: Research before planning: hardened-runtime entitlements for frozen Python + ctypes (capstone), `sys.executable`/`REPO` inside `.app`, PySide6 `setUnixProcessParameters` vs porter-side `setsid`, `wayland-*` plugin collection, .NET 10 MSBuild server env-var names
- [Phase 1→2]: Once cancel kills the whole tree (Phase 1), a cancelled run can leave a stage output the cache trusts until atomic stamps land (HARD-05, Phase 2). Clear the build folder after a cancel while testing in between
- [Phase 2]: Research: whether older platform-tools URLs stay downloadable after pinning
- [Phase 3]: Research: HomuHomu833 arm64 NDK (asset re-uploaded in place, so the pinned hash can drift; clang build parity with r27c; its glibc), minimum distro adb and when `push -Z` arrived (Debian 12 ships 29.0.6)
- [Phase 5]: Research: confirm `feature:android.hardware.vulkan.version` on the Y700 via `pm list features`, and `pm list packages --show-versioncode` reliability
- Upstream sync: merge shirai91/nx2android weekly (never rebase); keep edits to `pipeline.py`, `cli.py`, `gui/app.py` to hook lines

## Deferred Items

Items acknowledged and deferred at milestone close, most recent first:

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| *(none)* | | | | |

## Session Continuity

Last session: 2026-10-29T16:03:58.760Z
Stopped at: Completed 01-07-PLAN.md
Resume file: None
