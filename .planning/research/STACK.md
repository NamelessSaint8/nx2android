# Stack Research

**Domain:** Cross-platform desktop GUI and distribution for a Python CLI pipeline (nx2android v1: Windows x64, macOS arm64, Linux x64, Linux arm64)
**Researched:** 2026-10-29
**Confidence:** HIGH for versions and wheel availability (checked against PyPI's JSON API, the GitHub releases API, Microsoft's .NET release metadata and the Debian, Launchpad and Fedora package APIs). MEDIUM for macOS entitlements and CI details (vendor docs plus practitioner reports).

## Verdict in one paragraph

Keep PySide6 (Qt Widgets) and PyInstaller, and add only what each OS needs. Every alternative GUI (Tauri, Electron, Flutter, Slint, NiceGUI or pywebview) still needs a frozen Python next to it, because the bundle's one executable is also the interpreter that `porter` and the unfrozen engine tools run under (`nx2android -m porter …`, `nx2android <script.py> …`, see `packaging/nx2android.py`). Switching would mean two runtimes, two signing paths and a second language, and the problems you know about (cancel, stderr, fonts, escaping) would stay. PySide6 6.12 is built on Qt 6.12, the current LTS. It ships official wheels for all four hosts, and its Linux aarch64 wheel includes the Wayland and XCB platform plugins. The work this milestone is packaging, not the toolkit. That means a macOS `.app` with signing and notarization, Linux tarballs, a CI matrix, a lockfile, and arm64-aware NDK paths.

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| Python (bundle interpreter) | **3.14.10** (pin 3.14.x for bundles; dev keeps 3.11+) | Interpreter frozen into every bundle | Every dependency has cp314 wheels on all four hosts (lz4 4.4.5, pillow 13.0.0, pyyaml 6.0.3; capstone and PySide6 are abi3/py3). `compression.zstd` is built in, so bundles drop `backports.zstd`. 3.15 (released 2026-10-09, now 3.15.2) is **not** ready: lz4 4.4.5 has no cp315 wheels, so it would build from source on four OSes. `actions/setup-python` has 3.14.10 for macOS arm64 and for Ubuntu 22.04/24.04 on both x64 and arm64. | HIGH |
| PySide6-Essentials | **6.12.0** (pin `==6.12.*`) | GUI toolkit (QtCore/QtGui/QtWidgets) | Built on Qt 6.12 LTS (released 2026-09-30, 5-year maintenance). Official wheels: `win_amd64`, `macosx_14_0_universal2`, `manylinux_2_34_x86_64`, `manylinux_2_39_aarch64`. Use **Essentials, not the `PySide6` meta-package**: `gui/` imports only QtCore/QtGui/QtWidgets, and `PySide6-Addons` (WebEngine, 3D, Multimedia…) only adds hundreds of MB to every bundle. | HIGH |
| Qt Widgets (not Qt Quick/QML) | (part of Essentials) | UI layer for the library, device manager, settings and first-run wizard | The existing code is Widgets. Model/View (`QAbstractTableModel` plus `QSortFilterProxyModel`) covers the game library and device list, and `QWizard` covers the guided first run, all with no new dependencies. Widgets has no QML JIT to worry about under macOS hardened runtime, and it tests headlessly with `QT_QPA_PLATFORM=offscreen` and `QtTest`, both in Essentials. | HIGH |
| PyInstaller | **6.22.3** (pin `==6.22.*`) | Freeze Python plus the GUI into a one-folder bundle per OS | It already works here, and its "the bundle's exe is the interpreter" pattern (`runpy` for `-m` and for `.py`, `freeze_support`) is something Nuitka and Briefcase don't support cleanly. Wheels exist for win_amd64, macOS universal2 and manylinux2014 aarch64/x86_64. On macOS it signs every collected binary with `codesign_identity=` and turns on hardened runtime with it, and `BUNDLE()` builds the `.app`. | HIGH |
| pyinstaller-hooks-contrib | **2026.9** | Hooks for PySide6, Pillow and others | It is released alongside PyInstaller, so pin them together. | HIGH |
| uv | **0.13.6** (dev/CI tool only, never shipped) | Resolve and lock Python dependencies | `uv pip compile --universal --generate-hashes` writes **one** `requirements.txt` with environment markers that is valid on all four hosts. Plain `pip install --require-hashes` can install from it, so players and CI don't need uv. | HIGH (version) / MEDIUM (workflow) |

