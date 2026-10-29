---
last_mapped_commit: 9d67edec2175ae5f4beadbd65f37eaa88105d132
last_mapped_at: 2026-10-29
---
# Codebase Structure

**Analysis Date:** 2026-10-29

## Directory Layout

```
nx2android/                         # repo root
├── gui/                            # PySide6 desktop app (python -m gui)
├── porter/                         # headless port pipeline and CLI (python -m porter)
├── packaging/                      # Windows bundle: PyInstaller spec, builder, INSTALL.md
├── nxnative/                       # engine: git subtree of upstream nxnative + Android port
│   ├── dm/
│   │   ├── host/                   # shared core: Horizon host (hle_*.c), entry.S, crash.c
│   │   ├── gfx/                    # shared core: NVN layer (gl/, metal/, vk/, nvn/, tex/, tools/, tests/)
│   │   ├── tools/                  # shared core: rewriter, shader split, NSO/NRO tools, nx_extract
│   │   ├── android/                # Android runtime: gfx_vk_*.c, front_android.c, build.py, apk/, tools/, shaders/
│   │   ├── ios/                    # iOS app (Sources/, project.yml, tests/, tools/)
│   │   ├── games/                  # game profiles, one folder per title ID (data only)
│   │   ├── third_party/            # vendored upstream: flip, libvpx, macnativegames, ryujinx, stb_vorbis, vulkan-headers
│   │   └── .gitignore
│   ├── scripts/                    # build_ipa_from_nsp.py (reused by porter)
│   └── docs/                       # development.md, agents/, geometry-metal-research.md, images/
├── devtools/                       # scripts for a connected device (push, record, soak, traces)
├── probes/                         # C probes (cpuprobe.c, vkprobe.c, vkzc.c) and probes/app/ (APK builder)
├── tests/                          # unittest tests (python -m unittest discover tests): porter, architecture rules, perf, Vulkan helpers
├── docs/                           # ARCHITECTURE.md, PORT_STATUS.md, RELEASE_CHECK.md, images/
├── .githooks/                      # commit-msg hook and commit_msg.py
├── .claude/                        # Claude Code settings and skills
├── README.md                       # user and developer entry
├── RESEARCH.md                     # research notes
├── requirements.txt                # Python deps (PySide6 for GUI; CLI runs without it)
├── .gitattributes, .gitignore
└── nx2android.code-workspace       # VS Code workspace (untracked)
```

## Directory Purposes

**`gui/`:**
- Purpose: The desktop app for players. Runs `porter` as a child process; holds no pipeline logic.
- Contains: `__init__.py` (one-line purpose comment), `__main__.py` (entry), `app.py` (Window, PortTab, SetupTab, GamesTab, `main`), `runner.py` (Porter, call_json).
- Key files: `gui/app.py`, `gui/runner.py`.
- Platform: Qt via PySide6; `Fusion` style set in `gui/app.py` `main`. Font is `Consolas` on Windows and `Menlo` elsewhere (`gui/app.py` `PortTab`). Process kill uses `taskkill` on Windows and `QProcess.kill` elsewhere (`gui/runner.py` `Porter.cancel`). The shipped build targets Windows x64 only (`packaging/build_bundle.py`).

**`porter/`:**
- Purpose: The port pipeline, its CLI, and everything the GUI calls.
- Contains: `cli.py` (argparse, `main`), `pipeline.py` (`Options`, `Port`, `inspect`, `emit_result`), `paths.py` (REPO, NXNATIVE, DM, `user_dir`, `signing_key`), `config.py`, `toolchain.py`, `fetch.py`, `upstream.py`, `install.py`, `adb.py`, `datapack.py`, `profiles.py`, `fpslocker.py`.
- Key files: `porter/cli.py`, `porter/pipeline.py`, `porter/paths.py`.
- Size: about 1,400 lines across 15 files.

**`packaging/`:**
- Purpose: Build the zip the player downloads.
- Contains: `nx2android.spec` (PyInstaller spec), `build_bundle.py` (builds the bundle, copies tracked `nxnative/` files beside the executable, zips), `build_bootloader.py`, `nx2android.py` (frozen entry dispatcher), `INSTALL.md`.
- Generated: `dist/` and `build/pyinstaller/` at the repo root (by the build; not committed).

**`nxnative/`:**
- Purpose: The engine and all game profiles. Shared with the iOS port upstream.
- Contains: `dm/` (engine), `scripts/`, `docs/`, `AGENTS.md` (agent notes for this subtree), `README.md`, `LICENSE`, `.gitignore`.
- Committed: Yes (subtree). Bundled: `build_bundle.py` copies every git-tracked file here.

**`nxnative/dm/host/`:**
- Purpose: The shared Horizon host. Service stand-ins named `hle_<service>.c` (for example `hle_fs.c`, `hle_hid.c`, `hle_audren.c`, `hle_codec.c`, `hle_fpslock.c`, `hle_haptics.c`).
- Key files: `dm.h`, `dm_input.h`, `dm_uc.h`, `entry.S`, `crash.c`, `front.h`, `front_mac.m` (Mac front), `haptics_apple.m`, `Makefile`.

