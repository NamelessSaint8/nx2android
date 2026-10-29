---
last_mapped_commit: 9d67edec2175ae5f4beadbd65f37eaa88105d132
last_mapped_at: 2026-10-29
---
# Technology Stack

**Analysis Date:** 2026-10-29

## Languages

**Primary:**
- Python 3.11+ - the port pipeline and CLI (`porter/`), the desktop GUI (`gui/`), the packaging scripts (`packaging/`), the dev tools (`devtools/`), and the engine's build and shader tools under `nxnative/dm/android/` and `nxnative/dm/gfx/tools/`. The `porter/` code uses `importlib.util`, `dataclasses` and `tarfile` filters with fallbacks for 3.11.
- C (C11 for the host, the Android runtime, and probes) - the game host and Android runtime: `nxnative/dm/host/*.c`, `nxnative/dm/android/*.c`, `nxnative/dm/gfx/**/*.c`, `nxnative/dm/third_party/libvpx/`, `nxnative/dm/third_party/stb_vorbis/stb_vorbis.c`, `probes/*.c`.
- AArch64 assembly - the guest entry and thunks: `nxnative/dm/host/entry.S`, `nxnative/dm/gfx/nvn/nvn_entry.S`, and the generated `nvn_thunks.S`. Mach-O assembly is converted to ELF for Android by `nxnative/dm/android/tools/darwin2elf.py`.

**Secondary:**
- Objective-C (ARC) - the Apple host and Metal backend: `nxnative/dm/host/front_mac.m`, `nxnative/dm/host/haptics_apple.m`, `nxnative/dm/gfx/vk/hle_vk.m` (Vulkan layer on Metal), `nxnative/dm/gfx/metal/`, `nxnative/dm/gfx/nvn/nvn_mtl.m`. Compiled only on macOS (`nxnative/dm/host/Makefile` links `-framework Metal -framework Foundation`).
- C# (.NET 10, `net10.0`) - the NSP/XCI extractor and the shader translator: `nxnative/dm/tools/nx_extract/nx_extract.csproj` (LibHac 0.19.0), `nxnative/dm/gfx/tools/dmsh_xlate/dmsh_xlate.csproj` (references Ryujinx projects under `nxnative/dm/third_party/ryujinx/src/`).
- GLSL - the Android backend's own small shaders, compiled by the NDK's `glslc` with `--target-env=vulkan1.1` (`nxnative/dm/android/shaders/`, invoked from `nxnative/dm/android/build.py`).
- Swift and YAML (XcodeGen) - the iOS app only: `nxnative/dm/ios/Sources/Launcher.swift`, `nxnative/dm/ios/project.yml`. No iOS build is part of the Android port.
- Shell (POSIX `sh`) - `.githooks/commit-msg`, `devtools/soak.sh`, `devtools/trace_pass.sh`.
- Python packaging via PyInstaller's waf build: `packaging/build_bootloader.py` compiles the launcher (needs Microsoft C++ Build Tools on Windows).

## Runtime

**Player / developer host:**
- Python 3.11 or later (README.md, `porter/toolchain.py` `checks()` requires `>= (3, 11)`). `porter/config.py`-level code and `porter/toolchain.py` use `compression.zstd` on Python 3.14+ and fall back to `backports.zstd` before that.
- Windows, macOS or Linux. Paths and the settings folder branch by OS in `porter/paths.py` (`%APPDATA%\nx2android` on Windows, `~/Library/Application Support/nx2android` on macOS, `$XDG_CONFIG_HOME`/`~/.config/nx2android` elsewhere; `NX2A_HOME` overrides).
- Bundled player runtime: a PyInstaller build of the same Python (`packaging/nx2android.spec`, `packaging/nx2android.py`) so the player does not install Python.

**Target device (Android):**
- Android 10 minimum (`MIN_SDK = 29`), target SDK 36 (`TARGET_SDK = 36`) in `nxnative/dm/android/apk/mkapk.py`.
- ABI: `arm64-v8a` only (`lib/arm64-v8a/lib<name>.so` in `mkapk.py`; `--target=aarch64-linux-android<api>` in `nxnative/dm/android/build.py`).
- Native activity: `android.app.NativeActivity`, no Java or Kotlin code (`hasCode=false`). Only `android.permission.VIBRATE` is requested.
- Vulkan 1.3 instance (`VK_API_VERSION_1_3` in `nxnative/dm/android/gfx_vk_core.c`) with a Vulkan 1.2/1.3 feature/extension set; the device must read BC-compressed textures (per `docs/PORT_STATUS.md` and `porter/install.py` `bc_textures()`).

