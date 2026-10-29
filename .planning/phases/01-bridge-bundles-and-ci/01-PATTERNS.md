# Phase 1: Bridge, Bundles and CI - Pattern Map

**Mapped:** 2026-10-29
**Files analyzed:** 22
**Analogs found:** 17 / 22 (the rest: workflows, lockfiles, `glibc_floor.py`, which have no analog in the repo)

All analogs below are git-tracked source. `.github/` does not exist; it was checked.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `porter/procs.py` (NEW) | utility (process setup) | event-driven (signals, stdin stop) | `packaging/nx2android.py` (ctypes kernel32), `porter/cli.py` `_with_progress` | partial |
| `porter/runlog.py` (NEW) | service (log + events) | streaming / file-I/O | `porter/cli.py` `_with_progress`, upstream `Progress._json/_out/end` | role-match |
| `porter/paths.py` (EDIT) | config | n/a | itself | exact |
| `porter/cli.py` (EDIT, 1 line) | controller | request-response | itself, line 162 | exact |
| `porter/pipeline.py` (EDIT, 1 line) | service | batch | itself, line 148 | exact |
| `gui/runner.py` (EDIT) | bridge | streaming | itself | exact |
| `gui/app.py` (EDIT, hooks) | component | event-driven | itself | exact |
| `packaging/nx2android.py` (EDIT) | entry | n/a | itself | exact |
| `packaging/nx2android.spec` (EDIT) | config | n/a | itself | exact |
| `packaging/build_bundle.py` (EDIT) | build script | file-I/O | itself | exact |
| `packaging/build_bootloader.py` (EDIT) | build script | n/a | itself (`is_local()`) | exact |
| `packaging/smoke_gui.py` (NEW) | script/test | request-response | `tests/test_architecture.py` + `gui/app.py` `main` | partial |
| `packaging/glibc_floor.py` (NEW) | script | file-I/O | `tests/arch_rules.py` (check-and-exit style) | partial |
| `tests/test_porter.py` (EDIT, imports) | test | n/a | itself lines 1-10 | exact |
| `tests/test_bridge.py` (NEW) | test | streaming | `tests/test_commit_msg.py`, `tests/test_architecture.py` | role-match |
| `tests/test_runlog.py` (NEW) | test | file-I/O | `tests/test_porter.py` (NX2A_HOME isolation) | role-match |
| `tests/test_workflows.py` (NEW) | test | n/a | `tests/test_architecture.py` | role-match |
| `tests/fixtures/bridge/fake_porter.py` + `*.jsonl` (NEW) | fixture | streaming | upstream `Progress._json` output format | partial |
| `.github/workflows/fork-ci.yml`, `fork-release.yml` (NEW) | CI config | batch | none | no analog |
| `requirements.in`, `requirements-build.in`, generated `.txt` | config | n/a | current `requirements.txt` | partial |
| `docs/ARCHITECTURE.md`, `docs/RELEASE_CHECK.md`, `packaging/INSTALL.md` (EDIT) | docs | n/a | themselves | exact |

## Pattern Assignments

### `porter/runlog.py` (service, streaming/file-I/O)

**Analog:** `porter/cli.py` `_with_progress` (lines 78-95) — the exception-to-exit-code map runlog wraps:
```python
def _with_progress(mode, fn):
    from porter.upstream import BuildError, PROG, nsp
    PROG.mode = nsp.progress_mode(mode)
    environ = dict(os.environ)
    try:
        fn(); return 0
    except BuildError as e:
        PROG.close(ok=False); PROG.say(f'[RED] {e}'); return 1
    except KeyboardInterrupt:
        PROG.close(ok=False); PROG.say('[RED] interrupted'); return 130
    except Exception as e:
        PROG.close(ok=False)
        if PROG.mode == 'json': PROG.say(f'[RED] {type(e).__name__}: {e}')
        raise
```
Do not edit this function; `runlog.run(a, fn)` wraps the result codes (1 / raise / 130 / 0) from outside.

**Event emitter to wrap** — `nxnative/scripts/build_ipa_from_nsp.py` (`Progress`, `PROG = Progress()` line 254). Wrap the instance methods, never edit the subtree:
```python
def _json(self, obj):   # line 160
    obj.setdefault('t', round(time.time(), 3))
    print(json.dumps(obj, ensure_ascii=False, allow_nan=False), flush=True)
# end() text form, line 174 — reuse for the log's stage_end line:
self._out(f'[{clock()}] {"✓" if ok else "✗"} [{self.k}/{self.n}] {st.name} ({hms(time.time() - st.t0)})' + (f': {summary}' if summary else ''))
def _out(self, text):   # line 220, non-JSON text line
```
`clock()` and `hms()` exist in the same module; import them via `porter.upstream` rather than reimplementing.

