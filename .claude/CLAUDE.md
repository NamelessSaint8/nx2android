<!-- GSD:project-start source:PROJECT.md -->

## Project

**nx2android**

nx2android turns a player's own Nintendo Switch game dump into a native Android app. It rewrites the game's ARM64 code to run on Android, replays NVN graphics on Vulkan, translates the shaders, and builds a signed APK plus a data pack, then installs both over adb. Today the shipped tool is a thin PySide6 GUI over a headless CLI, available only as a Windows bundle. This milestone reworks that GUI and ships it on Windows, macOS and Linux for the developer and a few testers.

**Core Value:** A tester on any supported host (Windows x64, macOS Apple Silicon, Linux x64, Linux arm64) can take their own Switch dump and get a working port onto their Android device through the GUI, without help.

### Constraints

- **Upstream compatibility**: keep syncing shirai91/nx2android, so diffs to shared files stay small and mergeable. The rework should live mostly in new or GUI-owned files.
- **Engine subtree**: changes to `nxnative/dm/{host,gfx,tools,third_party}` stay small and platform-guarded, because they merge with `git subtree pull`.
- **Architecture**: the GUI holds no pipeline logic; every rule lives in `porter/` and reaches the GUI through the JSON protocol. A new CLI flag is added in `porter/cli.py` first. This is enforced by `docs/ARCHITECTURE.md` and `tests/arch_rules.py`.
- **No game-specific code in the Android runtime**: per-title data goes in `nxnative/dm/games/<title ID>/` (enforced by `tests/arch_rules.py`).
- **Toolchains are not bundled**: NDK, .NET and adb are downloaded by Setup or supplied by the player. On Linux arm64 there are no official Google NDK or platform-tools builds, so the tool uses distro adb and a community arm64 NDK.
- **macOS distribution**: Developer ID signing plus notarization, which means hardened runtime and entitlements for the frozen Python and the child processes it launches. The signing secrets live in GitHub Actions.
- **Python**: 3.11+ for dev runs; bundles ship 3.14. Safe tar extraction needs `filter='data'` and the CVE-2025-4517 fix (3.11.13 / 3.12.11 / 3.13.4+).
- **Android target**: arm64-v8a, Android 10+ (minSdk 29), Vulkan 1.3, BC texture support.
- **Legal**: never ship keys, game files or FPSLocker configs.

<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->

## Technology Stack

## Languages

- Python 3.11+ - the port pipeline and CLI (`porter/`), the desktop GUI (`gui/`), the packaging scripts (`packaging/`), the dev tools (`devtools/`), and the engine's build and shader tools under `nxnative/dm/android/` and `nxnative/dm/gfx/tools/`. The `porter/` code uses `importlib.util`, `dataclasses` and `tarfile` filters with fallbacks for 3.11.
- C (C11 for the host, the Android runtime, and probes) - the game host and Android runtime: `nxnative/dm/host/*.c`, `nxnative/dm/android/*.c`, `nxnative/dm/gfx/**/*.c`, `nxnative/dm/third_party/libvpx/`, `nxnative/dm/third_party/stb_vorbis/stb_vorbis.c`, `probes/*.c`.
- AArch64 assembly - the guest entry and thunks: `nxnative/dm/host/entry.S`, `nxnative/dm/gfx/nvn/nvn_entry.S`, and the generated `nvn_thunks.S`. Mach-O assembly is converted to ELF for Android by `nxnative/dm/android/tools/darwin2elf.py`.
- Objective-C (ARC) - the Apple host and Metal backend: `nxnative/dm/host/front_mac.m`, `nxnative/dm/host/haptics_apple.m`, `nxnative/dm/gfx/vk/hle_vk.m` (Vulkan layer on Metal), `nxnative/dm/gfx/metal/`, `nxnative/dm/gfx/nvn/nvn_mtl.m`. Compiled only on macOS (`nxnative/dm/host/Makefile` links `-framework Metal -framework Foundation`).
- C# (.NET 10, `net10.0`) - the NSP/XCI extractor and the shader translator: `nxnative/dm/tools/nx_extract/nx_extract.csproj` (LibHac 0.19.0), `nxnative/dm/gfx/tools/dmsh_xlate/dmsh_xlate.csproj` (references Ryujinx projects under `nxnative/dm/third_party/ryujinx/src/`).
- GLSL - the Android backend's own small shaders, compiled by the NDK's `glslc` with `--target-env=vulkan1.1` (`nxnative/dm/android/shaders/`, invoked from `nxnative/dm/android/build.py`).
- Swift and YAML (XcodeGen) - the iOS app only: `nxnative/dm/ios/Sources/Launcher.swift`, `nxnative/dm/ios/project.yml`. No iOS build is part of the Android port.
- Shell (POSIX `sh`) - `.githooks/commit-msg`, `devtools/soak.sh`, `devtools/trace_pass.sh`.
- Python packaging via PyInstaller's waf build: `packaging/build_bootloader.py` compiles the launcher (needs Microsoft C++ Build Tools on Windows).

## Runtime

