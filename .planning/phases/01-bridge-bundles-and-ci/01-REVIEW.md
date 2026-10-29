---
phase: 01-bridge-bundles-and-ci
reviewed: 2026-10-29T20:17:04Z
depth: standard
files_reviewed: 36
files_reviewed_list:
  - .github/workflows/fork-ci.yml
  - .github/workflows/fork-release.yml
  - README.md
  - docs/ARCHITECTURE.md
  - docs/RELEASE_CHECK.md
  - gui/__main__.py
  - gui/app.py
  - gui/runner.py
  - packaging/INSTALL.md
  - packaging/build_bundle.py
  - packaging/glibc_floor.py
  - packaging/nx2android.py
  - packaging/nx2android.spec
  - packaging/smoke_bundle.py
  - packaging/smoke_gui.py
  - porter/cli.py
  - porter/paths.py
  - porter/pipeline.py
  - porter/procs.py
  - porter/runlog.py
  - requirements.in
  - requirements.txt
  - tests/fixtures/bridge/edge.jsonl
  - tests/fixtures/bridge/fake_porter.py
  - tests/fixtures/bridge/inspect_error.json
  - tests/fixtures/bridge/install_ok.jsonl
  - tests/fixtures/bridge/port_build_error.jsonl
  - tests/fixtures/bridge/port_ok.jsonl
  - tests/fixtures/bridge/record.py
  - tests/test_bridge.py
  - tests/test_packaging.py
  - tests/test_paths.py
  - tests/test_perf_adaptive.py
  - tests/test_porter.py
  - tests/test_runlog.py
  - tests/test_workflows.py
findings:
  critical: 0
  warning: 6
  info: 4
  total: 10
status: issues_found
---

# Phase 1: Code Review Report

**Reviewed:** 2026-10-29T20:17:04Z
**Depth:** standard
**Files Reviewed:** 36
**Status:** issues_found

## Summary

I reviewed the new bridge code (`porter/procs.py`, `porter/runlog.py`, `gui/runner.py`, the `gui/app.py` changes), the frozen-engine copy in `porter/paths.py`, the packaging and smoke scripts, the two fork workflows, and the tests and fixtures. For `porter/cli.py` and `porter/pipeline.py` I reviewed only the diff against `5d87388`, because those files are shared with upstream.

I traced the main paths and found them sound:

- The POSIX session and SIGTERM/SIGKILL stop works as intended.
- On Windows, the kill-on-close Job Object works when it is created.
- The run-log open, wrap and close sequence is correct. Upstream `Progress.lock` is an `RLock`, so the wrapped `end()` does not deadlock.
- The `.port-running` marker works.
- `call_json` calls back exactly once, and it is safe when its owner widget is destroyed mid-call.
- Secrets stay in the `release` environment and reach the macos job only through `env:`. Actions are pinned to commit SHAs. No workflow runs on a privileged pull-request trigger.

None of the problems below is a release blocker. They fall into three groups:

- Two Windows stop-channel gaps: the no-Job-Object fallback never fires, and child processes inherit the stop pipe.
- An import-time engine copy with no recovery when it fails.
- A "report, not a gate" job that actually gates the release.

There are also two GUI and test robustness issues.

## Warnings

### WR-01: Windows stop without a Job Object orphans the whole tree

**File:** `porter/procs.py:77-85`, `gui/runner.py:79-84`
**Issue:** If `_job()` fails, `setup()` records the note and `job` stays `None`. On a stop, `_watch` calls `on_stop()`, skips `TerminateJobObject`, and calls `os._exit(130)` straight away. That ends porter alone and leaves dotnet, MSBuild, clang and the shader tools running. The GUI fallback meant for this case never runs. `_force` taskkills only `if run.state() != QProcess.NotRunning`, but porter has already exited. `_done`/`_reap` then sets `ended=True` at once on Windows, and `_force` returns early on `self.ended`. The comment on line 83 ("a porter whose Job Object could not be made") describes a path that cannot be reached.
**Fix:** If there is no job, kill the tree from inside porter before exiting:
```python
if job: _k().TerminateJobObject(job, 130)
else: subprocess.run(['taskkill', '/T', '/F', '/PID', str(os.getpid())], capture_output=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
os._exit(130)
```
Add a test that patches `_job` to raise `OSError` and checks that the grandchild is gone.

