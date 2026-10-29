---
last_mapped_commit: 9d67edec2175ae5f4beadbd65f37eaa88105d132
last_mapped_at: 2026-10-29
---
# Coding Conventions

**Analysis Date:** 2026-10-29

Scope: the repository's own code (`porter/`, `gui/`, `packaging/`, `devtools/`, `tests/`, `probes/`, `nxnative/dm/android/`, `nxnative/dm/{host,gfx,tools}/`, `nxnative/dm/games/` profiles). `nxnative/dm/third_party/` is vendored upstream code (Ryujinx) and is excluded; it follows upstream's style. `nxnative/` itself is a git subtree of seedds/nxnative and keeps upstream's conventions where they differ.

The project's own rules live in `README.md` (Commit messages), `docs/ARCHITECTURE.md` (layer rules, enforced by `tests/arch_rules.py`) and `.claude/skills/nx2android-dev/SKILL.md` ("Rules that always hold"). Those are authoritative; this document summarizes what the code actually does.

## Naming Patterns

**Files:**
- Python modules: short lowercase nouns, no underscores unless needed: `porter/adb.py`, `porter/fpslocker.py`, `porter/pipeline.py`. Compound names use underscores: `porter/push_chunked.py` (devtools), `gui/runner.py`.
- Tests: `tests/test_<area>.py` (`tests/test_porter.py`, `tests/test_commit_msg.py`). Test modules that exercise C code are named after the C file: `tests/test_vk_present_timing.py` drives `nxnative/dm/android/gfx_vk_present.c`.
- Android C sources use a subsystem prefix: `nxnative/dm/android/gfx_vk_present.c`, `gfx_vk_shader.c`, `perf_android.c`, `front_android.c`. Headers sit beside them (`gfx_vk.h`).
- Shell scripts: lowercase with underscores or none: `devtools/soak.sh`, `devtools/trace_pass.sh`.

**Functions:**
- Python: `snake_case`, verbs for actions: `inspect(folder)`, `entry(g, p)`, `all_entries(android_only=True)`, `set_value(key, value)` (`porter/config.py`). Private helpers get a leading underscore only where needed: `_parser()` in `porter/cli.py`, `_env()` in `gui/runner.py`.
- C: `snake_case` with a module prefix. Public Vulkan-backend entry points use `vk_`: `vk_shaders_open(const char *path)` in `nxnative/dm/android/gfx_vk_shader.c`, `vk_dsl_register`. File-local helpers are `static` with short names: `bundle_open_once`, `present_time_get`, `adapt_frame`, `work_pct`.
- Test methods: `test_<behaviour>` in `unittest` classes (`test_refused`, `test_accepted`, `test_bad_keys_are_refused`, `test_ticket_history`).

**Variables:**
- Python: `snake_case`. Short names are normal for local tuples and comprehension values (`g`, `p`, `k`, `v`, `ln`, `rx`).
- Module-level constants: `UPPER_CASE` (`TYPES`, `MAX_LINE`, `HEADER_RX`, `KEYS`, `STATUS` in `.githooks/commit_msg.py`, `porter/config.py`, `porter/adb.py` `LONG_PATH`).
- C globals: a `g_` prefix, and file-scope state often gathered in one anonymous struct: `static struct { ... } V;`, `static const uint8_t *g_bundle; static uint32_t g_nent;` (`gfx_vk_shader.c`).
- Environment switches are `DM_*` (`DM_VK_SHADERS`, `DM_ROOT`, `DM_FPS_PIN`, `DM_ADAPT_UP_PCT`); Vulkan-related log helper is `VKLOG`.

**Types:**
- Python classes: `PascalCase`, dataclasses for records and options: `Options` (`porter/pipeline.py`), `Entry` (`porter/profiles.py`), `Item` (`porter/fetch.py`), `Adb` (`porter/adb.py`).
- Exceptions: `<Thing>Error` deriving from `Exception`: `AdbError` (`porter/adb.py`), `ToolError` (`porter/toolchain.py`), `ProfileError` (`nxnative/dm/android/tools/android_profile.py`), `BuildError` (upstream, used in `porter/pipeline.py`). A single-purpose refusal can be a bare subclass: `class Refused(Exception): pass` in `porter/fpslocker.py`.
- C types: `typedef struct __attribute__((packed)) { ... } bent;` (short lowercase typedef names for on-disk records). Opaque `VkXxx` Vulkan handles are used as declared.

