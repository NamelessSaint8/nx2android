---
last_mapped_commit: 9d67edec2175ae5f4beadbd65f37eaa88105d132
last_mapped_at: 2026-10-29
---
# Testing Patterns

**Analysis Date:** 2026-10-29

Scope: the repository's test suites: `tests/` (run by the README command), `nxnative/dm/tools/tests/` (upstream's engine tests, run separately), and the device-side checks in `devtools/` and `docs/RELEASE_CHECK.md`. `nxnative/dm/third_party/` is vendored and has no tests in this repo's runner.

## Test Framework

**Runner:**
- Python `unittest` (standard library). No pytest, no `pytest.ini`, `tox.ini`, `conftest.py`, or `pyproject.toml`.
- Config: none. Discovery is controlled by the command line.

**Assertion Library:**
- `unittest` assertions: `assertEqual`, `assertTrue`, `assertIn`, `assertRaises` (as a context manager, with `msg=`), `assertGreater`, `assertRaises(..., msg=rows)`, `skipTest`, `skipUnless`.
- Plain `assert` statements inside the C harnesses that tests generate and compile (see "Common Patterns").

**Run Commands:**
```bash
python -m unittest discover tests                     # whole Python suite (README; includes tests/arch_rules.py via test_architecture.py)
python -m unittest tests.test_porter                  # one module
python -m unittest tests.test_porter.AndroidProfiles.test_neo   # one test
python tests/arch_rules.py                            # layer rules on their own, prints PASS/FAIL per check
python -m unittest discover nxnative/dm/tools/tests   # upstream engine tests (run from the repo root; not part of the README command)
python .githooks/commit_msg.py <message file>         # check one commit message by hand
```
Watch mode: not configured. Coverage: not configured (no `coverage` config or command in the repo).

## Test File Organization

**Location:**
- Separate from source. Python unit tests live in `tests/` at the repo root. The engine's upstream tests live beside the engine tools in `nxnative/dm/tools/tests/`.
- No co-located `*.test.*` files.

**Naming:**
- `tests/test_<area>.py`. Current modules: `test_porter.py` (19 tests, the port pipeline and profiles), `test_commit_msg.py` (4), `test_architecture.py` (1, wraps `arch_rules.py`), `test_perf_adaptive.py` (1, C controller), `test_vk_layout_cache.py` (1, C layout cache), `test_vk_present_timing.py` (1, C presentation history).
- Non-test helper: `tests/arch_rules.py` (not named `test_*`; discovered only through `test_architecture.py`).
- Test classes: `CamelCase` describing the subject (`AndroidProfiles`, `CommitMsg`, `Architecture`, `AdaptiveFrameRate`, `PresentTiming`, `LayoutCache`). Methods: `test_<behaviour>`.

**Structure:**
```
tests/
├── arch_rules.py                    # static checks of the committed tree (not a test module)
├── test_architecture.py             # runs arch_rules.py as a subprocess, asserts exit 0
├── test_commit_msg.py               # .githooks/commit_msg.py rules, loaded via importlib
├── test_porter.py                   # porter's profiles, config, datapack, pipeline pieces
├── test_perf_adaptive.py            # C adaptive frame-rate controller from perf_android.c
├── test_vk_layout_cache.py          # C descriptor-set layout cache from gfx_vk_shader.c
└── test_vk_present_timing.py        # C presentation history from gfx_vk_present.c

nxnative/dm/tools/tests/
├── test_jump_copies.py, test_nro_pack.py, test_nsp_chain.py,
    test_nsp_mac.py, test_nsp_progress.py, test_patches.py
```

## Test Structure

**Suite Organization:**
```python
# tests/test_commit_msg.py
import importlib.util, subprocess, sys, tempfile, unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / '.githooks/commit_msg.py'
spec = importlib.util.spec_from_file_location('commit_msg', HOOK)
cm = importlib.util.module_from_spec(spec); spec.loader.exec_module(cm)


def errs(text): return cm.check(cm.clean(text))


class CommitMsg(unittest.TestCase):
    def test_accepted(self):
        for m in ('fix(vk): a transfer read ...', ...):
            self.assertEqual(errs(m), [], m)

    def test_refused(self):
        for m, why in (('Vulkan backend: ...', 'the header must be'), ...):
            e = errs(m)
            self.assertTrue(any(why in s for s in e), f'{m!r} -> {e}')

if __name__ == '__main__':
    unittest.main()
```

**Patterns:**
- Every test module ends with `if __name__ == '__main__': unittest.main()`. Keep this.
- Table-driven cases: a tuple of inputs in a loop, with the message as the `msg=` argument so a failure names the input (`self.assertEqual(errs(m), [], m)`; `with self.assertRaises(ProfileError, msg=rows)`).
- Setup: module-level code for shared fixtures (the `tests/test_commit_msg.py` loads the hook once). Per-test setup via helper functions, not `setUp`.
- Teardown: `tearDown` only to undo process environment changes (`tests/test_porter.py` removes `DM_GAMES_DIR`). Temporary folders are created with `tempfile.mkdtemp(prefix='nx2a_test_...')` and not removed; keep new temp dirs under a recognizable prefix.
- Environment isolation: `tests/test_porter.py` sets `NX2A_HOME` to a temp folder at import time, before importing `porter`, so no test touches the developer's settings or signing key. Do the same for any test that would read the player folder.