**`nxnative/dm/gfx/`:**
- Purpose: NVN graphics layer with backends.
- Contains: `nvn/`, `gl/`, `metal/`, `vk/`, `tex/`, `tools/`, `tests/`, `hle_nv.c`, `hle_vi.c`, `README.md`, `nvn_metal_mapping.md`.

**`nxnative/dm/tools/`:**
- Purpose: Build-time tools that work on Switch binaries: `patch_nso.py` (rewriter), `shader_split.py` (named in the port), `nso.py`, `nso2elf.py`, `nacp.py`, `nro_collect.py`, `sdk_patches.py`, `nx_extract/` (.NET project), `ghidra/`, `tests/`.
- Note: Upstream per-game rewrite cuts are keyed by build ID in `patches.py` and `sdk_patches.py`.

**`nxnative/dm/android/`:**
- Purpose: The Android runtime and its build.
- Contains:
  - `front_android.c`, `gfx_common.c`, `gfx_null.c`, `gfx_vk_core.c`, `gfx_vk_exec.c`, `gfx_vk_present.c`, `gfx_vk_shader.c`, `gfx_vk_tex.c`, `gfx_vk.h`: Vulkan backend and front end
  - `haptics_android.c`, `perf_android.c`, `movie_avc.c`, `overlay_layout.h`, `overlay_default.tsv`, `font5x7.h`
  - `build.py` (NDK build; writes `game_profile.h` and `android_profile.h`)
  - `apk/mkapk.py` (APK writer, signed with the player's key)
  - `tools/`: `shader_vk.py`, `android_profile.py`, `darwin2elf.py`
  - `shaders/`: shader sources
  - `compat/`: compatibility shims

**`nxnative/dm/games/<title ID>/`:**
- Purpose: One folder per game. Data only, except `patches.py`.
- Contains: `game.tsv`, shader tables, `patches.py`, `android.tsv` (present on Android-supported titles).
- Counts at analysis time: 62 folders with a `0100…` title ID; 14 with `android.tsv`. `docs/ARCHITECTURE.md` and `nxnative/AGENTS.md` describe a different total (54 / 53); the folder count is the source of truth for this map.
- Key example: `nxnative/dm/games/010015100B514000/` (Super Mario Bros. Wonder).

**`nxnative/dm/ios/`:**
- Purpose: iOS app from upstream. Not built by this repository's Android pipeline.
- Contains: `Sources/`, `project.yml`, `tests/`, `tools/`.

**`nxnative/dm/third_party/`:**
- Purpose: Vendored third-party code. Do not map internals; project code calls into it.
- Contains: `flip`, `libvpx`, `macnativegames`, `ryujinx` (the shader translator source used by the `translator` stage through `dm/gfx/tools/dmsh_xlate`), `stb_vorbis`, `vulkan-headers`, plus `README.md`.

**`devtools/`:**
- Purpose: Scripts for bringing up a game on a connected device.
- Key files: `device.py` (device selection from `devtools/device.json` or `NX2A_DEVICE`), `push_chunked.py`, `soak.sh`, `trace_pass.sh`, `rec_flicker.py`, `burst.py`, `port_check.py`, `nso_image.py`, `dmsv_extract.py`, `ppm2png.py`, `spv_support_use.py`.
- Note: The port never imports these.

**`probes/`:**
- Purpose: Device probes built with the NDK: `cpuprobe.c`, `vkprobe.c`, `vkzc.c`; `probes/app/` holds `probeapp.c`, `font5x7.h`, and `mkapk.py`.

**`tests/`:**
- Purpose: Tests for porter and for architecture rules. Run with `python -m unittest discover tests`; they need no game files, toolchains or device.
- Key files: `arch_rules.py` (rules from `docs/ARCHITECTURE.md`, run by `test_architecture.py`), `test_architecture.py`, `test_porter.py`, `test_commit_msg.py`, `test_perf_adaptive.py`, `test_vk_present_timing.py`, `test_vk_layout_cache.py`.

**`docs/`:**
- Purpose: Human documentation. `ARCHITECTURE.md` (layers and rules), `PORT_STATUS.md` (which games play), `RELEASE_CHECK.md` (checked versions), `images/` (game screenshots).

**`.githooks/`:**
- Purpose: Git hooks. `commit-msg` calls `commit_msg.py` (enforced by `tests/test_commit_msg.py`).

## Key File Locations

**Entry Points:**
- `gui/__main__.py`: `python -m gui`
- `porter/__main__.py`: `python -m porter`
- `packaging/nx2android.py`: frozen bundle executable
- `nxnative/dm/android/build.py`: NDK host build
- `nxnative/dm/android/apk/mkapk.py`: APK writer

**Configuration:**
- `requirements.txt`: Python dependencies
- `porter/config.py`: saved player settings (in `user_dir()`, not in the repo)
- `porter/paths.py`: where paths resolve
- `nxnative/dm/android/overlay_default.tsv`: default on-screen gamepad layout
- `nxnative/dm/games/<title ID>/android.tsv`: per-game Android settings

**Core Logic:**
- `porter/pipeline.py`: port stages
- `nxnative/dm/host/hle_*.c`: service stand-ins
- `nxnative/dm/android/gfx_vk_*.c`: Vulkan replay
- `nxnative/dm/tools/patch_nso.py`: rewriter

**Testing:**
- `tests/`: all Python tests; `nxnative/dm/gfx/tests/` and `nxnative/dm/tools/tests/` for engine-side tests

## Naming Conventions

**Files:**
- Python modules: lowercase, underscores (`porter/fpslocker.py`, `tools/shader_vk.py`)
- Tests: `test_<area>.py` in `tests/` (`tests/test_vk_layout_cache.py`)
- Engine C files: `hle_<service>.c` for service stand-ins, `gfx_vk_<part>.c` for Vulkan parts, `*_android.c` / `*_apple.m` for platform-specific code
- Profile folders: exact 16-character title ID in upper case (`nxnative/dm/games/010015100B514000/`)
- Generated files: `<App>.apk`, `<App>-data/`, `<title ID>_build/` (see `porter/pipeline.py` `app_stem`)

**Directories:**
- Lowercase, single word where possible (`gui`, `porter`, `gfx`, `host`)
- Title IDs upper-case hex for profiles

**Code style:**
- Python: one import line per module group; short one-liner functions and classes are common (`gui/runner.py`, `porter/paths.py`).
- Comments are the module's first lines, describing purpose and rules.

## Where to Add New Code

**New GUI screen or tab:**
- Primary code: `gui/app.py` (add a `QWidget` subclass like `PortTab`, then `Window.__init__` `addTab`). If the file grows, split a tab into `gui/<name>.py` and import it from `gui/app.py`.
- Process calls: `gui/runner.py` (`Porter` for long commands, `call_json` for short ones)
- Tests: none exist for `gui/`; add headless logic to `porter/` and test that.

**New GUI-visible feature with logic:**
- Logic: `porter/` (new module or `porter/pipeline.py` method)
- Command: `porter/cli.py` (`_parser` add subparser, `cmd_<name>`, dispatch in `main`); support `--json` and `--progress json` as the existing commands do
- Tests: `tests/test_porter.py` (or a new `tests/test_<area>.py`)

**New port stage:**
- Implementation: a method on `Port` in `porter/pipeline.py`, called from `Port.run`
- Caching: keyed by inputs, as `extract`, `rewrite`, `shaders` do

**New game:**
- Profile: `nxnative/dm/games/<title ID>/` (`game.tsv`, shader tables, optional `patches.py`, `android.tsv`)
- Android support: `status`, `tested`, and `package` keys in `android.tsv`; the keys are checked by `tests/arch_rules.py`
- Do not add title IDs or names to `nxnative/dm/android/` (enforced)

**New Android runtime code:**
- Implementation: `nxnative/dm/android/` (C for runtime; `.py` for build tools)
- Platform guard: `DM_ANDROID` or `__ANDROID__`
- Keep changes that also touch the shared core small: they are merged with `git subtree pull`

**New shared-core code:**
- Implementation: `nxnative/dm/host/`, `nxnative/dm/gfx/`, or `nxnative/dm/tools/`
- Platform guard: `__APPLE__` / `DM_ANDROID`; no title-ID branches (checked by `tests/arch_rules.py`)

**New utilities for porter:**
- Shared helpers: `porter/paths.py` (location helpers), `porter/config.py` (settings)

**New devtools script:**
- Implementation: `devtools/<name>.py` or `.sh`. Must not be imported by `porter/`.

## Special Directories

**`nxnative/dm/games/`:**
- Purpose: Game profiles
- Generated: Partly. `build.py` generates `game_profile.h` and `android_profile.h` at build time, not in this folder.
- Committed: Yes

**`nxnative/dm/third_party/`:**
- Purpose: Vendored upstream code (`ryujinx`, `libvpx`, and others)
- Generated: No
- Committed: Yes (vendored)

**`.planning/`:**
- Purpose: GSD planning and codebase maps (this directory)
- Generated: Yes (by mapping tools)
- Committed: Not decided by this map

**`dist/`, `build/`, `tools/` (at repo root, when present):**
- Purpose: Local bundle output, PyInstaller work files, and developer toolchains (`porter/paths.py` `LOCAL_TOOLS`)
- Generated: Yes
- Committed: No (`/dist/`, `/build/`, `/tools/` are in `.gitignore`)

**`<game folder>/<title ID>_build/`:**
- Purpose: Port outputs (extract, android, APK and data pack), kept beside the player's game files
- Generated: Yes
- Committed: No (outside the repo)

---

*Structure analysis: 2026-10-29*