**Paths:** use `paths.user_dir() / 'logs'` (pattern of `player_tools()` in `porter/paths.py` lines 22-23).

### `porter/procs.py` (utility, event-driven)

**ctypes analog:** `packaging/nx2android.py` lines 22-25 (only existing kernel32 use):
```python
if os.name == 'nt':
    import ctypes
    k = ctypes.windll.kernel32; ids = (ctypes.c_uint * 4)()
```
Extend with `ctypes.wintypes` + explicit `restype`/`argtypes` (RESEARCH Pitfall 2). Import ctypes lazily inside the `nt` branch as here.
**adb lookup:** `toolchain.find_adb(config.load())` as in `porter/cli.py` `cmd_install` (`toolchain.find_adb(cfg)`).
**Env pattern:** `_with_progress` restores `os.environ` in `finally` (lines 93-95): set MSBuild vars in `procs.setup` **before** `_with_progress` snapshots, so they persist for the run.

### `porter/paths.py` (config) — current lines 5-8
```python
REPO = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent.parent   # the bundle: nxnative/ beside nx2android.exe
NXNATIVE = REPO / 'nxnative'
DM = NXNATIVE / 'dm'
```
Keep the word `frozen` (arch rule 10b). Add `_engine()` in the same one-line-comment style as `player_tools()`/`signing_key()`.

### `porter/cli.py` (1 hook line) — line 162
```python
return {'doctor': cmd_doctor, ..., 'config': cmd_config}[a.cmd](a)
```
becomes `return runlog.run(a, {...}[a.cmd])`.

### `porter/pipeline.py` (1 hook line) — after line 148/149
```python
self.aw = self.work / 'android'; self.logs = self.work / 'logs'
for d in (self.aw, self.logs, self.work / 'tmp'): d.mkdir(parents=True, exist_ok=True)
```
Add `runlog.build_folder(self.work, self.logs)` right after (D-08 marker + per-tool log path).

### `gui/runner.py` (bridge, streaming) — whole file is the analog (69 lines)
- `_env()` lines 11-14: add `NX2A_GUI=1`, `PYTHONPATH` when not frozen.
- `Porter.start` lines 28-35: change `setArguments(['-m', 'porter', *args])` to `[*PORTER, *args]` with `PORTER = ['-m', 'porter']` (literal must stay for arch rule 5), `setWorkingDirectory(str(user_dir()))`, add `setUnixProcessParameters(CreateNewSession)` on POSIX, `errorOccurred`.
- `_out` lines 37-45: keep line splitting / non-JSON → `say` exactly.
- `_done` lines 47-51: gate `finished.emit` on group-gone.
- `cancel` lines 53-56 (`taskkill /T /F` / `p.kill()`): becomes `stop()` with grace timer; keep taskkill as Windows fallback when the job failed.
- `call_json` lines 59-69: add `timeout`, keep stderr, `done(obj, code, fail)`.

### `gui/app.py` (hook lines only)
- `PortTab.cancel` line 174-175: `self.cancelled = True; self.porter.cancel(); self.append('[RED] cancelled')` → "stopping…", disable button; "cancelled" moves to `on_finished`.
- `on_event` (~line 187-215): add `elif e == 'log'` / `elif e == 'error'` branches in the same style as `elif e == 'result': self.result = ev`.
- `on_finished` lines 217-226: replace `f'failed after {took} (the log says why)'` with the error msg; add Open log via the `open_out` pattern (line 228):
  ```python
  QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self.result['apk']).parent)))
  ```
- `on_inspect` line 112-115: the `'No game found…'` fallback must only show when `code == 0`; otherwise stderr tail / timeout + Retry link.
- `call_json` sites: lines 110, 142, 268, 324, 338 — each callback gains the `fail` arg.
- `Window` lines 349-362: add `closeEvent`; `self.port.porter` and `self.setup.fetch` (line 253) are the two `Porter`s.
- HTML escaping: copy `append()` line 177-179's `.replace("&", "&amp;").replace("<", "&lt;")` for error text.

### `packaging/nx2android.py` — lines 8-27; only add `sys.dont_write_bytecode = True` (no new imports: arch rule 10b allows only multiprocessing, os, runpy, sys, ctypes, gui).

### `packaging/nx2android.spec` — line 22-23:
```python
exe = EXE(pyz, a.scripts, [('u', None, 'OPTION'), ('X utf8', None, 'OPTION')], exclude_binaries=True, name='nx2android', console=True, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name='nx2android', upx=False)
```
Add `codesign_identity=os.environ.get('MACOS_SIGN_IDENTITY')` and a darwin-only `BUNDLE(coll, …)` (RESEARCH Pattern 8).

