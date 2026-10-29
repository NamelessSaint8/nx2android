---
phase: 01
review: 01-REVIEW.md
titles: json
findings:
  - id: WR-01
    severity: warning
    disposition: open
    title: "Windows stop without a Job Object orphans the whole tree"
  - id: WR-02
    severity: warning
    disposition: open
    title: "Child processes inherit the stop channel (porter's stdin), and `adb shell` can swallow \"stop\""
  - id: WR-03
    severity: warning
    disposition: open
    title: "The frozen engine copy runs at import time and has no recovery when it fails"
  - id: WR-04
    severity: warning
    disposition: open
    title: "`upstream-diff` is described as \"a report, not a gate\", but the release job needs it"
  - id: WR-05
    severity: warning
    disposition: open
    title: "The GUI's `devices` limit (15 s) is shorter than porter's own adb timeouts (30 s)"
  - id: WR-06
    severity: warning
    disposition: open
    title: "Unit tests start the developer machine's real adb server"
  - id: IN-01
    severity: info
    disposition: open
    title: "The Windows watcher prints outside the emitter's lock"
  - id: IN-02
    severity: info
    disposition: open
    title: "The GUI does not check the shape of one-shot answers"
  - id: IN-03
    severity: info
    disposition: open
    title: "A local variable shadows the module-level `cause()`"
  - id: IN-04
    severity: info
    disposition: open
    title: "Two ways of escaping, and a misleading status on quit"
open: 10
total: 10
recorded: 2026-10-29T20:18:43.567Z
---

# Phase 01: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| WR-01 | warning | open | - |
| WR-02 | warning | open | - |
| WR-03 | warning | open | - |
| WR-04 | warning | open | - |
| WR-05 | warning | open | - |
| WR-06 | warning | open | - |
| IN-01 | info | open | - |
| IN-02 | info | open | - |
| IN-03 | info | open | - |
| IN-04 | info | open | - |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