### WR-02: Child processes inherit the stop channel (porter's stdin), and `adb shell` can swallow "stop"

**File:** `porter/procs.py:69-76` (with `porter/adb.py:44` and upstream `nsp.run`, which use `subprocess.run`/`Popen` without `stdin=`)
**Issue:** Under the GUI, fd 0 is the pipe the GUI writes `stop\n` into. Every child porter starts inherits it. On a non-tty stdin, `adb shell` reads stdin and forwards it to the device. `install` runs many `adb shell` calls, and `am start -W` can take up to 60 s. If Cancel is pressed during one of these calls, adb takes the bytes and porter's watcher never sees `stop`. On Windows that means no `cancelled during <stage>` line in the log and no `[RED] interrupted` line. The run then ends only through the GUI's taskkill after 5 s. On POSIX this does no harm, because the stop there is SIGTERM.
**Fix:** In `setup()`, before the watcher thread starts, give the watcher its own copy of the pipe and point fd 0 at the null device. All children then inherit an empty stdin. On Windows, UCRT `_dup2` also updates the standard input handle, but confirm that on a Windows runner.
```python
fd = os.dup(0); nul = os.open(os.devnull, os.O_RDONLY); os.dup2(nul, 0); os.close(nul)
threading.Thread(target=_watch, args=(job, on_stop, as_json, fd), daemon=True).start()
# _watch: chunk = os.read(fd, 64)
```

### WR-03: The frozen engine copy runs at import time and has no recovery when it fails

**File:** `porter/paths.py:24-50`
**Issue:** `_engine()` runs when `porter.paths` is imported. That happens in the GUI process too: `gui/runner.py` imports it before any window exists. So a failed copy takes down every porter command and the GUI itself, with a bare traceback. When the Windows bundle is double-clicked its console is hidden, so the player sees nothing at all. Three concrete failure paths:
1. On Windows, `os.rename(tmp, dst)` often fails with `PermissionError` while Defender scans the roughly 1,450 files just written. `dst` does not exist yet, so line 39 re-raises.
2. If `dst` exists but `dst/nxnative` does not (for example a partly deleted folder, or AV quarantine), every later start copies again, then fails the rename because `dst` is not empty, then raises. The app never starts again until the player deletes the folder by hand.
3. Each failed attempt leaves a `<eid>.tmp-<pid>` folder of about 150 MB that the prune loop never removes. The comment on line 44 covers this case only for a killed copy.

The first launch also blocks the GUI's main thread for the whole 153 MB copy and shows no window.
**Fix:**
- Retry the rename a few times with a short sleep before giving up.
- If `dst` exists without `nxnative`, remove `dst` with `rmtree` before the rename.
- Wrap the copy so a failure falls back to a clear `[RED]` message. Or show it in a `QMessageBox` from `gui/__main__.py`.
- Remove `tmp` on failure:
```python
try: shutil.copytree(...); _chmod(tmp)
except BaseException: shutil.rmtree(tmp, ignore_errors=True); raise
for n in range(5):
    try: os.rename(tmp, dst); break
    except OSError:
        if (dst / 'nxnative').is_dir(): shutil.rmtree(tmp, ignore_errors=True); break
        if dst.exists() and n == 0: shutil.rmtree(dst, ignore_errors=True)
        if n == 4: raise
        time.sleep(0.5)
```

### WR-04: `upstream-diff` is described as "a report, not a gate", but the release job needs it

**File:** `.github/workflows/fork-release.yml:161-176`
**Issue:** `release` has `needs: [build, macos, upstream-diff]`. If `git fetch https://github.com/shirai91/nx2android.git main` fails (a network error, a renamed or private upstream, a force-push), or `git diff FETCH_HEAD...HEAD` finds no merge base, the job fails. That blocks the draft release of bundles that are already signed and notarized. This contradicts the CI-04 comment on line 161.
**Fix:** Keep the dependency, which `tests/test_workflows.py:134` pins, but make the job non-fatal. Add `continue-on-error: true` to the `upstream-diff` job, or end its step with `|| echo '[RED] upstream diff unavailable' >> "$GITHUB_STEP_SUMMARY"`.