### Pipeline dependencies (pin what is tested today)

| Library | Pin | Notes | Confidence |
|---------|-----|-------|------------|
| capstone | `==5.0.9` (and `<6`) | **6.0 is in alpha (6.0.0a9) with renamed AArch64 APIs.** An unpinned install picks it up as soon as it goes final and breaks `patch_nso.py`. py3-none wheels exist for all four hosts. | HIGH |
| lz4 | `==4.4.5` | Has cp311 to cp314 wheels incl. `manylinux2014_aarch64`. **No cp315**, which is why the bundle stays on 3.14. | HIGH |
| pillow | `==13.0.*` | 13.0 needs Python 3.11 or later, which matches the project floor. | HIGH |
| pyyaml | `==6.0.3` | cp314 wheels on all four hosts. | HIGH |
| backports.zstd | `==1.8.0; python_version < "3.14"` | Dev machines on 3.11 to 3.13 only. Bundles on 3.14 skip it, so remove it from `packaging/nx2android.spec`'s `collect_all` list when `sys.version_info >= (3, 14)` (the spec already guards this). | HIGH |

### Host toolchains the player's Setup fetches (not bundled)

| Toolchain | Windows x64 / macOS arm64 / Linux x64 | Linux arm64 | Confidence |
|-----------|---------------------------------------|-------------|------------|
| Android NDK r27c (27.2.12479018) | Google's `dl.google.com` zips (unchanged) | **HomuHomu833/android-ndk-custom**, release tag `r27`, asset `android-ndk-r27c-aarch64-linux-gnu.tar.xz` (121 MB, MIT build scripts, repo active as of 2026-10-28, 198 stars). It includes `shader-tools/linux-arm64/glslc`, `clang-18`, `ld.lld` and `llvm-strip`. **Its host folder is `linux-arm64`, not `linux-x86_64`**, so `nxnative/dm/android/build.py` line 27 needs a platform-guarded `platform.machine()` branch. **The asset is re-uploaded in place** (last re-uploaded 2026-10-03 at sha256 `9c6214a6…fdc00c`), so a recorded hash breaks whenever the maintainer rebuilds. Pin the digest anyway and fail closed with a clear message plus the "point Setup at your own NDK" path. | HIGH (asset and layout verified by listing the tarball) / MEDIUM (maintenance outlook) |
| .NET SDK 10 | dotnet-install / release metadata (unchanged) | Official `linux-arm64` SDK. The latest is **10.0.403** (2026-10-25), supported on Ubuntu 22.04/24.04/26.04, Debian 13 and Fedora 43/44 on Arm64. `porter/fetch.py` already maps `aarch64` to `linux-arm64`. | HIGH |
| adb | Google platform-tools zips | **Distro package**: Debian 13 `adb` 34.0.5, Ubuntu 24.04 `adb` 34.0.4 (25.10+ has 34.0.5), Fedora 43 `android-tools` 37.0.0, Arch `android-tools` 37.0.0. Also needs udev rules plus the `plugdev` group (Debian/Ubuntu: `android-sdk-platform-tools-common`). Setup should detect `adb` on PATH and print the install command for each distro. | HIGH |

### Development and CI tools

