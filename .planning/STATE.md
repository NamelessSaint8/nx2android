---
gsd_state_version: "1.0"
current_phase: 01
current_phase_name: Bridge, Bundles and CI
status: executing
stopped_at: Completed 01-05-PLAN.md
last_updated: "2026-10-29T08:43:06.582Z"
last_activity: 2026-10-29
last_activity_desc: Phase 01 execution started
state_head: 6b190f920b969774c409674a406d81bcd6589134
progress:
  total_phases: 6
  completed_phases: 0
  total_plans: 8
  completed_plans: 2
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-29)

**Core value:** A tester on any supported host (Windows x64, macOS Apple Silicon, Linux x64, Linux arm64) can take their own Switch dump and get a working port onto their Android device through the GUI, without help.
**Current focus:** Phase 01 — Bridge, Bundles and CI

## Current Position

Phase: 01 (Bridge, Bundles and CI) — EXECUTING
Plan: 3 of 8
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

Last session: 2026-10-29T08:43:06.566Z
Stopped at: Completed 01-05-PLAN.md
Resume file: None