- Python 3.11 or later (README.md, `porter/toolchain.py` `checks()` requires `>= (3, 11)`). `porter/config.py`-level code and `porter/toolchain.py` use `compression.zstd` on Python 3.14+ and fall back to `backports.zstd` before that.
- Windows, macOS or Linux. Paths and the settings folder branch by OS in `porter/paths.py` (`%APPDATA%\nx2android` on Windows, `~/Library/Application Support/nx2android` on macOS, `$XDG_CONFIG_HOME`/`~/.config/nx2android` elsewhere; `NX2A_HOME` overrides).
- Bundled player runtime: a PyInstaller build of the same Python (`packaging/nx2android.spec`, `packaging/nx2android.py`) so the player does not install Python.
- Android 10 minimum (`MIN_SDK = 29`), target SDK 36 (`TARGET_SDK = 36`) in `nxnative/dm/android/apk/mkapk.py`.
- ABI: `arm64-v8a` only (`lib/arm64-v8a/lib<name>.so` in `mkapk.py`; `--target=aarch64-linux-android<api>` in `nxnative/dm/android/build.py`).
- Native activity: `android.app.NativeActivity`, no Java or Kotlin code (`hasCode=false`). Only `android.permission.VIBRATE` is requested.
- Vulkan 1.3 instance (`VK_API_VERSION_1_3` in `nxnative/dm/android/gfx_vk_core.c`) with a Vulkan 1.2/1.3 feature/extension set; the device must read BC-compressed textures (per `docs/PORT_STATUS.md` and `porter/install.py` `bc_textures()`).
- pip - Python dependencies, `requirements.txt` (no lockfile; versions are not pinned).
- .NET SDK 10 - restores NuGet packages for `nx_extract` and `dmsh_xlate` (`nxnative/dm/third_party/ryujinx/Directory.Packages.props` centrally pins the Ryujinx dependency versions, e.g. Avalonia 12.1.1, SkiaSharp 3.119.4; only the Shader/Common projects are built).
- Lockfile: missing. `requirements.txt` has no pins; no `packages.lock.json` or `poetry.lock` is present.

## Frameworks

