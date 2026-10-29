# Phase 1: Bridge, Bundles and CI - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-29
**Phase:** 01-bridge-bundles-and-ci
**Areas discussed:** Errors, timeouts & logs; Cancel & close

Areas offered but not chosen, so left to Claude's discretion: Release & versioning, Read-only bundle.

---

## Errors, timeouts & logs

### Where a run's full log is saved

| Option | Description | Selected |
|--------|-------------|----------|
| Porter, user folder | porter writes `<user dir>/logs/<time>-<command>[-<title ID>].log` for every long command, CLI runs included, with the path in the result and error events | ✓ |
| Porter, build folder | `<tid>_build/logs/run-<time>.log`, beside the per-tool logs; an install-only run or a deleted build folder leaves no log | |
| GUI tees it | the GUI saves what it received; CLI runs leave no log, and the GUI would own a record | |

### What goes into the saved log

| Option | Description | Selected |
|--------|-------------|----------|
| Readable text | the GUI pane's lines, the full stderr traceback, and the per-tool log paths | ✓ |
| Raw JSON-lines | every event plus stderr; can be replayed, but is hard for a tester to read | |
| Both files | a .log and a .jsonl side by side | |

### One-shot call timeout

| Option | Description | Selected |
|--------|-------------|----------|
| Per command | for example devices 15 s, doctor 30 s, inspect 60 s; kill at the limit, then show the message, stderr's tail and Retry | ✓ |
| One limit for all | for example 60 s for every call | |
| You decide | values picked in planning | |

### How a failure shows

| Option | Description | Selected |
|--------|-------------|----------|
| Inline + Open log | the status line shows the real cause, plus an Open log button; no dialog | ✓ |
| Dialog on failure | a modal with the cause, Open log and Copy | |
| Dialog for crashes only | known errors inline, a dialog for tracebacks | |

**Notes:** the user then moved on; log retention and how failed one-shot calls show their stderr were left to Claude.

---

## Cancel & close

### How Cancel stops the run

| Option | Description | Selected |
|--------|-------------|----------|
| Grace, then force | SIGTERM / Ctrl-Break to the tree, "stopping…", force-kill after about 5 s, "cancelled" once everything is gone | ✓ |
| Grace + Force button | the same, and Cancel turns into Force stop during the wait | |
| Hard kill at once | kill the tree at once; porter can't close its log | |

### Close-window confirmation

| Option | Description | Selected |
|--------|-------------|----------|
| Stop and quit / Keep running | two buttons; the window waits for the stop and then quits; an install adds a half-installed warning | ✓ |
| Add 'quit now' | a third button that force-kills and closes at once | |
| Ask only for a port | an install just stops, without asking | |

### Cut-off build before Phase 2's stamps

| Option | Description | Selected |
|--------|-------------|----------|
| Coarse 'run in progress' marker | a marker in `<tid>_build/`; if the next port finds it, every cached stage is redone; works after a SIGKILL | ✓ |
| Pull HARD-05 forward | per-stage atomic stamps now; touches every stage in pipeline.py and changes the roadmap | |
| Known issue only | tell testers to delete `_build` after a cancel | |

### Close confirmation for toolchain downloads

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, same dialog | the same dialog and stop for the Setup tab's download process | ✓ |
| Stop silently | stop the download without asking | |
| Port/install only | leave downloads to Phase 3 | |

---

## Claude's Discretion

- Release trigger (`v*` tag plus manual dispatch, draft release on the fork) and asset names
- The fork's tag and version scheme (one-way, to be surfaced at planning)
- The macOS bundle identifier and app name (one-way, to be surfaced at planning)
- The read-only bundle layout: the `REPO` split, bytecode off, copying `nxnative/` into the user folder (preferred) vs redirecting `obj/`
- Smoke-test depth: CI runs `doctor --json` plus an offscreen GUI start from a read-only copy; the full port and the codesign check after it are manual on the Mac
- Log retention, exact timeouts and grace period, how one-shot errors display, and whether `tools --download` writes a log

## Deferred Ideas

- Download Cancel button with resume: Phase 3 (FRUN-01)
- Per-stage atomic stamps replacing the marker: Phase 2 (HARD-05)