**Package managers:**
- pip - Python dependencies, `requirements.txt` (no lockfile; versions are not pinned).
- .NET SDK 10 - restores NuGet packages for `nx_extract` and `dmsh_xlate` (`nxnative/dm/third_party/ryujinx/Directory.Packages.props` centrally pins the Ryujinx dependency versions, e.g. Avalonia 12.1.1, SkiaSharp 3.119.4; only the Shader/Common projects are built).
- Lockfile: missing. `requirements.txt` has no pins; no `packages.lock.json` or `poetry.lock` is present.

## Frameworks

**Core:**
- PySide6 (Qt for Python) - desktop GUI, `gui/app.py`, `gui/runner.py`. Imported from `PySide6.QtWidgets`, `PySide6.QtCore`, `PySide6.QtGui`. Optional at run time: the CLI (`python -m porter`) runs without it (see the comment in `requirements.txt`).
- NDK native frontend - `ANativeActivity_onCreate` in `nxnative/dm/android/front_android.c` (NativeActivity, no framework).
- Vulkan (system `libvulkan.so`, headers vendored in `nxnative/dm/third_party/vulkan-headers/`) - Android graphics backend `nxnative/dm/android/gfx_vk_*.c`.
- Metal (Apple) - Mac/iOS backend `nxnative/dm/gfx/metal/`, `nxnative/dm/gfx/nvn/nvn_mtl.m`.
- Upstream nxnative engine (git subtree at `nxnative/`) - the Horizon OS host, NVN graphics layer and rewriter. Not a framework dependency; vendored source.

**Testing:**
- Python `unittest` - the test suite under `tests/` (`python -m unittest discover tests`). Files: `tests/test_porter.py`, `tests/test_architecture.py`, `tests/test_commit_msg.py`, `tests/test_perf_adaptive.py`, `tests/test_vk_layout_cache.py`, `tests/test_vk_present_timing.py`. Layer rules are checked by `tests/arch_rules.py`.
- Test helpers in the engine: `nxnative/dm/gfx/tests/Makefile`, `nxnative/dm/gfx/tex/tests/Makefile`, `nxnative/dm/host/tests/Makefile`.
- On-device probes (not unit tests): `probes/app/probeapp.c`, `probes/vkprobe.c`, `probes/cpuprobe.c`, `probes/vkzc.c`.

**Build/Dev:**
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