| Tool | Purpose | Notes |
|------|---------|-------|
| GitHub Actions, standard hosted runners | Build, test and sign all four bundles | The repo is public, so standard runners, arm64 included, are free. Use explicit labels, never `-latest` (see the matrix below). |
| `xcrun notarytool` + `xcrun stapler` (Xcode on the macOS runner) | Notarize and staple | `altool` stopped working on 2023-11-01. Authenticate with an **App Store Connect API key** (`--key/--key-id/--issuer`), not an Apple ID app-specific password. API keys are revocable and don't trigger 2FA. |
| `codesign`, `security` (macOS built-ins) | Sign; temporary CI keychain | Follow GitHub's documented temp-keychain recipe (create, then `set-keychain-settings -lut 21600`, unlock, `import -A`, `set-key-partition-list -S apple-tool:,apple:`, `list-keychain`). No marketplace action is needed. |
| `hdiutil` (macOS built-in) | Build the `.dmg` | A DMG can be stapled, but a `.zip` can't. The macOS `zip` and `shutil.make_archive` also drop the symlinks PyInstaller relies on. |
| `tar` (GNU tar on the runners) | Linux archives | Keeps PyInstaller 6's symlinks. Don't zip Linux bundles. |
| PyInstaller bootloader built from source (`packaging/build_bootloader.py`) | Windows only | The `windows-2025` runner has MSVC Build Tools. Keep this step to avoid AV flags, and skip it on macOS/Linux (make `is_local()` Windows-only, CONCERNS.md). |

## CI runner matrix

| Target | Runner label | Why this one | Artifact |
|--------|--------------|--------------|----------|
| Windows x64 | `windows-2025` | Current image with MSVC for the bootloader | `nx2android-<ver>-windows-x64.zip` |
| macOS arm64 | `macos-15` (or `macos-26`; both are Apple Silicon) | Native arm64; Xcode with notarytool. The PySide6 6.12 wheel sets the **minimum macOS to 14 Sonoma** | `nx2android-<ver>-macos-arm64.dmg` (signed, notarized, stapled) |
| Linux x64 | `ubuntu-22.04` | The **oldest glibc that PySide6 6.12 accepts** (wheel is `manylinux_2_34`, runner has 2.35). Bundles built here run on glibc 2.35+ (Ubuntu 22.04+, Debian 12+, Fedora 36+) | `nx2android-<ver>-linux-x64.tar.gz` |
| Linux arm64 | `ubuntu-24.04-arm` | **This is forced:** PySide6's aarch64 wheel is `manylinux_2_39` (it has been since 6.8.3), so it won't install on `ubuntu-22.04-arm`. The bundle needs **glibc 2.39+ on the tester's machine** (Ubuntu 24.04+, Debian 13, Fedora 40+). Debian 12 and Raspberry Pi OS bookworm can't run it. | `nx2android-<ver>-linux-arm64.tar.gz` |

The test job runs the same four-runner matrix with `python -m unittest discover tests` and `QT_QPA_PLATFORM=offscreen`, so no Xvfb is needed. Run the signing and notarization steps only on `push: tags: ['v*']` or `workflow_dispatch`, inside a GitHub **Environment** (e.g. `release`) that holds the secrets and requires approval. Pull-request runs then never see them, and fork PRs never get them in any case.

**Secrets (all in the `release` Environment):** `MACOS_CERT_P12_BASE64` (Developer ID Application cert and key, exported as .p12), `MACOS_CERT_PASSWORD`, `KEYCHAIN_PASSWORD` (random), `APPLE_API_KEY_P8_BASE64`, `APPLE_API_KEY_ID`, `APPLE_API_ISSUER_ID`, `APPLE_TEAM_ID`. Decode the .p8 into `$RUNNER_TEMP` and never echo it. GitHub-hosted runners are destroyed after the job, so no keychain cleanup is needed.

## macOS signing and notarization: the specific recipe