**Known test-process rules:**
- No game files, toolchains, device or network are needed for `tests/`. Keep it that way; `tests/test_porter.py` states the suite "need[s] no game files, toolchains or device".
- Tests that need a host C compiler or the NDK use `skipUnless` / `skipTest`, not failure: `@unittest.skipUnless(shutil.which('cc'), 'a host C compiler is required')` and `if not cc: self.skipTest(...)`.

## Mocking

**Framework:** `unittest.mock` is used in the engine tests (`nxnative/dm/tools/tests/test_nsp_chain.py`, `test_nsp_mac.py` import `from unittest import mock`). `tests/` does not import `mock`; it uses real files in temp folders and environment variables instead.

**Patterns:**
- Prefer a real temp folder with real files over a mock: `profile_dir(rows, gid=...)` writes a throwaway `game.tsv` and `android.tsv` under a temp root and points `DM_GAMES_DIR` at it (`tests/test_porter.py`). Use the same helper shape for new profile tests.
- Environment variables as the seam: set `os.environ[...]` in the test and remove it in `tearDown` (`os.environ.pop('DM_GAMES_DIR', None)`). The C harnesses use `setenv` / `unsetenv` for the same reason.
- Stub external systems in generated C code with macros, not mocks: `tests/test_vk_layout_cache.py` defines `#define vkCreateDescriptorSetLayout make_layout` and a fake `vk_dsl_register`, so the real layout-cache helper compiles against a fake Vulkan device.

**What to Mock:**
- The Vulkan device, the Android runtime, and the presentation queue: stub at the C level in the harness (see the three C-harness tests).
- Subprocess-based tools only when the test is about the caller, not the tool.

**What NOT to Mock:**
- Pure Python logic: the commit-message rules, profile parsing (`android_profile.load` on a real temp folder), the architecture checks (run `arch_rules.py` for real on the committed tree).
- The filesystem for profile and layout tests: use temp folders.

## Fixtures and Factories

**Test Data:**
```python
def profile_dir(rows, gid='0100000000AAA000'):
    """A throwaway game profile with an android.tsv of these rows, found through DM_GAMES_DIR"""
    root = Path(tempfile.mkdtemp(prefix='nx2a_test_profiles_')); d = root / gid; d.mkdir()
    (d / 'game.tsv').write_text(f'title_id\t{gid}\nprogram_id\t{gid}\nname\tTest Game\nipa\tTestGame.ipa\nmodules\tmain sdk\n', encoding='utf-8')
    (d / 'android.tsv').write_text(''.join(f'{k}\t{v}\n' for k, v in rows), encoding='utf-8')
    os.environ['DM_GAMES_DIR'] = str(root)
    return d
```
- Real game IDs are used as known fixtures only when the test is about that game's shipped profile: `NEO = '010043B013C5C000'` in `tests/test_porter.py` (asserts its status, package, settings and `requires`). Do not add new real-game fixtures that depend on game files.
- Synthetic IDs use the `0100000000AAA000` pattern (valid title-ID shape, obviously fake).

**Location:**
- Inline in the test module. No shared fixtures directory, no factories package.
- The C source under test is read from the repo at runtime (`SOURCE = Path(__file__).resolve().parents[1] / 'nxnative/dm/android/perf_android.c'`), so the test always checks the committed code.

## Coverage

**Requirements:** None enforced. No coverage threshold, no CI coverage gate. The architecture and commit-message rules are the enforced checks.

**View Coverage:** Not configured. To measure ad hoc: `python -m coverage run -m unittest discover tests && python -m coverage report` (coverage is not in `requirements.txt`).

## Test Types

**Unit Tests (`tests/`):**
- Scope: the Python pipeline pieces (profiles, config, datapack helpers, commit-message rules, pure helpers) and the pure-logic parts of the C runtime, reached by extracting a function body from the source and compiling it with `cc`.
- Approach: table-driven cases; assert on exact outputs and on the error type and message.

**C Harness Tests (`tests/test_perf_adaptive.py`, `tests/test_vk_layout_cache.py`, `tests/test_vk_present_timing.py`):**
- Scope: the Android runtime's stateful algorithms (frame-rate step controller, descriptor-set layout cache, presentation ticket history).
- Approach: slice the function(s) out of the real `.c` file by searching for a start marker (`src.index('static const int64_t STEPS[]')`), wrap them in a generated `main()` with `assert`s, and compile and run with the host `cc`. The harness is a raw string (`r'''...'''`) that includes the sliced source and stubs for the platform calls.
- Use `shutil.which('cc') or shutil.which('clang')` to find a compiler; skip with a message when none is present.
- Keep the slice markers stable. If a refactor moves a function, the marker changes and the test fails at `src.index(...)`, which is the intended signal.