**Python (`requirements.txt`, unpinned):**
- `lz4` - LZ4 block decompression for NSO/NSP content: `porter/` via `upstream` (`import lz4.block` in the engine's tools).
- `capstone` - AArch64 disassembly for the rewriter (`patch_nso.py`), named in `porter/toolchain.py` `PY_MODULES`.
- `pillow` (PIL) - the app icon from the game's icon: checked in `porter/toolchain.py` (`_importable('PIL')`), used in `porter/pipeline.py`; also `devtools/burst.py`, `devtools/rec_flicker.py`. Bundled via `packaging/nx2android.spec`.
- `pyyaml` (`yaml`) - parses FPSLocker-Warehouse configs in `porter/fpslocker.py`; collected into the bundle by `packaging/nx2android.spec`.
- `backports.zstd` - zstd decoding on Python < 3.14 (`requirements.txt` marker `python_version < "3.14"`; `porter/toolchain.py`).
- `PySide6` - GUI (`gui/`).
- `pyinstaller` - not in `requirements.txt`; install manually (`python -m pip install -r requirements.txt pyinstaller`, README.md).
- Optional Python modules used by dev tools only: `numpy` and `av` (PyAV) in `devtools/burst.py`, `devtools/rec_flicker.py` and `.claude/skills/switch-android-port/scripts/*.py`; not listed in `requirements.txt`.

**Python standard library in use:** `urllib.request` (HTTP downloads, see `porter/fetch.py`, `porter/fpslocker.py`), `hashlib` (checksum verification), `xml.etree.ElementTree` (Google SDK index), `tarfile`/`zipfile`, `subprocess` (adb, dotnet, NDK tools), `multiprocessing` (shader workers in the bundle), `runpy`, `json`, `struct`.

**Engine / vendored (`nxnative/dm/third_party/`, see README in that folder):**
- `libvpx/` - libvpx v1.17.0 (VP9 decoder only, BSD-3-Clause), built file by file into `gen/vpx/libvpx.a` by `nxnative/dm/host/Makefile`; the Android build compiles the same sources in `nxnative/dm/android/build.py` (`VPX = srcs('third_party/libvpx/**/*.c')`). Used by `nxnative/dm/host/hle_movie.c`.
- `stb_vorbis/` - stb_vorbis 1.22 (single file, MIT / public domain), used by `nxnative/dm/host/hle_movie.c` (push-data API).
- `vulkan-headers/` - Vulkan-Headers 1.4.363 (Apache-2.0 or MIT), used by `nxnative/dm/gfx/vk/hle_vk.m` and `nxnative/dm/android/gfx_vk_*.c`.
- `ryujinx/` - Ryujinx 1.3.2 shader translation projects `Ryujinx.Graphics.Shader`, `Ryujinx.Common`, `Spv.Generator` (MIT), compiled by `dmsh_xlate` in `porter/pipeline.py`.
- `flip/` - NVIDIA FLIP image metric (BSD-3-Clause), for image-quality verification; `nxnative/dm/third_party/README.md` names `dm/verify/gfxq/` as its consumer, but that folder is not present in this checkout. Build: `make -C nxnative/dm/third_party/flip`.
- `macnativegames` / deko3d / `nvn.h` - code ported or adapted, listed in `nxnative/dm/third_party/README.md`.

**.NET (NuGet, via `Directory.Packages.props` and `*.csproj`):**
- `LibHac` 0.19.0 - Switch NCA/NSP/XCI reader for `nx_extract` (`nxnative/dm/tools/nx_extract/nx_extract.csproj`).
- Ryujinx projects (project references, not NuGet) for `dmsh_xlate`.
- Ryujinx's package set in `Directory.Packages.props` (Avalonia, SkiaSharp, CommandLineParser, CommunityToolkit.Mvvm, etc.) is inherited but only the shader/common projects are compiled here.

**Infrastructure / platform:**
- Android NDK r27c - `porter/toolchain.py` `NDK_RELEASE = 'r27c'`; fetched from `dl.google.com` (see INTEGRATIONS.md) or supplied by the player.
- Android platform-tools (adb) - device install (`porter/adb.py`, `porter/install.py`).
- .NET SDK 10 (`porter/toolchain.py` `DOTNET_MAJOR = 10`).
- Khronos validation layer (`VK_LAYER_KHRONOS_validation`) - optional, only when the APK is built with `mkapk.py --extra-so` and `DM_VK_VALIDATE=1` (`nxnative/dm/android/gfx_vk_core.c`).
- Android system libraries linked by the runtime (`nxnative/dm/android/build.py` `LIBS`): `-landroid -llog -lvulkan -laaudio -lnativewindow -lmediandk -lm -ldl`. Media decoding uses MediaCodec (`nxnative/dm/android/movie_avc.c`); audio uses AAudio (`nxnative/dm/android/compat/audiotoolbox_aaudio.c`).

## Configuration

**Player settings file:**
- `<user dir>/config.json` written by `porter/config.py` (keys: `keys`, `ndk`, `dotnet`, `adb`, `out`, `device`, `language`). Managed by the GUI's Setup tab and `python -m porter config`.
- `<user dir>/signing-key.json` - the APK signing key, created on first use by `mkapk.py` (`porter/paths.py` `signing_key()`); gitignored (`*-signing-key.json`).
- `<user dir>/toolchains/` - downloaded NDK, .NET SDK and platform-tools (`porter/paths.py` `player_tools()`).
- `<user dir>/tools/dmsh_xlate/` - the translator built from source per player (`porter/pipeline.py`).

**Environment variables read by the code:**
- `NX2A_HOME` - overrides the player's settings folder (`porter/paths.py`).
- `NX2A_GAME` (a title ID), `NX2A_DEVICE`, `NX2A_PACKAGE` - dev tools target (`devtools/device.py`).
- `DM_GAMES_DIR`, `DM_GAMES_FIRST` - an external game profile folder (`porter/pipeline.py`, `nxnative/dm/gfx/...` make rules).
- `ANDROID_NDK_HOME`, `ANDROID_NDK_ROOT`, `ANDROID_HOME`, `ANDROID_SDK_ROOT` - NDK and SDK discovery (`porter/toolchain.py` `find_ndk`, `_sdk_roots`).
- `DOTNET_ROOT` - `dotnet` discovery and runtime location (`porter/toolchain.py`, `porter/pipeline.py`).
- `LOCALAPPDATA`, `APPDATA`, `ProgramFiles`, `ProgramW6432` - Windows install locations.
- `XDG_CONFIG_HOME` - Linux settings folder.
- `DM_VK_VALIDATE`, `DM_CTL`, `DM_FPS_TARGET`, `DM_PRESENT_INTERVAL`, `DM_FPS_LOCKS`, `DM_PATCHES_EXTRA` - engine and runtime switches written to the data pack's `env.txt` or used by the build tools (`nxnative/dm/android/`, `porter/pipeline.py`).
- `XLATE`, `XLATE_DEBUG`, `XLATE_REDUCED`, `DM_ROOT`, `DM_GAME`, `DM_SPLIT_AOC` - engine shader-tool switches (`nxnative/dm/gfx/tools/dmsh_chain.py`, `dmsh_build.py`, `shader_vk.py`).

**Per-game configuration (data, not code):**
- `nxnative/dm/games/<title ID>/game.tsv` (upstream keys), `android.tsv` (Android keys: `status`, `tested`, `package`, `orientation`, `requires`, `setting`, `env`, `overlay`), shader tables, `patches.py`. Documented in `docs/ARCHITECTURE.md`.
- `nxnative/dm/android/overlay_default.tsv` - default on-screen gamepad layout compiled into `android_profile.h`.

**Build configuration:**
- `nxnative/dm/host/Makefile` - `CFLAGS=-O1 -g -Wall -Wno-unused-function`; `GAME` required.
- `nxnative/dm/android/build.py` - `--api` (default 31), `--release`, `--debug`, `--ndk`, `--out`, `--jobs`. Links with `-fuse-ld=lld`, page size 16 KB (`-Wl,-z,max-page-size=16384`).
- `nxnative/dm/third_party/ryujinx/Directory.Build.props` and `Directory.Packages.props` - .NET central package management.
- `packaging/nx2android.spec` - PyInstaller spec, one-folder build, `upx=False`, `console=True`.
- `.gitattributes`, `.gitignore` - LF line endings; keys, game dumps, `tools/`, `work/`, `build/`, `dist/`, `.venv/`, `devtools/device.json` are excluded.
- `nx2android.code-workspace` - VS Code workspace (untracked, single folder).

**Engine versions pinned in-repo:**
- `dm/gfx/tools/dmsh_chain.lock` - tool fingerprints (Ryujinx shader DLL, SPIRV-Cross, Metal compiler) for the Apple shader chain.
- `dm/gfx/nvn/dmsh_chain.h` - chain version header generated by `nxnative/dm/gfx/tools/dmsh_chain.py --header`.

## Platform Requirements

**Development (building the port from this repository):**
- Python 3.11+ with `requirements.txt` installed.
- Android NDK r27c (only the NDK; no Android Studio, SDK or JDK required, per README.md).
- .NET SDK 10 (builds `nx_extract` and the translator).
- Android platform-tools (`adb`) to install onto a device.
- Optional: `pyinstaller` and, on Windows, the Microsoft C++ Build Tools (for `packaging/build_bootloader.py`).
- macOS with Xcode for the Apple host/Metal work (`nxnative/dm/host/Makefile`, `nxnative/dm/gfx/metal/Makefile`); not needed for the Android port.
- Roughly 20 GB free disk space recommended (`porter/toolchain.py` `DISK_GB`); a NEO-sized port takes about 7 GB of build folder.

**Player (end user):**
- Windows x64 bundle from GitHub Releases (`nx2android-<version>-windows-x64.zip`, README.md) with no Python or toolchains to install; the Setup tab downloads the rest.
- Their own `prod.keys` and NSP/XCI files (never shipped).
- An Android device with a Vulkan 1.3 driver and BC texture support (Adreno or Xclipse GPU; Mali and PowerVR are not supported), Android 10+, USB debugging if installing from the tool.

**Production (what is produced):**
- Per-game Android APK (`lib/arm64-v8a/libdmhost.so`, NativeActivity, `minSdk` 29, `targetSdk` 36), signed with the player's own key, plus a data pack (`<App>-data/`) pushed to `/sdcard/Android/data/<package>/files`.
- No server-side deployment; the project publishes no hosted service.

---

*Stack analysis: 2026-10-29*