### WR-05: The GUI's `devices` limit (15 s) is shorter than porter's own adb timeouts (30 s)

**File:** `gui/runner.py:16`, `porter/procs.py:30`, `porter/adb.py:59`
**Issue:** `devices --json` now runs `procs.adb_server()` first, with `timeout=30`, and then `adb devices -l`, with `timeout=30`. A cold or mismatched adb server can take more than 15 s to start (for example, "adb server version doesn't match this client; killing..."). When that happens the GUI SIGKILLs porter's session. It shows "porter didn't answer in 15 s" instead of the adb error that porter would have reported. The comment on line 14 says the limit exists "because adb stalls on a bad cable". The limit is now below the time porter itself allows adb to answer.
**Fix:** Make the GUI limit larger than porter's worst case (for example `'devices': 45`), or lower porter's `start-server` timeout below the GUI limit (for example 10 s). Update `tests/test_bridge.py:390` and the `TIMEOUTS` line in `docs/ARCHITECTURE.md` to match.

### WR-06: Unit tests start the developer machine's real adb server

**File:** `tests/test_runlog.py:128`, `tests/test_bridge.py:83-97`
**Issue:** `procs.setup()` calls `adb_server()` for any `cmd in ('devices', 'install')`. `Retention.test_keeps_newest_30` runs `runlog.run` in-process with `cmd='install'`. `Errors.test_failed_port_shows_cause_and_log` builds a real `Window` with the real porter, and its start-up `devices --json` call goes through `procs.setup`. On a machine where `adb` is on `PATH` or under `ANDROID_HOME`, both tests run `adb start-server`. That call can block for up to 30 s and leaves a daemon running. On a machine with a connected device it also touches that device's adb state. `record.py:37` stubs `adb_server` for exactly this reason, but the tests do not.
**Fix:** Patch it in the tests:
- In `InProcess.setUp`, add `self.addCleanup(mock.patch.object(procs, 'adb_server', lambda: None).stop)` and start the patch.
- For the real-porter GUI test, set `PATH` and `ANDROID_HOME` to empty values in the child environment, or set an env switch that `adb_server()` honours.

## Info

### IN-01: The Windows watcher prints outside the emitter's lock

**File:** `porter/procs.py:82`
**Issue:** The watcher thread calls `print(json.dumps(...))` without holding `PROG.lock`, while the main thread can be inside `PROG._json`. `print` makes two writes (the text, then `\n`), so the two lines can interleave into one corrupted line. The GUI would then show it as a raw `say`.
**Fix:** Write the line in a single `sys.stdout.write(line + '\n')`, or take `PROG.lock` when `porter.upstream` is already loaded.

### IN-02: The GUI does not check the shape of one-shot answers

**File:** `gui/app.py:125-131`, `gui/app.py:146-155`
**Issue:** `call_json` passes along any valid JSON. `on_inspect` calls `info.get(...)`, and `got` uses `r['state']`. A list, or a dict without the expected keys, raises inside the slot, and the card stays at "Reading the game folder…". `fake_porter.py` itself answers `[]` to `inspect`. Porter is the same version as the GUI, so this is a contract-hardening point, not a live bug.
**Fix:** `if not isinstance(info, dict): fail = {'timeout': 0, 'error': 'porter gave an unexpected answer', 'stderr': ''}`, and do the same check for lists of dicts.

### IN-03: A local variable shadows the module-level `cause()`

**File:** `gui/app.py:244`
**Issue:** `cause = (self.error or {}).get('msg') or self.red` inside `on_finished` hides the module function `cause(fail)` defined at line 33. Any later edit that calls `cause(...)` in that method would fail.
**Fix:** Rename the local, for example `why`.

### IN-04: Two ways of escaping, and a misleading status on quit

**File:** `gui/app.py:329`, `gui/app.py:426`
**Issue:**
- `fetched()` escapes by hand with `.replace('&', ...).replace('<', ...)`, while `failed()` uses `html.escape`. Both work, but they will drift apart.
- `closeEvent` sets the Port tab's status to "stopping…" even when the only thing running is a tool download.

**Fix:** Use `html.escape(msg, quote=False)` in `fetched()`. In `closeEvent`, set `self.port.step` only when `self.port.porter` is one of the running processes.

---

_Reviewed: 2026-10-29T20:17:04Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