- PySide6 (Qt for Python) - desktop GUI, `gui/app.py`, `gui/runner.py`. Imported from `PySide6.QtWidgets`, `PySide6.QtCore`, `PySide6.QtGui`. Optional at run time: the CLI (`python -m porter`) runs without it (see the comment in `requirements.txt`).
- NDK native frontend - `ANativeActivity_onCreate` in `nxnative/dm/android/front_android.c` (NativeActivity, no framework).
- Vulkan (system `libvulkan.so`, headers vendored in `nxnative/dm/third_party/vulkan-headers/`) - Android graphics backend `nxnative/dm/android/gfx_vk_*.c`.
- Metal (Apple) - Mac/iOS backend `nxnative/dm/gfx/metal/`, `nxnative/dm/gfx/nvn/nvn_mtl.m`.
- Upstream nxnative engine (git subtree at `nxnative/`) - the Horizon OS host, NVN graphics layer and rewriter. Not a framework dependency; vendored source.
- Python `unittest` - the test suite under `tests/` (`python -m unittest discover tests`). Files: `tests/test_porter.py`, `tests/test_architecture.py`, `tests/test_commit_msg.py`, `tests/test_perf_adaptive.py`, `tests/test_vk_layout_cache.py`, `tests/test_vk_present_timing.py`. Layer rules are checked by `tests/arch_rules.py`.
- Test helpers in the engine: `nxnative/dm/gfx/tests/Makefile`, `nxnative/dm/gfx/tex/tests/Makefile`, `nxnative/dm/host/tests/Makefile`.
- On-device probes (not unit tests): `probes/app/probeapp.c`, `probes/vkprobe.c`, `probes/cpuprobe.c`, `probes/vkzc.c`.
- Python `pyinstaller` (not pinned; build-time only) - `packaging/nx2android.spec`, run by `packaging/build_bundle.py`.
- Android NDK r27c (`NDK_REVISION = '27.2.12479018'` in `porter/toolchain.py`) - clang (`toolchains/llvm/prebuilt/*/bin/clang`), `lld` (`-fuse-ld=lld`), `llvm-strip`, `glslc` from `shader-tools/`. Built by `nxnative/dm/android/build.py` (`--api` default 31; the APK's `minSdk` is 29).
- Apple clang + Make - `nxnative/dm/host/Makefile` (`CC = clang`, `-std=c11`, `-fobjc-arc`), `nxnative/dm/gfx/metal/Makefile`.
- Android `aapt`/SDK tools are not used: `nxnative/dm/android/apk/mkapk.py` writes binary AXML, the APK, and signs it itself (standard library only, no JDK).
- .NET SDK 10 `dotnet build` for `nx_extract` and `dmsh_xlate`, run by `porter/pipeline.py` (`nsp.run([self.tools['dotnet'], 'build', src, '-c', 'Release', ...])`).
- Android platform-tools `adb` - only to install to a device.
- Git with Conventional Commits enforcement: `.githooks/commit-msg` and `.githooks/commit_msg.py` (no external commitlint install; commitlint's `config-conventional` rules are re-implemented).
- Git subtree for `nxnative/` (`git subtree pull --prefix nxnative ... --squash`, README.md).
- `.gitattributes`: `* text=auto eol=lf`.

## Key Dependencies

- `lz4` - LZ4 block decompression for NSO/NSP content: `porter/` via `upstream` (`import lz4.block` in the engine's tools).
- `capstone` - AArch64 disassembly for the rewriter (`patch_nso.py`), named in `porter/toolchain.py` `PY_MODULES`.
- `pillow` (PIL) - the app icon from the game's icon: checked in `porter/toolchain.py` (`_importable('PIL')`), used in `porter/pipeline.py`; also `devtools/burst.py`, `devtools/rec_flicker.py`. Bundled via `packaging/nx2android.spec`.
- `pyyaml` (`yaml`) - parses FPSLocker-Warehouse configs in `porter/fpslocker.py`; collected into the bundle by `packaging/nx2android.spec`.
- `backports.zstd` - zstd decoding on Python < 3.14 (`requirements.txt` marker `python_version < "3.14"`; `porter/toolchain.py`).
- `PySide6` - GUI (`gui/`).
- `pyinstaller` - not in `requirements.txt`; install manually (`python -m pip install -r requirements.txt pyinstaller`, README.md).
- Optional Python modules used by dev tools only: `numpy` and `av` (PyAV) in `devtools/burst.py`, `devtools/rec_flicker.py` and `.claude/skills/switch-android-port/scripts/*.py`; not listed in `requirements.txt`.
- `libvpx/` - libvpx v1.17.0 (VP9 decoder only, BSD-3-Clause), built file by file into `gen/vpx/libvpx.a` by `nxnative/dm/host/Makefile`; the Android build compiles the same sources in `nxnative/dm/android/build.py` (`VPX = srcs('third_party/libvpx/**/*.c')`). Used by `nxnative/dm/host/hle_movie.c`.
- `stb_vorbis/` - stb_vorbis 1.22 (single file, MIT / public domain), used by `nxnative/dm/host/hle_movie.c` (push-data API).
- `vulkan-headers/` - Vulkan-Headers 1.4.363 (Apache-2.0 or MIT), used by `nxnative/dm/gfx/vk/hle_vk.m` and `nxnative/dm/android/gfx_vk_*.c`.
- `ryujinx/` - Ryujinx 1.3.2 shader translation projects `Ryujinx.Graphics.Shader`, `Ryujinx.Common`, `Spv.Generator` (MIT), compiled by `dmsh_xlate` in `porter/pipeline.py`.
- `flip/` - NVIDIA FLIP image metric (BSD-3-Clause), for image-quality verification; `nxnative/dm/third_party/README.md` names `dm/verify/gfxq/` as its consumer, but that folder is not present in this checkout. Build: `make -C nxnative/dm/third_party/flip`.
- `macnativegames` / deko3d / `nvn.h` - code ported or adapted, listed in `nxnative/dm/third_party/README.md`.
- `LibHac` 0.19.0 - Switch NCA/NSP/XCI reader for `nx_extract` (`nxnative/dm/tools/nx_extract/nx_extract.csproj`).
- Ryujinx projects (project references, not NuGet) for `dmsh_xlate`.
- Ryujinx's package set in `Directory.Packages.props` (Avalonia, SkiaSharp, CommandLineParser, CommunityToolkit.Mvvm, etc.) is inherited but only the shader/common projects are compiled here.
- Android NDK r27c - `porter/toolchain.py` `NDK_RELEASE = 'r27c'`; fetched from `dl.google.com` (see INTEGRATIONS.md) or supplied by the player.
- Android platform-tools (adb) - device install (`porter/adb.py`, `porter/install.py`).
- .NET SDK 10 (`porter/toolchain.py` `DOTNET_MAJOR = 10`).
- Khronos validation layer (`VK_LAYER_KHRONOS_validation`) - optional, only when the APK is built with `mkapk.py --extra-so` and `DM_VK_VALIDATE=1` (`nxnative/dm/android/gfx_vk_core.c`).
- Android system libraries linked by the runtime (`nxnative/dm/android/build.py` `LIBS`): `-landroid -llog -lvulkan -laaudio -lnativewindow -lmediandk -lm -ldl`. Media decoding uses MediaCodec (`nxnative/dm/android/movie_avc.c`); audio uses AAudio (`nxnative/dm/android/compat/audiotoolbox_aaudio.c`).

## Configuration

- `<user dir>/config.json` written by `porter/config.py` (keys: `keys`, `ndk`, `dotnet`, `adb`, `out`, `device`, `language`). Managed by the GUI's Setup tab and `python -m porter config`.
- `<user dir>/signing-key.json` - the APK signing key, created on first use by `mkapk.py` (`porter/paths.py` `signing_key()`); gitignored (`*-signing-key.json`).
- `<user dir>/toolchains/` - downloaded NDK, .NET SDK and platform-tools (`porter/paths.py` `player_tools()`).
- `<user dir>/tools/dmsh_xlate/` - the translator built from source per player (`porter/pipeline.py`).
- `NX2A_HOME` - overrides the player's settings folder (`porter/paths.py`).
- `NX2A_GAME` (a title ID), `NX2A_DEVICE`, `NX2A_PACKAGE` - dev tools target (`devtools/device.py`).
- `DM_GAMES_DIR`, `DM_GAMES_FIRST` - an external game profile folder (`porter/pipeline.py`, `nxnative/dm/gfx/...` make rules).
- `ANDROID_NDK_HOME`, `ANDROID_NDK_ROOT`, `ANDROID_HOME`, `ANDROID_SDK_ROOT` - NDK and SDK discovery (`porter/toolchain.py` `find_ndk`, `_sdk_roots`).
- `DOTNET_ROOT` - `dotnet` discovery and runtime location (`porter/toolchain.py`, `porter/pipeline.py`).
- `LOCALAPPDATA`, `APPDATA`, `ProgramFiles`, `ProgramW6432` - Windows install locations.
- `XDG_CONFIG_HOME` - Linux settings folder.
- `DM_VK_VALIDATE`, `DM_CTL`, `DM_FPS_TARGET`, `DM_PRESENT_INTERVAL`, `DM_FPS_LOCKS`, `DM_PATCHES_EXTRA` - engine and runtime switches written to the data pack's `env.txt` or used by the build tools (`nxnative/dm/android/`, `porter/pipeline.py`).
- `XLATE`, `XLATE_DEBUG`, `XLATE_REDUCED`, `DM_ROOT`, `DM_GAME`, `DM_SPLIT_AOC` - engine shader-tool switches (`nxnative/dm/gfx/tools/dmsh_chain.py`, `dmsh_build.py`, `shader_vk.py`).
- `nxnative/dm/games/<title ID>/game.tsv` (upstream keys), `android.tsv` (Android keys: `status`, `tested`, `package`, `orientation`, `requires`, `setting`, `env`, `overlay`), shader tables, `patches.py`. Documented in `docs/ARCHITECTURE.md`.
- `nxnative/dm/android/overlay_default.tsv` - default on-screen gamepad layout compiled into `android_profile.h`.
- `nxnative/dm/host/Makefile` - `CFLAGS=-O1 -g -Wall -Wno-unused-function`; `GAME` required.
- `nxnative/dm/android/build.py` - `--api` (default 31), `--release`, `--debug`, `--ndk`, `--out`, `--jobs`. Links with `-fuse-ld=lld`, page size 16 KB (`-Wl,-z,max-page-size=16384`).
- `nxnative/dm/third_party/ryujinx/Directory.Build.props` and `Directory.Packages.props` - .NET central package management.
- `packaging/nx2android.spec` - PyInstaller spec, one-folder build, `upx=False`, `console=True`.
- `.gitattributes`, `.gitignore` - LF line endings; keys, game dumps, `tools/`, `work/`, `build/`, `dist/`, `.venv/`, `devtools/device.json` are excluded.
- `nx2android.code-workspace` - VS Code workspace (untracked, single folder).
- `dm/gfx/tools/dmsh_chain.lock` - tool fingerprints (Ryujinx shader DLL, SPIRV-Cross, Metal compiler) for the Apple shader chain.
- `dm/gfx/nvn/dmsh_chain.h` - chain version header generated by `nxnative/dm/gfx/tools/dmsh_chain.py --header`.

## Platform Requirements

- Python 3.11+ with `requirements.txt` installed.
- Android NDK r27c (only the NDK; no Android Studio, SDK or JDK required, per README.md).
- .NET SDK 10 (builds `nx_extract` and the translator).
- Android platform-tools (`adb`) to install onto a device.
- Optional: `pyinstaller` and, on Windows, the Microsoft C++ Build Tools (for `packaging/build_bootloader.py`).
- macOS with Xcode for the Apple host/Metal work (`nxnative/dm/host/Makefile`, `nxnative/dm/gfx/metal/Makefile`); not needed for the Android port.
- Roughly 20 GB free disk space recommended (`porter/toolchain.py` `DISK_GB`); a NEO-sized port takes about 7 GB of build folder.
- Windows x64 bundle from GitHub Releases (`nx2android-<version>-windows-x64.zip`, README.md) with no Python or toolchains to install; the Setup tab downloads the rest.
- Their own `prod.keys` and NSP/XCI files (never shipped).
- An Android device with a Vulkan 1.3 driver and BC texture support (Adreno or Xclipse GPU; Mali and PowerVR are not supported), Android 10+, USB debugging if installing from the tool.
- Per-game Android APK (`lib/arm64-v8a/libdmhost.so`, NativeActivity, `minSdk` 29, `targetSdk` 36), signed with the player's own key, plus a data pack (`<App>-data/`) pushed to `/sdcard/Android/data/<package>/files`.
- No server-side deployment; the project publishes no hosted service.

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

## Naming Patterns

- Python modules: short lowercase nouns, no underscores unless needed: `porter/adb.py`, `porter/fpslocker.py`, `porter/pipeline.py`. Compound names use underscores: `porter/push_chunked.py` (devtools), `gui/runner.py`.
- Tests: `tests/test_<area>.py` (`tests/test_porter.py`, `tests/test_commit_msg.py`). Test modules that exercise C code are named after the C file: `tests/test_vk_present_timing.py` drives `nxnative/dm/android/gfx_vk_present.c`.
- Android C sources use a subsystem prefix: `nxnative/dm/android/gfx_vk_present.c`, `gfx_vk_shader.c`, `perf_android.c`, `front_android.c`. Headers sit beside them (`gfx_vk.h`).
- Shell scripts: lowercase with underscores or none: `devtools/soak.sh`, `devtools/trace_pass.sh`.
- Python: `snake_case`, verbs for actions: `inspect(folder)`, `entry(g, p)`, `all_entries(android_only=True)`, `set_value(key, value)` (`porter/config.py`). Private helpers get a leading underscore only where needed: `_parser()` in `porter/cli.py`, `_env()` in `gui/runner.py`.
- C: `snake_case` with a module prefix. Public Vulkan-backend entry points use `vk_`: `vk_shaders_open(const char *path)` in `nxnative/dm/android/gfx_vk_shader.c`, `vk_dsl_register`. File-local helpers are `static` with short names: `bundle_open_once`, `present_time_get`, `adapt_frame`, `work_pct`.
- Test methods: `test_<behaviour>` in `unittest` classes (`test_refused`, `test_accepted`, `test_bad_keys_are_refused`, `test_ticket_history`).
- Python: `snake_case`. Short names are normal for local tuples and comprehension values (`g`, `p`, `k`, `v`, `ln`, `rx`).
- Module-level constants: `UPPER_CASE` (`TYPES`, `MAX_LINE`, `HEADER_RX`, `KEYS`, `STATUS` in `.githooks/commit_msg.py`, `porter/config.py`, `porter/adb.py` `LONG_PATH`).
- C globals: a `g_` prefix, and file-scope state often gathered in one anonymous struct: `static struct { ... } V;`, `static const uint8_t *g_bundle; static uint32_t g_nent;` (`gfx_vk_shader.c`).
- Environment switches are `DM_*` (`DM_VK_SHADERS`, `DM_ROOT`, `DM_FPS_PIN`, `DM_ADAPT_UP_PCT`); Vulkan-related log helper is `VKLOG`.
- Python classes: `PascalCase`, dataclasses for records and options: `Options` (`porter/pipeline.py`), `Entry` (`porter/profiles.py`), `Item` (`porter/fetch.py`), `Adb` (`porter/adb.py`).
- Exceptions: `<Thing>Error` deriving from `Exception`: `AdbError` (`porter/adb.py`), `ToolError` (`porter/toolchain.py`), `ProfileError` (`nxnative/dm/android/tools/android_profile.py`), `BuildError` (upstream, used in `porter/pipeline.py`). A single-purpose refusal can be a bare subclass: `class Refused(Exception): pass` in `porter/fpslocker.py`.
- C types: `typedef struct __attribute__((packed)) { ... } bent;` (short lowercase typedef names for on-disk records). Opaque `VkXxx` Vulkan handles are used as declared.

## Code Style

- No formatter config is committed (no `pyproject.toml`, `.prettierrc`, `.clang-format`, `setup.cfg`). Match the surrounding file.
- Python: 4-space indent. Line length is loose; long lines of 150+ characters appear in `porter/cli.py` and `porter/pipeline.py`. Prefer wrapping only when a line becomes hard to scan.
- Python is written in a dense one-line style: short bodies are placed on the same line as the `if`, `for` or `def` (`if not errs: return 0`, `def tearDown(self): os.environ.pop('DM_GAMES_DIR', None)`, `try: c = json.loads(...)`, `except (OSError, ValueError): c = {}`). Use this for guard clauses and one-statement bodies; use full blocks for multi-step logic.
- Several statements share a line separated by `;` (`p = paths; out = []`, `c = load(); c[key] = value; save(c)`). Acceptable where the lines are a related pair.
- C: 4-space indent, braces on the same line, `if (...) { ...; }` one-liners common in hot-path code. Lines wrap at roughly 150 to 180 characters. Comments are `//` (both in the Android/Vulkan code and the upstream Ryujinx-derived tree); block comments `/* */` appear only in headers.
- Line endings are LF everywhere (`.gitattributes`: `* text=auto eol=lf`). Shell scripts and assembly run on device and in the NDK build; do not introduce CRLF.
- Not configured. No flake8, ruff, pylint, mypy, clang-tidy or clang-format configs are committed.
- `tests/arch_rules.py` is the only enforced static check. It parses the committed tree and fails on: game IDs, game names or packages in core code (`nxnative/dm/android/`); title-ID branches in Android-guarded shared code; non-data files inside `nxnative/dm/games/<id>/` (only `patches.py` may hold code); `android.tsv` keys and status values outside the documented set; GUI imports (PySide6) inside `porter/`; toolchains committed to the repo.
- Python compatibility: 3.11 or later per `requirements.txt`. `backports.zstd` is pinned only for Python below 3.14.
- Shell: scripts should be safe under `set -e`-style use; existing scripts (`devtools/soak.sh`) are plain POSIX-ish bash.

## Import Organization

## Error Handling

- Errors that the user should see are raised as a named exception with a message that says what to do: `raise BuildError('this folder has only NSZ / XCZ files: decompress them to NSP / XCI first (nsz -D with your prod.keys), ...')` (`porter/pipeline.py` / `porter/upstream.py`). Messages name the file and the fix.
- Wrap a lower-level error into the layer's own error with chaining: `except toolchain.ToolError as e: raise BuildError(str(e)) from e` (`porter/pipeline.py`).
- Ignore a failure only where absence is expected, and say so with the narrowest exception: `except (OSError, ValueError): c = {}` (`porter/config.py`) and `except OSError: shutil.copy2(p, q)` (`porter/adb.py`).
- Retries are explicit and logged, not silent: `Adb.run(..., retries=3)` logs `adb {cmd} failed (...), retry N` before retrying, and does not retry an `install` failure because it is an answer, not a dropped link (`porter/adb.py`).
- Input validation at the boundary raises the module's error type with the offending line: `raise ProfileError(f'{self.path}:{n}: unknown key {k!r} (keys: ...)')` (`nxnative/dm/android/tools/android_profile.py`).
- Errors are logged and the code degrades; it does not abort the process: `VKLOG("[RED] no shader bundle at %s: nothing will be drawn", path); ... return;` (`nxnative/dm/android/gfx_vk_shader.c`).
- Vulkan calls are wrapped in a checking macro: `VKCHK(call)` (used in the layout-cache harness in `tests/test_vk_layout_cache.py` and the `gfx_vk` sources).
- Resources are closed on every failure path before returning: `if (fd >= 0) close(fd);`.

## Logging

- Prefix a problem line with `[RED] ` so the GUI can colour it and users can grep for it: `PROG.say(f'[RED] {e}')` (`porter/cli.py`), `say(f'[RED] {self.derived}: ...')` (`porter/pipeline.py`), and in C `VKLOG("[RED] ...")`. The project rule is that logs for something unimplemented or wrong start with `[RED] ` (`.claude/skills/nx2android-dev/SKILL.md`).
- Machine output: `--json` prints one JSON document; `--progress json` prints one JSON event per line with `ev` keys (`stage`, `step`, `progress`, `stage_end`, `say`, `result`). Do not mix human text into a JSON stream; the GUI (`gui/runner.py`) parses stdout line by line and treats non-JSON lines as `say` events.
- Log in English only.
- Port logs for a run go to `<game folder>/port_check.jsonl` (`devtools/port_check.py`).

## Comments

- Comments state the *why* and cite the evidence: a log line, a crash address, a census, or a game and build that exposed the problem. Example from `porter/adb.py`: the comment on `LONG_PATH` explains the Windows 260-character limit and the Viractal bundle that hit it. Keep this habit; the project's rule is "measure, then change" and the evidence goes in the comment beside the fix.
- File headers: Python modules open with a `#` comment block of one to five lines describing the module's job and the contract (`porter/config.py`, `porter/pipeline.py`, `gui/runner.py`). C files open with `//` lines in the same role (`gfx_vk_shader.c`).
- Comments may name a game a rule was found with (allowed by the SKILL rules); code branches may not depend on a game (enforced by `tests/arch_rules.py`).

## Function Design

## Module Design

## Commit Messages

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

<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

## System Overview

```text

```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| GUI window and tabs | Port (pick folder, options, run, progress), Setup (tool check, downloads, settings), Games (profile list) | `gui/app.py` |
| Process bridge | Starts `porter` as a `QProcess`, parses JSON events into Qt signals, cancels the process tree | `gui/runner.py` |
| GUI entry | `python -m gui` runs `gui.app.main` | `gui/__main__.py` |
| CLI | argparse subcommands: `doctor`, `profiles`, `inspect`, `port`, `install`, `devices`, `tools`, `config` | `porter/cli.py` |
| Port pipeline | `Options` dataclass and `Port` class; one method per stage | `porter/pipeline.py` |
| Game inspection | Finds base game, updates, DLC in a folder and matches a profile | `porter/pipeline.py` (`inspect`) |
| Paths | Repo root (`REPO`, the bundle folder when frozen), per-player folder, signing key | `porter/paths.py` |
| Settings | Saved player settings (prod.keys, NDK, dotnet, adb, output, device) | `porter/config.py` |
| Toolchains | Locates NDK, .NET SDK, platform-tools per OS | `porter/toolchain.py` |
| Downloads | Fetches NDK, .NET, platform-tools from vendor URLs | `porter/fetch.py` |
| Upstream helpers | Engine-source helpers; APFS clone check (macOS only) | `porter/upstream.py` |
| Profiles | Reads game profiles, `android.tsv` keys | `porter/profiles.py` |
| Device I/O | adb wrapper, long-path handling on Windows | `porter/adb.py` |
| Data pack | Assembles the files the app reads at runtime | `porter/datapack.py` |
| FPS locker | Converts the build's FPSLocker config for `--fps60` | `porter/fpslocker.py` |
| Engine host | Horizon OS service stand-ins, NVN graphics layer | `nxnative/dm/host/`, `nxnative/dm/gfx/` |
| Android runtime | Vulkan backend, NativeActivity front end, NDK build, APK writer | `nxnative/dm/android/` |
| Rewriter and shader tools | Patch NSO code, split shaders, translate to SPIR-V | `nxnative/dm/tools/patch_nso.py`, `nxnative/dm/tools/shader_split.py`, `nxnative/dm/android/tools/shader_vk.py` |
| Game profiles | Data per title: `game.tsv`, shader tables, `patches.py`, `android.tsv` | `nxnative/dm/games/<title ID>/` |
| Bundle | PyInstaller spec and builder for the Windows zip | `packaging/nx2android.spec`, `packaging/build_bundle.py` |
| Bundle entry | Dispatches `-m module`, `script.py`, or the GUI | `packaging/nx2android.py` |
| Dev tools | Device bring-up, pushing, screen recording, soak, traces | `devtools/*.py`, `devtools/*.sh` |

## Pattern Overview

- The GUI holds no pipeline logic. A rule in `gui/` must not duplicate what `porter/` does (documented in `docs/ARCHITECTURE.md`).
- Process boundary as the API. Long commands print one JSON object per line (`--progress json`, events `stage`, `step`, `progress`, `stage_end`, `say`, `result`). Short commands print one JSON document (`--json`). `gui/runner.py` is the only consumer of this protocol.
- The engine (`nxnative/`) is a vendored, git-subtree copy of an upstream project and is built per port with the player's NDK. Shared core code must stay small because it is merged with `git subtree pull`.
- Data-only game profiles. A profile is compiled into the host at build time (`game_profile.h`, `android_profile.h`, generated by `nxnative/dm/android/build.py`).
- Cached stages. Slow stages (extract, rewrite, shader split, translator build, Vulkan shaders) store output keyed by their inputs and are skipped when unchanged.

## Layers

- Purpose: Screens for the player: setup check, game folder, options, progress, install.
- Location: `gui/`
- Contains: `Window`, `PortTab`, `SetupTab`, `GamesTab` in `gui/app.py`; `Porter` (long process) and `call_json` (one-shot) in `gui/runner.py`.
- Depends on: PySide6; `porter.config` and `porter.paths` (imported directly for settings and `REPO`); `porter` via subprocess.
- Used by: The player, through `python -m gui` or the frozen `nx2android.exe`.
- Purpose: Everything the port does, runnable without a UI.
- Location: `porter/`
- Contains: `cli.py` (command dispatch in `main`), `pipeline.py` (`Port` class with stage methods `inputs`, `extract`, `fps_unlock`, `rewrite`, `shaders`, `pull_captures`, `translator`, `host`, `apk`, `icon`, `data`, `install`), support modules.
- Depends on: Standard library, `porter/paths.py`, `porter/config.py`; reuses steps of `nxnative/scripts/build_ipa_from_nsp.py` by import.
- Used by: `gui/runner.py`, and users at the command line (`python -m porter`).
- Purpose: Run Switch code natively: a host that stands in for Horizon OS services, and a graphics layer that replays NVN calls.
- Location: `nxnative/dm/host/`, `nxnative/dm/gfx/`, `nxnative/dm/tools/`
- Contains: `hle_*.c` service stand-ins (`hle_fs.c`, `hle_hid.c`, `hle_audren.c`, ...), NVN implementations for `gl`, `metal`, `vk`, and `nvn`, the rewriter and shader tools.
- Depends on: `nxnative/dm/third_party/` (for example `flip`, `libvpx`, `stb_vorbis`, `vulkan-headers`, and `ryujinx` for the shader translator).
- Used by: Both platforms. Platform differences are guarded by `DM_ANDROID`, `__APPLE__`, or `DM_TARGET`.
- Purpose: The Android side of the engine.
- Location: `nxnative/dm/android/`
- Contains: `front_android.c` (NativeActivity front end: gamepad, pause menu, text entry, haptics, audio), `gfx_vk_*.c` (Vulkan backend), `build.py` (NDK build), `apk/mkapk.py` (APK writer), `tools/shader_vk.py`, `tools/android_profile.py`, `overlay_default.tsv`.
- Depends on: NDK (player's own), shared core in `dm/host` and `dm/gfx`.
- Used by: The port's `host` and `apk` stages.
- Purpose: Everything specific to one title.
- Location: `nxnative/dm/games/<title ID>/`
- Contains: `game.tsv`, shader tables, `patches.py` (the only code allowed here), `android.tsv`.
- Depends on: Nothing; read by the pipeline and by `nxnative/dm/android/tools/android_profile.py`.
- Used by: `porter/pipeline.py` (`inputs`, `use_profile_dir`, `experimental_profile`).
- Purpose: Build the player's Windows zip.
- Location: `packaging/`
- Contains: PyInstaller spec, `build_bundle.py` (copies the git-tracked `nxnative/` next to the executable), `build_bootloader.py`, `nx2android.py` (dispatcher), `INSTALL.md`.
- Depends on: PyInstaller, PySide6, committed sources only.
- Used by: Release process.

## Data Flow

### Primary Request Path: Port a game

### Runtime path on the device

### Setup path

- Player settings and signing key: a per-player folder from `porter/paths.py` `user_dir()` (`%APPDATA%\nx2android` on Windows, `~/Library/Application Support/nx2android` on macOS, `~/.config/nx2android` elsewhere; overridable by `NX2A_HOME`).
- GUI state lives in widget attributes (`PortTab.info`, `PortTab.result`) and is not persisted; the Port tab's last game folder is not saved.
- Pipeline state lives in the game folder's build directory and in stage caches keyed by input hashes.

## Key Abstractions

- Purpose: Runs the port's stages in order and reports each as a JSON event.
- Examples: `porter/pipeline.py` (`class Port`, `def run`)
- Pattern: One method per stage; each stage is skipped when its cache key is unchanged.
- Purpose: Typed options for one port run.
- Examples: `porter/pipeline.py` (`class Options`)
- Pattern: Dataclass built from CLI args in `cmd_port`.
- Purpose: Runs one long porter command and turns its stdout into Qt signals.
- Examples: `gui/runner.py` (`class Porter`)
- Pattern: `QProcess` plus `Signal(dict)` per JSON event. The GUI never parses pipeline internals beyond the event fields.
- Purpose: Per-title data (name, IDs, shader tables, Android status and settings).
- Examples: `nxnative/dm/games/010015100B514000/` (Super Mario Bros. Wonder), `porter/profiles.py`
- Pattern: Directory keyed by title ID, data files only, `patches.py` for per-build rewriter cuts.
- Purpose: Run upstream Python tools unchanged.
- Examples: `packaging/nx2android.py` (dispatch), `nxnative/dm/tools/patch_nso.py`
- Pattern: Subprocess `python <script>`; under the bundle the same executable is the interpreter.

## Entry Points

- Location: `gui/__main__.py` (`python -m gui`), and `main` in `gui/app.py`
- Triggers: Player opens the app or `python -m gui`.
- Responsibilities: Creates `QApplication` (Fusion style), `Window` with three tabs.
- Location: `porter/__main__.py` (`python -m porter`), `main` in `porter/cli.py`
- Triggers: Command line, or the GUI's `QProcess`.
- Responsibilities: Subcommands `doctor`, `profiles`, `inspect`, `port`, `install`, `devices`, `tools`, `config`.
- Location: `packaging/nx2android.py`
- Triggers: The frozen `nx2android.exe`.
- Responsibilities: `-m module` runs a module; `*.py` runs a script with its folder on `sys.path`; no arguments opens the GUI and hides the Windows console when double-clicked.
- Location: `nxnative/dm/host/entry.S`, `nxnative/dm/host/crash.c`
- Triggers: Loaded by the Android APK.
- Responsibilities: Assembly entry point and crash handler; the service stand-ins are in `nxnative/dm/host/hle_*.c`.
- Location: `devtools/` (for example `devtools/device.py`, `devtools/soak.sh`), `probes/` (C probes and `probes/app/mkapk.py`)
- Triggers: Run by hand against a connected device.

## Architectural Constraints

- **Threading:** The GUI runs on the Qt event loop in one thread. Long work runs in child processes (`QProcess`). The shader splitter (`nxnative/dm/tools/shader_split.py`) runs a multiprocessing pool; the bundle calls `multiprocessing.freeze_support()` in `packaging/nx2android.py`.
- **Global state:** Module-level settings in `porter/paths.py` (`REPO`, `NXNATIVE`, `DM`) computed at import time. `REPO` changes meaning when frozen (`sys.executable`'s folder).
- **Circular imports:** None observed in the sampled modules. `gui` imports `porter`; `porter` does not import `gui`.
- **Shared core must stay upstream-compatible:** Changes to `nxnative/dm/{host,gfx,tools,third_party}` are merged with `git subtree pull`. Keep diffs small and platform-guarded.
- **No game-specific code in Android runtime:** Enforced by `tests/arch_rules.py` (run by `tests/test_architecture.py`): no title IDs, game names, or per-game branches in `nxnative/dm/android/`.
- **Profiles are data:** Enforced by `tests/arch_rules.py`: only `patches.py` may hold code in a profile folder; `android.tsv` keys and status values are checked.
- **Platform:** Shipping target is Windows x64 (`packaging/build_bundle.py`, `packaging/INSTALL.md`). Code paths exist for macOS (`porter/paths.py`, `porter/toolchain.py`, `porter/fetch.py`, `porter/upstream.py` APFS clone) and Linux (XDG paths). Not verified from code whether macOS or Linux GUI runs are tested.
- **Toolchains are not bundled:** The bundle carries no NDK, .NET or adb; `porter/fetch.py` downloads them, or the player installs them.

## Anti-Patterns

### Pipeline logic in the GUI

### Game-specific branches in shared code

### Implicit contract between GUI and CLI output

## Error Handling

- `gui/runner.py` `Porter._done` shows the last line of stderr (a traceback's last line) in red when the exit code is non-zero.
- `gui/app.py` `on_inspect` shows `error` from the inspect JSON in red on the card.
- Pipeline stages raise and the stage reports a failure event; the GUI shows it on the stage row.

## Cross-Cutting Concerns

<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

| Skill | Description | Path |
|-------|-------------|------|
| nx2android-dev | How to add a new game profile to nx2android (port another Switch game to Android) or improve the shared core (the Android runtime, the Vulkan backend, the Horizon host, the rewriter, the shader tools, the porter or the GUI). Use whenever the task is to port or bring up a game on Android, add or edit a profile under nxnative/dm/games/ or an android.tsv, decide whether a fix belongs in a profile or the core, make a core change (missing SDK/NVN functions, shader readers or the translator, input, the overlay, the pause menu), install a build on the device, or change porter/, gui/, packaging/ or nxnative/dm/android/ — even if the user only says "make <game> work" or "port <game>". Chasing a symptom on the device (flicker, crashes in the app, refused submissions, stutter) or measuring speed and stability is the switch-android-port skill's; it sends the fix back here. | `.claude/skills/nx2android-dev/SKILL.md` |
| switch-android-port | Track down and fix problems in a Switch game running on an Android device under nx2android - crashes in the app, rendering bugs (flicker, vanishing blocks, upside-down pictures, refused Vulkan submissions, wrong colours), stutter and frame rate, soak tests and play-session checks - with the methods that found NEO - The World Ends with You's bugs (screen recordings, frame shots, pass dumps, live A/B switches, the validation layer). Use when chasing a symptom on the tablet or measuring speed or stability there. For where a change belongs (profile or core), adding a game profile, the port pipeline and the repository's rules, use nx2android-dev; the two are meant to be used together. | `.claude/skills/switch-android-port/SKILL.md` |
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-fast` for a trivial task inline, with no subagents and no PLAN.md
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