## Code Style

**Formatting:**
- No formatter config is committed (no `pyproject.toml`, `.prettierrc`, `.clang-format`, `setup.cfg`). Match the surrounding file.
- Python: 4-space indent. Line length is loose; long lines of 150+ characters appear in `porter/cli.py` and `porter/pipeline.py`. Prefer wrapping only when a line becomes hard to scan.
- Python is written in a dense one-line style: short bodies are placed on the same line as the `if`, `for` or `def` (`if not errs: return 0`, `def tearDown(self): os.environ.pop('DM_GAMES_DIR', None)`, `try: c = json.loads(...)`, `except (OSError, ValueError): c = {}`). Use this for guard clauses and one-statement bodies; use full blocks for multi-step logic.
- Several statements share a line separated by `;` (`p = paths; out = []`, `c = load(); c[key] = value; save(c)`). Acceptable where the lines are a related pair.
- C: 4-space indent, braces on the same line, `if (...) { ...; }` one-liners common in hot-path code. Lines wrap at roughly 150 to 180 characters. Comments are `//` (both in the Android/Vulkan code and the upstream Ryujinx-derived tree); block comments `/* */` appear only in headers.
- Line endings are LF everywhere (`.gitattributes`: `* text=auto eol=lf`). Shell scripts and assembly run on device and in the NDK build; do not introduce CRLF.

**Linting:**
- Not configured. No flake8, ruff, pylint, mypy, clang-tidy or clang-format configs are committed.
- `tests/arch_rules.py` is the only enforced static check. It parses the committed tree and fails on: game IDs, game names or packages in core code (`nxnative/dm/android/`); title-ID branches in Android-guarded shared code; non-data files inside `nxnative/dm/games/<id>/` (only `patches.py` may hold code); `android.tsv` keys and status values outside the documented set; GUI imports (PySide6) inside `porter/`; toolchains committed to the repo.
- Python compatibility: 3.11 or later per `requirements.txt`. `backports.zstd` is pinned only for Python below 3.14.
- Shell: scripts should be safe under `set -e`-style use; existing scripts (`devtools/soak.sh`) are plain POSIX-ish bash.

## Import Organization

**Order (Python):**
1. Standard library, one `import` line with comma-separated modules (`import ast, re, subprocess, sys` in `tests/arch_rules.py`; `import contextlib, hashlib, os, shlex, shutil, subprocess, tempfile, time` in `porter/adb.py`). `from pathlib import Path` follows on its own line.
2. Third-party (`PySide6` in `gui/`, `lz4`/`capstone`/`pillow` etc. only in packaging or upstream code).
3. First-party: `from porter import config, datapack, ...` then `from porter.upstream import ...` (`porter/pipeline.py`).

Tests add a path bootstrap before first-party imports: `sys.path.insert(0, str(REPO))` followed by `from porter import ... # noqa: E402` (`tests/test_porter.py`). Use the same pattern for new test files.

**Path Aliases:** None. Imports are absolute from the package root (`porter.`, `gui.`); there are no relative imports in `porter/` or `gui/`.

**C includes:** Project headers first in the upstream-style files (`#include "gfx_vk.h"`, `#include "nvn_hmap.h"`), then system headers (`<fcntl.h>`, `<string.h>`, `<sys/mman.h>`). `gfx_vk_shader.c` and `perf_android.c` follow this mix; keep it within a file.

## Error Handling

**Python patterns:**
- Errors that the user should see are raised as a named exception with a message that says what to do: `raise BuildError('this folder has only NSZ / XCZ files: decompress them to NSP / XCI first (nsz -D with your prod.keys), ...')` (`porter/pipeline.py` / `porter/upstream.py`). Messages name the file and the fix.
- Wrap a lower-level error into the layer's own error with chaining: `except toolchain.ToolError as e: raise BuildError(str(e)) from e` (`porter/pipeline.py`).
- Ignore a failure only where absence is expected, and say so with the narrowest exception: `except (OSError, ValueError): c = {}` (`porter/config.py`) and `except OSError: shutil.copy2(p, q)` (`porter/adb.py`).
- Retries are explicit and logged, not silent: `Adb.run(..., retries=3)` logs `adb {cmd} failed (...), retry N` before retrying, and does not retry an `install` failure because it is an answer, not a dropped link (`porter/adb.py`).
- Input validation at the boundary raises the module's error type with the offending line: `raise ProfileError(f'{self.path}:{n}: unknown key {k!r} (keys: ...)')` (`nxnative/dm/android/tools/android_profile.py`).