**Static / architecture tests (`tests/test_architecture.py` → `tests/arch_rules.py`):**
- Scope: the committed tree, through `git ls-files`. Checks layer rules from `docs/ARCHITECTURE.md`:
  - no game IDs, names or packages in `nxnative/dm/android/` code (string literals are ignored unless they match);
  - no title-ID branch in shared core code guarded by `DM_ANDROID` / `__ANDROID__`;
  - game profile folders hold data only, except `patches.py`;
  - every `android.tsv` key and status is in the documented set, and `playable` / `wip` profiles have a `tested` row;
  - `android_profile.py` reads every documented key;
  - `porter/` does not import a UI toolkit; GUI drives `python -m porter`;
  - no toolchain committed.
- Output format: `PASS  <check>` or `FAIL  <check>: <detail>` per check; exit 1 when any check fails.
- Add a check here when a new architecture rule is written in `docs/ARCHITECTURE.md`.

**Commit-message tests (`tests/test_commit_msg.py`):**
- Covers the accepted and refused forms, the 100-character limit, the body blank-line rule, the breaking-change footer, cleaning of git's comment and scissors lines, and the hook's exit status via a real subprocess.

**Engine tests (`nxnative/dm/tools/tests/`):**
- Upstream-style `unittest` modules with `mock` for the NSP/NRO tooling. Run them from the repo root with discovery pointed at that folder. They are not in the README command; run them when touching `nxnative/dm/tools/`.
- `nxnative/AGENTS.md` requires `dm/tools/tests/test_nsp_chain.py` to pass after changing a chain tool and `dmsh_chain.h` is regenerated (`dmsh_chain.py --header`).

**Device and release checks (not unit tests):**
- `devtools/port_check.py <bundle> <game folder>...` ports games with the player's bundle and writes each result into `docs/RELEASE_CHECK.md` between `<!-- port_check rows -->` markers. This is the release check; it needs game files and a device or toolchain.
- `devtools/soak.sh`, `devtools/burst.py`, `devtools/rec_flicker.py`, `devtools/trace_pass.sh`: on-device stability, timing and flicker diagnostics. Not automated tests.
- Behaviour fixes for a running game are verified on the device with evidence (log line, recording). See `.claude/skills/nx2android-dev/references/device-loop.md`.

**E2E Tests:** Not used.

## Common Patterns

**Async Testing:** Not used in `tests/`. The porter pipeline is synchronous; the GUI runs it as a subprocess (`gui/runner.py`) and parses its JSON events, which is tested by the device and release checks rather than by unit tests.

**Error Testing:**
```python
def test_bad_keys_are_refused(self):
    for rows in ([('status', 'great')], [('colour', 'red')], [('setting', 'volume=3')],
                 [('status', 'boots'), ('status', 'playable')]):
        d = profile_dir(rows)
        with self.assertRaises(android_profile.ProfileError, msg=rows): android_profile.load(d.name)
```
Every refusal path in a parser gets one case in this table form: the bad input, the expected error class, and `msg=` set to the input.

**C harness assertion pattern:**
```python
harness = r'''
#include <assert.h>
...
''' + controller + r'''
int main(int argc, char **argv) {
    ...
    assert(work_pct(50) == 15000000 && work_pct(90) == 27000000);
    return 0;
}
'''
# compiled with cc, run, and the returncode asserted to be 0
```

**Rendering and timing tests:** Not present. Visual results (flicker, frame pacing) are checked on the device with `devtools/rec_flicker.py` and the switch-android-port skill's playbooks.

## Adding a Test: Checklist

1. Put Python tests in `tests/test_<area>.py` with the module header comment, `sys.path` bootstrap if it imports `porter`, and `NX2A_HOME` isolation if it touches the player folder.
2. Write a table-driven method per behaviour; name the input in `msg=`.
3. Use a temp folder through a `profile_dir`-style helper; restore any `os.environ` change in `tearDown`.
4. For C logic, slice the function from the real source by a stable start marker and skip (not fail) when no compiler is found.
5. New non-trivial logic gets at least one test; trivial changes need none.
6. Run `python -m unittest discover tests` before committing. Run `nxnative/dm/tools/tests` too when `nxnative/dm/tools/` changed.

## Known Gaps

- No coverage measurement; no CI in the repository (`.github/` is not present) so none of these suites runs automatically on push. The commit-msg hook is the only automatic gate, and it is opt-in.
- The `gui/` package has no tests. Its runner's JSON parsing and cancellation are unverified in code.
- `devtools/` scripts have no tests.
- `nxnative/dm/tools/tests/` is not part of the documented command; a change there can pass `tests/` and still break engine tests.

---

*Testing analysis: 2026-10-29*