### `packaging/build_bundle.py` — lines 18-32
- line 20-21: `is_local()` gate → only when `os.name == 'nt'`.
- line 23: keep `files = tracked('nxnative')` literal (arch rule), filter out `dmsh_xlate_bin/`, target `APP` vs `nx2android.app/Contents/Resources`.
- line 29-30: `git describe` → `VERSION`; add `ENGINE` hash file beside it the same way.
- line 31: `shutil.make_archive(..., 'zip', ...)` stays Windows only; tar.gz on Linux, `hdiutil` DMG on macOS.

### `tests/test_porter.py` — lines 5-10
```python
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.environ['NX2A_HOME'] = tempfile.mkdtemp(prefix='nx2a_test_home_')

from porter import config, datapack, pipeline, profiles   # noqa: E402
from porter.upstream import android_profile, game          # noqa: E402
```
Wrap only the two import lines in the RESEARCH Pattern 14 try/except.

### `tests/test_bridge.py`, `tests/test_runlog.py`, `tests/test_workflows.py`
Header + setup from `tests/test_porter.py` lines 1-7 (one-line `#` header, `sys.path.insert(REPO)`, `NX2A_HOME` tempdir before porter imports). Subprocess-test shape from `tests/test_architecture.py`:
```python
class Architecture(unittest.TestCase):
    def test_rules(self):
        r = subprocess.run([sys.executable, str(HERE / 'arch_rules.py'), str(HERE.parent)], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
```
Dense list-of-cases loop style from `tests/test_commit_msg.py` `test_accepted`. `tearDown` one-liner style: `def tearDown(self): os.environ.pop('DM_GAMES_DIR', None)`. Bridge tests must `QCoreApplication` once at module level and override `runner.PORTER`.

### `tests/fixtures/bridge/*.jsonl`
Event shape from `Progress._json` / `end` (above): `{"ev":"stage_end","k":..,"name":..,"ok":..,"summary":..,"elapsed":..,"t":..}`. Capture real output, replace paths with `<folder>`.

### `packaging/smoke_gui.py`, `packaging/glibc_floor.py`
Header comment style of `packaging/build_bundle.py` lines 1-5 (what, how to run). `glibc_floor.py`: check-then-`sys.exit(1)` style of `tests/arch_rules.py` `check(...)`. `smoke_gui.py` builds `Window` like `gui/app.py` `main` (`QApplication(argv)`, `Window()`), polls `w.games.table.rowCount()`.

## Shared Patterns

### Problem lines
`[RED] ` prefix, e.g. `PROG.say(f'[RED] {e}')` (cli.py); GUI's `append()` colours it. Use for every new error/timeout/cut-off message.

### Errors
Named `<Thing>Error` with a "what to do" message; chain with `raise X(str(e)) from e`; narrow `except (OSError, ValueError)` only where absence is expected (`porter/config.py`).

### Protocol
Additive fields/events only; one JSON object per line via `json.dumps(obj, ensure_ascii=False)` + `flush=True`. Non-JSON stdout lines become `say` in `runner._out`.

### Arch-rule invariants to keep green (`tests/arch_rules.py`)
- `gui/runner.py` contains `'-m', 'porter'` (line 95-96).
- `gui/` never imports `porter.upstream|pipeline|install|datapack` nor names engine tools outside string literals (so `gui` must not import `porter.runlog`/`procs` either if they import upstream; prefer no gui→procs import).
- `requirements.txt` contains `lz4`, `capstone`, `pillow`, `pyside6` (line 132-133).
- `packaging/nx2android.py` import whitelist; `build_bundle.py` contains `tracked('nxnative')`; `paths.py` contains `frozen`.
- No PySide6 in `porter/`.

### Style
Module header `#` block of 1-5 lines stating the job and contract (see `gui/runner.py` lines 1-3, `porter/fpslocker.py` lines 1-9); dense one-line bodies; comments cite evidence.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `.github/workflows/fork-ci.yml` | CI config | batch | No `.github/` folder exists; use RESEARCH Patterns 11 + SHA table |
| `.github/workflows/fork-release.yml` | CI config | batch | Same; use RESEARCH Patterns 8, 12, 13 |
| `requirements.in` / `requirements-build.in` + generated locks | config | n/a | Only an unpinned `requirements.txt` exists; use RESEARCH Pattern 10 commands |
| `packaging/glibc_floor.py` | script | file-I/O | No ELF tooling in repo (style analog only) |
| Windows Job Object code in `procs.py` | utility | event-driven | No Job Object / signal handling anywhere; only the ctypes import style exists |

## Metadata

**Analog search scope:** `gui/`, `porter/`, `packaging/`, `tests/`, `nxnative/scripts/build_ipa_from_nsp.py`
**Files scanned:** 12
**Pattern extraction date:** 2026-10-29