**CLI exit codes:** `porter/cli.py` returns `0` done, `1` error, `130` interrupted. The top-level handler prints the error and returns the code; `KeyboardInterrupt` maps to 130.

**C patterns (Android/Vulkan):**
- Errors are logged and the code degrades; it does not abort the process: `VKLOG("[RED] no shader bundle at %s: nothing will be drawn", path); ... return;` (`nxnative/dm/android/gfx_vk_shader.c`).
- Vulkan calls are wrapped in a checking macro: `VKCHK(call)` (used in the layout-cache harness in `tests/test_vk_layout_cache.py` and the `gfx_vk` sources).
- Resources are closed on every failure path before returning: `if (fd >= 0) close(fd);`.

## Logging

**Framework:** None. Output is `print` in CLI code and a `say`/`PROG.say` helper for progress events (`porter/upstream.py`, `porter/cli.py`). Android runtime logging is `LOG` with a `VKLOG` wrapper that prefixes `[vk] ` (`nxnative/dm/android/gfx_vk.h`).

**Patterns:**
- Prefix a problem line with `[RED] ` so the GUI can colour it and users can grep for it: `PROG.say(f'[RED] {e}')` (`porter/cli.py`), `say(f'[RED] {self.derived}: ...')` (`porter/pipeline.py`), and in C `VKLOG("[RED] ...")`. The project rule is that logs for something unimplemented or wrong start with `[RED] ` (`.claude/skills/nx2android-dev/SKILL.md`).
- Machine output: `--json` prints one JSON document; `--progress json` prints one JSON event per line with `ev` keys (`stage`, `step`, `progress`, `stage_end`, `say`, `result`). Do not mix human text into a JSON stream; the GUI (`gui/runner.py`) parses stdout line by line and treats non-JSON lines as `say` events.
- Log in English only.
- Port logs for a run go to `<game folder>/port_check.jsonl` (`devtools/port_check.py`).

## Comments

**When to Comment:**
- Comments state the *why* and cite the evidence: a log line, a crash address, a census, or a game and build that exposed the problem. Example from `porter/adb.py`: the comment on `LONG_PATH` explains the Windows 260-character limit and the Viractal bundle that hit it. Keep this habit; the project's rule is "measure, then change" and the evidence goes in the comment beside the fix.
- File headers: Python modules open with a `#` comment block of one to five lines describing the module's job and the contract (`porter/config.py`, `porter/pipeline.py`, `gui/runner.py`). C files open with `//` lines in the same role (`gfx_vk_shader.c`).
- Comments may name a game a rule was found with (allowed by the SKILL rules); code branches may not depend on a game (enforced by `tests/arch_rules.py`).

**JSDoc/TSDoc:** Not applicable. Python uses docstrings only where helpful, typically a one-line triple-quoted string for a public function or module (`"""What a game folder holds, without extracting anything: ..."""` in `porter/pipeline.py`, `"""Exercise the runtime layout cache with ... stubbed."""` in tests). Docstrings are short and imperative or descriptive, not Sphinx-style.

## Function Design

**Size:** Most functions are short. The pipeline and CLI are the exceptions: `porter/pipeline.py` and `porter/cli.py` hold long sequences of steps. Split out a helper when a step is reused, not just to shorten a function.

**Parameters:** Positional for the one or two obvious arguments; keyword arguments with defaults for options (`Adb(exe, serial=None, timeout=120, log=print)`). Options that travel together go in a dataclass (`Options` in `porter/pipeline.py`) rather than long argument lists.

**Return Values:** Return the value directly. Use `None` for "not found" (`profiles.by_title`), and return a status code from CLI entry points. Return tuples for a small fixed pair (`app, fam`).