1. **Spec:** add a macOS-only `BUNDLE(coll, name='nx2android.app', bundle_identifier='io.github.namelesssaint8.nx2android', info_plist={'LSMinimumSystemVersion': '14.0', 'NSHighResolutionCapable': True})`. Pass `codesign_identity=os.environ.get('MACOS_SIGN_IDENTITY')` and `entitlements_file='packaging/entitlements.plist'` to `EXE()`. PyInstaller then signs every collected dylib/.so with the same Team ID under hardened runtime, so **`disable-library-validation` isn't needed**.
2. **Entitlements:** start with **none**. If a `MemoryError` comes from ctypes (capstone's bindings are ctypes) under the signed build, add only `com.apple.security.cs.allow-unsigned-executable-memory` to that one executable. Don't add `allow-jit` (no QML, and CPython's JIT is off by default), `allow-dyld-environment-variables` or `disable-library-validation` speculatively. Apple DTS advises finding the failing API instead of stacking entitlements. Plist files must contain no comments. (MEDIUM: practitioner reports, to be confirmed by a signed-build smoke test in CI.)
3. **Child processes are fine as they are.** The frozen app re-executing itself (`nx2android -m porter`, `nx2android script.py`) runs the same signed binary. Downloaded `dotnet`, NDK `clang`/`ld.lld`/`glslc` and `adb` are separate executables. Hardened runtime and library validation apply to the process that loads libraries, not to children. Files written by Python's `urllib` get **no `com.apple.quarantine` xattr**, so Gatekeeper never checks them. Don't set `LSFileQuarantineEnabled` in Info.plist, because that would quarantine everything the app downloads. `dotnet build` output is ad-hoc signed by the linker on arm64 and runs without a Developer ID.
4. **Bundle contents must pass notarization:** the notary service rejects any unsigned Mach-O. The tracked tree has exactly one: **`nxnative/dm/gfx/tools/dmsh_xlate_bin/dmsh_xlate`** (arm64 apphost, the iOS chain's prebuilt translator, which the Android port doesn't use per `porter/pipeline.py`). Leave the whole `dmsh_xlate_bin/` folder (64 files) out of every bundle in `build_bundle.py`.
5. **Layout:** `nxnative/` must live under `Contents/Resources/`, not next to the executable in `Contents/MacOS/` (non-code files there break signing). `porter/paths.py` `REPO` then needs a frozen-macOS branch: `Path(sys.executable).parent.parent / 'Resources'`.
6. **Submit and staple:** `codesign --verify --deep --strict` the `.app`, build the DMG with `hdiutil create -format UDZO`, sign the DMG, then `xcrun notarytool submit app.dmg --key … --key-id … --issuer … --wait`. Run `xcrun notarytool log <id>` on failure, then `xcrun stapler staple app.dmg` and `spctl -a -t open --context context:primary-signature -v app.dmg`.

## Installation (developer and CI)

```bash
# requirements.in: the human-edited, unpinned list (today's requirements.txt contents, with PySide6 changed to PySide6-Essentials)
# requirements.txt: generated, pinned and hashed, valid on all four hosts; committed
uv pip compile requirements.in --universal --python-version 3.11 --generate-hashes -o requirements.txt

# Anyone (no uv needed):
python -m pip install --require-hashes -r requirements.txt

# Build-only extras (CI and the bundle builder):
#   requirements-build.in -> pyinstaller==6.22.*, pyinstaller-hooks-contrib==2026.9
#   requirements-dev.in   -> numpy, av (devtools/burst.py, devtools/rec_flicker.py; closes the CONCERNS.md item)
uv pip compile requirements-build.in --universal --python-version 3.11 --generate-hashes -o requirements-build.txt
```

Use `--python-version 3.11` so the lock still resolves for the supported floor, and so the `backports.zstd` marker stays. Renovate or Dependabot (the `pip-compile` manager understands this layout) can propose bumps. Each bump is a commit whose CI matrix has to pass.

## Alternatives Considered

| Recommended | Alternative | When to Use the Alternative |
|-------------|-------------|-----------------------------|
| PySide6 (Qt Widgets) | **Tauri 2** (Rust + system webview) with the frozen Python as a sidecar | Only if the team wants a web-tech UI and is willing to maintain Rust, a JS frontend, *and* the PyInstaller sidecar. On Linux it depends on the system WebKitGTK version, and the sidecar has to be signed and notarized separately. For four tabs over a JSON-lines protocol, that cost buys nothing. |
| PySide6 | **Flutter** desktop | Linux arm64 is a supported deployment target, but it adds Dart and a second runtime, and the Python sidecar problem stays the same as with Tauri. |
| PySide6 | **Electron** | Never for this app: about 150 MB of Chromium per OS on top of the Python bundle, plus the Chromium-specific hardened-runtime entitlements (`allow-jit`). |
| PySide6 | **Slint** (Python bindings) | Not yet. The Python package is still beta (`1.18.1b1`) and needs Python 3.12+. It's worth another look when it reaches 1.x stable. |
| PySide6 | **NiceGUI 3.18 / pywebview 6.2** | Only for a browser-tab UI. pywebview on Linux depends on GTK/WebKit2GTK through PyGObject (no manylinux wheels) or on QtWebEngine (so you'd be back on Qt, plus Chromium). Freezing either for Linux arm64 is the most fragile option on the list. |
| PyInstaller 6.22 | **Nuitka 4.3** | When startup time or source protection matters. Here the bundle has to *act as a general interpreter* for unfrozen engine scripts that import arbitrary stdlib modules. Nuitka would have to compile the whole stdlib to match today's `collect_submodules(stdlib)` spec, with long C builds on four OSes. |
| PyInstaller 6.22 | **Briefcase 0.4.7** | When you want a native installer per distro (.deb/.rpm) and automatic macOS notarization. Its stub has no "run this .py / -m module" interpreter mode, Linux packages must be built per distro, and its own docs discourage the AppImage backend. |
| PyInstaller 6.22 | **python-build-standalone + a launcher script** (a real `python3` inside the bundle) | Fallback if PyInstaller's frozen-interpreter quirks (multiprocessing, `sys.executable`, `runpy`) start costing more than they save. It's a real interpreter, so engine tools run unmodified. It still needs the same per-binary macOS signing. |
| tar.gz (Linux) | **AppImage** (type2 runtime) | For a single-file download for testers later. Downsides: it needs FUSE on the host (Ubuntu 24.04 ships `libfuse2t64`, not installed by default), its squashfs mount is read-only (see "bundle tree must stay read-only" below), and the mount disappears if the GUI exits while a `porter` child still runs from it. |
| Distro adb on Linux arm64 | Community static adb (e.g. `zhuwanhong/android-sdk-linux-arm64`, `kaspersigi/android-sdk-linux-aarch64`) | Only if a tester's distro has no `adb` package. These are low-star, single-maintainer builds. |
| HomuHomu833 NDK r27c | `kaspersigi/android-ndk-r27d-linux-aarch64` (r27d, 1 star), `SnowNF/ndk-aarch64-linux` (r25c/r29 only) | If HomuHomu833 disappears. r27d isn't r27c, so the pipeline's cache keys and `NDK_REVISION` check would need to accept it. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `PySide6` meta-package | It pulls in `PySide6-Addons` (WebEngine, 3D, Multimedia, PDF…), which the GUI never imports, and makes every bundle much larger | `PySide6-Essentials==6.12.*` |
| Python 3.15 for bundles (this milestone) | lz4 has no cp315 wheels, so it would build from source on all four runners | Python 3.14.x |
| `ubuntu-22.04-arm` / `ubuntu-latest` for the arm64 build | PySide6's aarch64 wheel needs glibc 2.39, and `-latest` labels move under you | `ubuntu-24.04-arm` |
| Building Linux x64 on `ubuntu-24.04` | Raises the tester glibc floor from 2.35 to 2.39 for no gain | `ubuntu-22.04` |
| Flatpak | The sandbox blocks USB access for adb and running downloaded toolchains in the user dir unless you open broad holes (`--device=all`, `--filesystem=home`), which defeats the purpose | tar.gz |
| `zip` / `shutil.make_archive('zip')` on macOS and Linux | It turns PyInstaller 6's symlinks into copies (bloat) or breaks them | `hdiutil` DMG (macOS), `tar czf` (Linux); zip only on Windows |
| `altool`, Apple ID app-specific passwords in CI | altool stopped working in Nov 2023; passwords are tied to a person and to 2FA | `notarytool` with an App Store Connect API key |
| `codesign --deep` as the signing method | Apple advises against it. It signs in the wrong order and applies entitlements to non-executables | PyInstaller's per-binary signing via `codesign_identity=`; use `--deep` only with `--verify` |
| Speculative entitlements (`disable-library-validation`, `allow-jit`, `allow-dyld-environment-variables`) | They weaken hardened runtime with no known need | Start with none; add one when you hit a specific error |
| `capstone` unpinned | 6.0 (alpha now) renames AArch64 APIs used by the rewriter | `capstone==5.0.9` |
| `pip freeze > requirements.txt` | It locks for one OS only, so a Windows-made freeze is wrong on Linux arm64 | `uv pip compile --universal` |
| psutil (for process-tree kill) | Not needed. Qt 6.6+ `QProcess.setUnixProcessParameters(CreateNewSession)` plus `os.killpg` on POSIX, and the existing `taskkill /T` (or a Job Object) on Windows, cover it with no new dependency | Built-ins (verify the PySide6 enum name in the phase) |

## Stack Patterns by Variant

**Windows x64:** one-folder PyInstaller build with the source-built bootloader and `console=True`. Keep the existing hide-console logic, zip it, leave it unsigned (SmartScreen will say "unknown publisher", which is acceptable for a few testers. Azure Artifact Signing is a later, public-release concern).

**macOS arm64:** `BUNDLE()` `.app`, `nxnative/` in `Contents/Resources`, signed per binary with hardened runtime, DMG notarized and stapled. **Finder starts apps with a minimal PATH**, so `porter/toolchain.py` must find `adb`/`dotnet` by full path (`/opt/homebrew/bin`, `/usr/local/bin`, the player's toolchains dir) and must not rely on PATH.

**All variants: the bundle tree must stay read-only.** A notarized `.app` that writes into itself breaks its seal, a DMG or translocated `.app` is mounted read-only, and an AppImage is squashfs. Two writes happen today: (1) Python writes `__pycache__` next to the engine scripts it imports from `nxnative/`. Set `sys.dont_write_bytecode = True` in `packaging/nx2android.py` when frozen. (2) `build_nx_extract` runs `dotnet build <bundle>/nxnative/dm/tools/nx_extract -o <tmp>`, which still writes `obj/` into the source folder. The same is likely true for the `dmsh_xlate` build under `third_party/ryujinx`. Build from a copy in the user dir, or redirect `BaseIntermediateOutputPath`.

**Linux x64 / arm64:** one-folder build, `tar.gz`. Testers need the system libraries Qt's XCB/Wayland plugins load (`libxcb-cursor0`, `libxkbcommon-x11-0`, `libegl1`, `libfontconfig1`, `libdbus-1-3`; PyInstaller doesn't bundle these system libs). Document them in `packaging/INSTALL.md`. The aarch64 wheel includes `platforms/libqwayland.so`, `libqxcb.so`, the `xdg-desktop-portal` platform theme and the `adwaita` Wayland decoration plugin, so native Wayland and portal file dialogs work. The phase still has to confirm that PyInstaller's PySide6 hook *collects* the `wayland-*` plugin folders into `dist/`. `QT_QPA_PLATFORM=xcb` is the escape hatch.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| PySide6-Essentials 6.12.0 | Python 3.10 to 3.15 (abi3); macOS **14+**; glibc **2.34+** x64 / **2.39+** aarch64 | The macOS floor rose from 13 to 14 in 6.12. Pin `6.11.*` instead if a tester is on macOS 13 (the 6.11 wheel is `macosx_13_0`; aarch64 is still 2.39). |
| PyInstaller 6.22.3 | Python 3.8 to 3.15; PySide6 6.12 via hooks-contrib 2026.9 | Bump PyInstaller and hooks-contrib together. |
| pillow 13.0.0 | Python ≥ 3.11 | Matches the project floor; 3.10 is no longer possible. |
| lz4 4.4.5 | Python ≤ 3.14 (wheels) | This blocks a 3.15 bundle. |
| HomuHomu833 NDK r27c | glibc aarch64 hosts | Host tag `linux-arm64` in `toolchains/llvm/prebuilt/` and `shader-tools/`. `build.py` currently hardcodes `linux-x86_64`. |
| .NET SDK 10.0.403 | linux-arm64 on Ubuntu 22.04+ / Debian 13 / Fedora 43+ | Support ends 2028-11-14 (LTS). |
| adb 34.0.4 (Ubuntu 24.04) | The project's adb usage (`push --sync`, `install`, `shell`) | Old enough to check during the arm64 verification. Fedora/Arch ship 37.x. |

## Sources

- PyPI JSON API (`pypi.org/pypi/<pkg>/json`), queried 2026-10-29: versions, upload dates and wheel tags for PySide6/-Essentials/-Addons/shiboken6 6.12.0 (and 6.7 to 6.11 for the glibc and macOS floor history), pyinstaller 6.22.3, pyinstaller-hooks-contrib 2026.9, nuitka 4.3.1, briefcase 0.4.7, pywebview 6.2.1, nicegui 3.18.0, slint 1.18.1b1, capstone 5.0.9 / 6.0.0a9, lz4 4.4.5, pillow 13.0.0, pyyaml 6.0.3, backports.zstd 1.8.0, uv 0.13.6. HIGH
- PySide6-Essentials 6.12.0 `manylinux_2_39_aarch64` wheel, central directory read remotely: confirmed `libqwayland.so`, `libqxcb.so`, `libqxdgdesktopportal.so`, wayland shell/decoration plugins. HIGH
- GitHub API `repos/HomuHomu833/android-ndk-custom/releases`, plus the streamed listing of `android-ndk-r27c-aarch64-linux-gnu.tar.xz`: asset names, sizes, digests, re-upload dates, `linux-arm64` host folders. HIGH
- GitHub API search for arm64 NDK builds (SnowNF, kaspersigi, zhuwanhong). MEDIUM
- Microsoft `builds.dotnet.microsoft.com/dotnet/release-metadata/10.0/releases.json` and `supported-os.json`. HIGH
- sources.debian.org API, Launchpad API, Fedora mdapi and the archlinux.org package API for adb versions. HIGH
- endoflife.date (Python 3.14.10 / 3.15.2, macOS versions); `actions/python-versions` manifest (setup-python builds for arm64 Linux and macOS). HIGH
- https://pyinstaller.org/en/stable/feature-notes.html: macOS signing, hardened runtime with identity, entitlements_file, BUNDLE signing. HIGH
- https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html: symlinks and zip, the reduced Finder PATH, sys.executable, freeze_support. HIGH
- https://docs.github.com/en/actions/how-tos/deploy/deploy-to-third-party-platforms/sign-xcode-applications: temporary keychain recipe and secret handling. HIGH
- https://docs.github.com/en/actions/reference/runners/github-hosted-runners and https://github.blog/changelog/2026-02-26-macos-26-is-now-generally-available-for-github-hosted-runners/: runner labels. MEDIUM (web search summary of the pages)
- https://www.phoronix.com/news/Qt-6.12-LTS-Released and https://qt.io/blog/qt-6.12-released: Qt 6.12 LTS. MEDIUM
- https://developer.apple.com/tutorials/data/documentation/security/customizing-the-notarization-workflow.md: altool retired, notarytool. MEDIUM
- https://developer.apple.com/forums/thread/132908, https://developer.apple.com/forums/thread/129546, https://haim.dev/posts/2020-08-08-python-macos-app, https://fman.io/blog/fman-works-again-on-macos-mojave/: entitlements for Python apps (dated 2020 to 2021). LOW to MEDIUM, so confirm with a signed smoke test
- https://briefcase.beeware.org/en/v0.3.25/reference/platforms/linux/index.html: Briefcase's Linux targets and its AppImage stance. MEDIUM
- https://docs.flutter.dev/reference/supported-platforms: Flutter's Linux arm64 deployment target. MEDIUM
- Local code read: `packaging/nx2android.py`, `packaging/nx2android.spec`, `packaging/build_bundle.py`, `porter/paths.py`, `porter/fetch.py`, `nxnative/dm/android/build.py`, `nxnative/scripts/build_ipa_from_nsp.py` (`build_nx_extract`), the `git ls-files nxnative | file` scan for Mach-O/ELF.

---
*Stack research for: nx2android v1 cross-platform GUI and distribution*
*Researched: 2026-10-29*