**Type hints:** Sparse. About a dozen modules in `porter/` and `gui/` use `->` annotations; most do not. Add annotations to new public functions in `porter/` when they clarify a return type; do not retrofit unrelated code.

## Module Design

**Exports:** No `__all__` lists. Modules expose their functions and classes directly. `porter/__init__.py` is minimal; import specific modules (`from porter import config`).

**Barrel Files:** Not used. Import from the module that defines the name.

**Data over code in game profiles:** A game is data: `nxnative/dm/games/<title ID>/game.tsv`, `android.tsv`, and optionally `patches.py` (the only code allowed in a profile folder). Behaviour that is true for a game goes into a profile key (`setting`, `env`, `overlay`, `requires`), never into a per-game branch in shared code. Profile keys are the set in `android_profile.py` (`status`, `tested`, `package`, `orientation`, `requires`, `setting`, `env`, `overlay`); a new key must be added there and to `KEYS` in `tests/arch_rules.py`.

**Layering:** `porter/` is the headless pipeline and CLI and must not import PySide6. `gui/` only drives `python -m porter` as a subprocess (`gui/runner.py` uses `QProcess`). The core in `nxnative/dm/{host,gfx,tools}/` stays platform-neutral; Apple- or Android-only code sits behind `__APPLE__` / `__ANDROID__` / `DM_TARGET` guards, and Android-only code lives in `nxnative/dm/android/`. Keep upstream merges easy: changes to `nxnative/dm/{host,gfx,tools,third_party}` stay small.

## Commit Messages

Conventional Commits 1.0.0 with commitlint's `config-conventional` types (README "Commit messages"; checked by `.githooks/commit_msg.py`).

- Header: `<type>[(<scope>)][!]: <description>`. Types: `build`, `chore`, `ci`, `docs`, `feat`, `fix`, `perf`, `refactor`, `revert`, `style`, `test`. Lower case type.
- Scope is optional and free: the part touched. Seen in history: `vk`, `android`, `audio`, `movie`, `fps`, `porter`, `gui`, `profile`, `status`, `release`, `core`, `nvn`, `packaging`, `hooks`. The git log uses `feat(profile): <Game> plays on the Legion Y700 at 60 fps` for game status, `docs(status): ...` for `docs/PORT_STATUS.md`, `fix(vk): ...` for backend fixes, `chore(release): version 0.1.2` for releases.
- Description: no full stop at the end; may start with a capital for game and API names (`feat(profile): Super Mario Bros. Wonder plays ...`, `feat(core): take upstream's Unity 6000.0 Shader layout`). Lowercase is the common case for mechanisms (`fix(movie): time held in the background ...`).
- Header, body and footer lines at most 100 characters; a lone URL may run longer.
- Body after one blank line. Footers: `Co-Authored-By: ...`, or `BREAKING CHANGE: <what breaks>` (capitalized) with `!` after the type or scope.
- Git-made messages (`Merge ...`, `Revert "..."`, `fixup! ...`) are accepted as is.
- The hook is opt-in: `git config core.hooksPath .githooks` enables `.githooks/commit-msg`, which runs `.githooks/commit_msg.py` with the first Python 3 it finds (`py -3`, `python3`, `python`). Bypass only with `--no-verify`.

## Git Hooks

- `.githooks/commit-msg` is a POSIX `sh` wrapper that finds Python 3 and execs `.githooks/commit_msg.py "$1"`. If no Python is found it refuses the commit.
- `.githooks/commit_msg.py` is the rule set: `TYPES`, `MAX_LINE = 100`, a header regex, and the `clean()` step that drops comment lines and anything below the `git commit -v` scissors line before checking. Its behaviour is pinned by `tests/test_commit_msg.py`.

## Branches and Commits

- Work on `main` for routine changes; feature work merges in from named branches (the log shows `Merge PR 5 (vulkan11)` and `Merge main into uo-global`).
- Commit only when asked. Commit messages end with the attribution line the session gives.
- Keep a change's docs in the same commit: `docs/ARCHITECTURE.md` when a layer, key or stage changes; `docs/PORT_STATUS.md` when a game's status changes; the `android.tsv` header comment with what was tested.

---

*Convention analysis: 2026-10-29*
