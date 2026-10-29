# Pitfalls Research

**Domain:** Cross-platform frozen Python desktop tool (PySide6 GUI over a CLI pipeline) that downloads and runs native toolchains (NDK clang, .NET SDK, adb), with signed macOS notarized bundles, Linux x64/arm64 bundles and Windows x64, built in GitHub Actions, in a fork that also carries a git subtree.
**Researched:** 2026-10-29
**Confidence:** MEDIUM overall. Each pitfall carries its own tag. HIGH = checked against this repo's code or an official/primary source; MEDIUM = several community sources or strong prior knowledge, not re-verified this session; LOW = a plausible risk to check, no source confirmed it.

Phase names below are suggestions for the roadmapper. They assume this order: **P1 Packaging and CI spike** (all four hosts, toolkit decision), **P2 Hardening core** (process tree, errors, env, locks, extraction, atomic writes, key, pinning), **P3 Host toolchains** (Linux arm64 NDK, distro adb, Setup detection), **P4 GUI rework**, **P5 Signed release pipeline** (notarization, secrets, reproducibility), **P6 Tester verification**, plus an ongoing **Upstream sync** track.

## Critical Pitfalls

### Pitfall 1: The frozen bundle writes into itself, which breaks the macOS seal and fails on read-only installs

**What goes wrong:**
In a frozen build, `porter/paths.py` sets `REPO = Path(sys.executable).parent`, and `LOCAL_TOOLS = REPO / 'tools'`. `gui/runner.py` uses `REPO` as the working directory. `nxnative/dm/android/build.py` defaults its output to `DM / 'android/out'` (the pipeline passes `--out`, but any caller that does not lands inside the bundle). The engine's `.py` tools run unfrozen from `nxnative/` beside the executable, so their imports write `__pycache__/*.pyc` next to the sources. In a macOS `.app`, `sys.executable` is `Contents/MacOS/nx2android`, so all of this lands inside the signed bundle. Results: `codesign --verify` fails after first launch, Gatekeeper may refuse the app on the next launch, and an app run from a translocated or read-only location (Downloads before it is moved, a mounted DMG) gets `EROFS`/`EPERM` part-way through a port. The same problem appears in a Linux tarball unpacked to `/opt` and a Windows bundle in `Program Files`.

**Why it happens:**
The Windows bundle was designed as one portable, writable folder, and that assumption was never tested anywhere else.

**How to avoid:**
- Split `REPO` into a read-only resource root (on macOS `Contents/Resources/`, where non-code files belong, since codesign rejects non-Mach-O files in `Contents/MacOS`) and a writable root under `user_dir()`/cache.
- In `packaging/nx2android.py`, set `sys.dont_write_bytecode = True`, or set `sys.pycache_prefix` to a user cache folder, before any `runpy` call. Pass `PYTHONDONTWRITEBYTECODE=1` to children too.
- Set the working directory to a user folder, never the bundle.
- Add a CI step that runs a smoke port step, then runs `codesign --verify --deep --strict` on the `.app` again. On Linux, run the bundle from a `chmod -R a-w` copy.

**Warning signs:** `__pycache__` folders appear under `nxnative/` in an installed bundle; `codesign --verify` passes in CI and fails on a tester's machine; "a sealed resource is missing or invalid".

**Phase to address:** P1 (layout decision), verified in P5. Confidence: HIGH (from the code); App Translocation behaviour MEDIUM.

---

### Pitfall 2: Notarization rejects the bundle, or the notarized app crashes under the hardened runtime

**What goes wrong:**
- Notarization rejects any Mach-O in the bundle that lacks a Developer ID signature, a secure timestamp or the hardened runtime. That includes the `.so`/`.dylib` files from PySide6, capstone, lz4, Pillow and zstd, and any Mach-O inside nested zip/jar archives. `nxnative/` (Ryujinx, third_party) may carry prebuilt binaries or archives you have forgotten about.
- Signing with `--deep` (PyInstaller uses it for `.app` bundles) is discouraged by Apple. It applies one set of entitlements to everything and misses some nested code.
- Once signed, the hardened runtime blocks behaviours that worked unsigned:
  - Library validation refuses dylibs not signed by your Team ID.
  - `DYLD_*` variables are ignored.
  - Writable+executable memory is refused (libffi closures in ctypes, any JIT).
- For comparison, the python.org 3.12 interpreter on this machine is signed with `disable-library-validation`, `disable-executable-page-protection`, `allow-dyld-environment-variables` and `automation.apple-events`. That shows what CPython needs in the worst case, not what you should copy.
- Zipping the `.app` with `zip` instead of `ditto -c -k --keepParent` breaks framework symlinks. A stapled ticket cannot be attached to a `.zip`.

**Why it happens:**
Developers sign once on their own Mac, where library validation or quarantine never triggers, and they assume PyInstaller's signing is complete.

**How to avoid:**
- Have PyInstaller build ad-hoc signed output. Then sign with your own script from the inside out: every `.so`/`.dylib`, then the Qt frameworks, then the main executable with an entitlements file, then the `.app`. Pass `--options runtime --timestamp` every time and never `--deep`.
- Start with the smallest entitlement set (likely none, or only `com.apple.security.cs.allow-unsigned-executable-memory` if ctypes callbacks or QML JIT are used). Add an entitlement only when a hardened local build fails. Today `build_ipa_from_nsp.py` calls `ctypes.CDLL(None).clonefile`, a plain libSystem call that needs no entitlement.
- Before submitting, scan the bundle for Mach-O files (`find … -type f -exec file {} + | grep Mach-O`) and check each with `codesign -dvv` (look for `Timestamp=` and `flags=0x10000(runtime)`).
- Ship a signed DMG: notarize the DMG, then staple it. Run `xcrun stapler validate` and `spctl -a -vvv -t install` in CI.
- If `notarytool` returns Invalid, fetch `xcrun notarytool log <id>` automatically.
- If the GUI toolkit uses QML/QtQuick, the V4 JIT needs `allow-jit`, or set `QV4_FORCE_INTERPRETER=1`.

**Warning signs:** notarytool "Invalid" with "The signature does not include a secure timestamp" or "The binary is not signed with a valid Developer ID certificate"; the app opens locally and crashes on a tester's Mac with `Library not loaded … code signature … not valid for use in process`.

**Phase to address:** P1 (a signed, notarized hello-world bundle built from CI, before any GUI work), P5 (final). Confidence: HIGH for Apple's rules and the local entitlements dump; MEDIUM that the minimal set is enough for this app (test it).

---

### Pitfall 3: Cancel kills the parent, and dotnet build servers, MSBuild nodes and the adb server outlive it

**What goes wrong:**
- On macOS/Linux, `gui/runner.py` `cancel()` calls `QProcess.kill()` on the direct child only (known bug).
- On Windows, `taskkill /T` walks the tree by parent PID, so it misses descendants whose intermediate parent already exited.
- `dotnet build` deliberately leaves MSBuild node-reuse processes, VBCSCompiler and (opt-in today, reportedly default in .NET 11 previews) the MSBuild server running after the build. On Windows they hold locks on files in `<title>_build/`, so the next port or `rmtree` fails with "file in use". The MSBuild server also keeps task assemblies loaded.
- If the first `adb` command of a port starts the adb server, that daemon inherits the port's pipes and process group. QProcess may never see EOF, and a group kill on cancel takes the adb server down for every other tool.
- Closing the GUI (no `closeEvent` today) orphans the whole tree.

**Why it happens:**
"Kill the child" looks like "kill the job". Windows already worked through `taskkill /T`, so nobody tested the POSIX path, and the dotnet servers are invisible until a lock error appears.

**How to avoid:**
- **POSIX:** start porter in its own session (`QProcess.setUnixProcessParameters(QProcess.UnixProcessFlag.CreateNewSession)`, Qt 6.6+, or `setChildProcessModifier(os.setsid)`). On cancel, send `os.killpg(pgid, SIGTERM)`, wait 3–5 s, then `SIGKILL`. Record the pgid at start, not at cancel.
- **Windows:** at porter startup, put porter in a Job Object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`. All descendants join it, and the tree dies even if the GUI crashes. Keep `taskkill /T` only as a fallback.
- **GUI death on any OS:** porter watches its stdin; on EOF (the GUI died) it kills its own group or job.
- **dotnet:** in porter's subprocess env, set `MSBUILDDISABLENODEREUSE=1`, `DOTNET_CLI_USE_MSBUILD_SERVER=0` (verify the variable name against SDK 10), and pass `-nodeReuse:false` and `-p:UseSharedCompilation=false` to `dotnet build`. After a cancel, run `dotnet build-server shutdown`.
- **adb:** start the adb server once from the GUI or Setup (`adb start-server`, output to DEVNULL) outside any port's process group, so ports never spawn it.
- Report "cancelled" only from `finished` (exit 130 or confirmed gone).
- Keep the kill logic at the porter/GUI root, not in `nxnative/scripts/build_ipa_from_nsp.py` `run()`. A session at the root covers every descendant without a subtree edit.

**Warning signs:** `ps -ef | grep -E 'dotnet|clang|VBCSCompiler|MSBuild'` shows processes after cancel; the second port on Windows fails in `rmtree` or shader stage; the GUI shows "cancelled" while the log keeps growing; device lists empty after a cancel.

**Phase to address:** P2. Add a scripted manual test on each host in P6. Confidence: HIGH (code, Qt docs for `CreateNewSession`, dotnet/cli issue on persistent servers); MEDIUM for the exact .NET 10/11 MSBuild server defaults.

---

### Pitfall 4: A killed or crashed stage leaves outputs the cache then trusts

**What goes wrong:**
The pipeline skips slow stages when their inputs are unchanged. Once SIGKILL and Job-object kills become routine (Pitfall 3), a stage interrupted mid-write can leave a partly written `extract/`, `shader/` or `.so` next to a reuse key that says it is current. The next port then "succeeds" with a corrupt build, and the error shows up on the device instead.

**Why it happens:**
Until now a cancel almost never happened mid-stage on macOS/Linux (the children kept running to completion), so the bug stayed hidden.

**How to avoid:**
Write each stage's reuse key or stamp last, atomically (temp file plus `os.replace`), after its outputs are complete. Or write the outputs to `stage.tmp/` and rename them into place. Add a test that kills a stage mid-run and checks the next run redoes it.

**Warning signs:** after a cancel, the next port finishes suspiciously fast; on-device crashes go away after deleting the build folder.

**Phase to address:** P2, together with process-tree cancel. Confidence: MEDIUM (I did not read every stage's key write order; verify per stage).

---

### Pitfall 5: The Linux arm64 bundle needs a newer glibc than testers have

**What goes wrong:**
A PyInstaller Linux bundle needs at least the newest glibc symbol used by any library it collected, including the build host's Python and libstdc++. PySide6 wheels set a floor:
- **6.12.0:** `manylinux_2_34_x86_64` and `manylinux_2_39_aarch64` (macOS `14_0`).
- **6.8.0 and 6.7.3:** `manylinux_2_28_x86_64` and `manylinux_2_31_aarch64`.

On 6.12, the arm64 bundle refuses to start on Debian 12 / Raspberry Pi OS bookworm (glibc 2.36) and Ubuntu 22.04 (2.35), with `GLIBC_2.38 not found`. GitHub's `ubuntu-24.04-arm` runner (glibc 2.39, now available for private repos too) hides this, because the bundle works on the runner.

**Why it happens:**
Developers build on the newest CI image and test on the same machine.

**How to avoid:**
- Decide the Linux floor explicitly (for example "Ubuntu 22.04 / Debian 12 or newer") and pick the PySide6 version whose wheels meet it. Pinning PySide6 is in scope anyway.
- Build inside a container whose glibc equals the floor, not on the runner OS.
- Add a CI step that runs `objdump -T` over every ELF in the bundle, takes the highest `GLIBC_` version found, and fails if it exceeds the floor. Smoke-start the bundle (`--version`, `QT_QPA_PLATFORM=offscreen`) in a container of the floor distro.
- Find out which distro the Linux arm64 tester actually runs before choosing.

**Warning signs:** `version 'GLIBC_2.3x' not found` reported by a tester; the arm64 bundle works on CI and on nothing older.

**Phase to address:** P1 (choose the floor and PySide6 pin together); enforce in P5. Confidence: HIGH (PyPI wheel tags fetched; GitHub changelog).

---

### Pitfall 6: Qt on Linux fails to start on real desktops (xcb-cursor, Wayland plugins, GL)

**What goes wrong:**
- From Qt 6.5, the xcb platform plugin needs `libxcb-cursor0`, which many installs lack. The app dies with "Could not load the Qt platform plugin xcb … even though it was found".
- On Wayland, Qt picks the wayland plugin if it is bundled. If the wayland shell/decoration plugins were not collected, windows have no title bar or fail to show.
- Bundling the build host's `libGL`, `libEGL`, `libwayland-*`, `libdrm`/`libgbm` or `libfontconfig` causes crashes or font errors against the tester's drivers and config.
- An AppImage needs FUSE 2 (`libfuse2`), which Ubuntu 22.04+ does not install by default.

**Why it happens:**
CI is headless, and the developer's own Linux box already has the full Qt dependency set from earlier projects.

**How to avoid:**
- Ship a plain `.tar.gz` (or AppImage with `--appimage-extract-and-run` documented) and a launcher script that checks for `libxcb-cursor.so.0` and prints the apt/dnf/pacman command when it is missing.
- Verify the bundle contains `platforms/libqwayland*.so` and the `wayland-*` plugin folders, or force `QT_QPA_PLATFORM=xcb` and document that choice.
- Confirm PyInstaller's exclude list keeps GL/EGL/wayland-client/drm out of the bundle.
- Smoke-test on a clean GNOME Wayland VM and a clean X11 VM for both arches, not only CI.

**Warning signs:** "qt.qpa.plugin: Could not load…"; no window decorations on GNOME; `Fontconfig error: unknown element`.

**Phase to address:** P1 (bundle smoke test), P6. Confidence: HIGH for xcb-cursor (Qt's own error message); MEDIUM for the Wayland plugin collection details.

---

### Pitfall 7: Distro adb on Linux is old, conflicts with other adbs, or has no USB permission

**What goes wrong:**
- `porter/adb.py` pushes with `push -Z` (disable compression). That flag arrived with adb push compression in platform-tools 30.x. Debian oldstable (bookworm) ships adb `29.0.6-28` (Ubuntu 22.04 is similar), so every install fails with an unknown-option error. Debian stable/trixie and Ubuntu now ship `34.0.5`.
- If a tester also has Android Studio's or another tool's adb, each client kills the other's server ("adb server version (41) doesn't match this client (39); killing…"), and devices vanish mid-push.
- Without udev rules and `plugdev` membership, the device shows as `no permissions (missing udev rules? user is in the plugdev group)`. The current UI could misreport that as "no device".
- Package names differ: Debian/Ubuntu `adb` (or `android-tools-adb`), Fedora/Arch `android-tools`.

**Why it happens:**
On Windows and macOS the tool controls the adb version by downloading platform-tools. On Linux arm64 it cannot, so every assumption about adb features breaks.

**How to avoid:**
- Parse `adb version` in `porter/toolchain.py` checks and set a minimum.
- Feature-gate `-Z` and other newer flags: drop `-Z` on old adb and accept the slower push.
- Surface the adb device state string (`unauthorized`, `no permissions`, `offline`) verbatim, with fix text (udev rules package `android-sdk-platform-tools-common` on Debian/Ubuntu, `android-udev-rules` elsewhere, then re-plug).
- Detect a running server of a different version (`adb version` versus `adb host-features` or the "doesn't match" message) and warn instead of fighting it.
- Prefer one adb per host: if the config names an adb, use only that one.

**Warning signs:** install fails only on Linux; devices drop when Android Studio is open; device list shows the serial but nothing works.

**Phase to address:** P3 (detection and gating), P4 (device manager shows real states), P6. Confidence: HIGH for `-Z` use in code and the Debian versions; MEDIUM for the exact adb release that added `-Z`.

---

### Pitfall 8: The "community arm64 NDK" is a different compiler in a different layout

**What goes wrong:**
- Google publishes no linux-aarch64 NDK host build. The visible community project (SnowNF/ndk-aarch64-linux) targets **r29**, not r27c. It is built with the system toolchain, skips tests, and maps `aarch64` to `x86_64` in the host detection, keeping the folder name `linux-x86_64`. Other builds use `linux-arm64` or `linux-aarch64`.
- `nxnative/dm/android/build.py` hardcodes `host = 'linux-x86_64'` on Linux for both clang and `shader-tools/<host>/glslc`. So the build either works by accident (same folder name) or fails, and in neither case is it the compiler the 11 playable titles were tested with.
- A different clang major can add new `-Werror` warnings, change codegen in a timing-sensitive runtime, and pair a mismatched `libc++_shared.so` with the headers.
- Community builds often omit `shader-tools/glslc`. They also inherit the glibc of the distro they were built on.
- Termux "NDK" builds are linked against bionic and do not run on desktop Linux at all.

**Why it happens:**
"An arm64 NDK exists" is treated as "r27c on arm64".

**How to avoid:**
- In Setup, detect any `toolchains/llvm/prebuilt/*/bin/clang`, run `clang --version` (this catches `Exec format error` and records the version), and compile and link a one-line C file with `--target=aarch64-linux-android29`. Store the result and show the clang version in the port log.
- Make `build.py` take the host folder and the glslc path from porter (an argument or env var, with today's default), as a small platform-guarded subtree change. On arm64, use distro `glslc` (shaderc).
- Pin the chosen community build by URL and SHA-256 in the repo. Prefer one built from the r27 branch. If none exists, evaluate the fallback: distro clang/lld of the same major version plus the official r27c **sysroot** and clang resource dir (`lib/clang/<ver>/lib/linux/libclang_rt.builtins-aarch64-android.a`) taken from the linux-x86_64 zip. Those files are architecture-independent.
- On Linux arm64, port one already-playable title and compare it on-device against the x64 build before calling arm64 supported.

**Warning signs:** `clang --version` on arm64 reports a different major than r27c; glslc not found; new warnings-as-errors only on arm64; a title that is playable on x64 builds misbehaves when built on arm64.

**Phase to address:** P3. This needs a dedicated research spike at phase start. Confidence: MEDIUM. Only one community project was inspected, and it is r29 only.

---

### Pitfall 9: Finder- and launcher-started GUIs see a different environment than the terminal

**What goes wrong:**
- An app started from Finder or the Dock gets `PATH=/usr/bin:/bin:/usr/sbin:/sbin`, cwd `/` and no `LANG`. `toolchain.find_dotnet` (`shutil.which('dotnet')`) and adb lookups that work from a terminal fail from the `.app`, and Homebrew/user installs are invisible.
- macOS TCC adds privacy prompts that are blamed on the app for every child process: game dumps in Downloads/Documents/Desktop, on removable or network volumes. A denial surfaces as `Operation not permitted` deep inside dotnet or clang.
- An ad-hoc or changing signature resets TCC grants on every build.
- Wireless adb to a LAN IP triggers macOS Local Network privacy (localhost:5037 is exempt).

**Why it happens:**
Developers always launch from a terminal with their shell profile loaded.

**How to avoid:**
- Search explicit locations (Homebrew `/opt/homebrew/bin`, `~/.dotnet`, the tool's own `player_tools()`) and store resolved absolute paths in config at Setup. Never rely on `PATH` at port time.
- Add `NSDocumentsFolderUsageDescription`, `NSDownloadsFolderUsageDescription`, `NSDesktopFolderUsageDescription`, `NSRemovableVolumesUsageDescription`, `NSNetworkVolumesUsageDescription` (and `NSLocalNetworkUsageDescription` if wireless adb is planned) to the `BUNDLE` `info_plist`.
- Have the guided first run pick the game folder through the native open panel, so the user's choice grants access.
- Map `PermissionError` on macOS to a message naming System Settings › Privacy & Security.
- Test by launching from Finder, never only from a terminal.

**Warning signs:** "dotnet not found" only when double-clicked; an EPERM in the extract stage when the game sits on an external SSD.

**Phase to address:** P3 (tool discovery), P4 (first-run flow), P6. Confidence: MEDIUM-HIGH (well-known macOS behaviour, not re-verified for macOS 15/26 this session).

---

### Pitfall 10: Extraction "fixes" that are still bypassable or reject valid toolchains

**What goes wrong:**
- **Tar:** `porter/fetch.py` `_untar` uses `filter='tar'` when available. The `'tar'` filter does not reject links whose targets point outside the destination; `'data'` does. Also, the filters themselves had bypasses (gh-135034: CVE-2025-4517/4330/4138/4435, CVE-2024-12718), fixed in **3.11.13 / 3.12.11 / 3.13.4**. So "require 3.11.4" in the CONCERNS fix is not enough.
- **Zip:** a symlink fix that checks `into / name` with `Path.is_relative_to` but resolves only one side gives false results. On macOS `/var`, `/tmp` and `/etc` are symlinks to `/private/...`, so resolve both sides.
- Checking the member name but not the link target lets a link point to `/` and a later regular file be written through it. So does creating symlinks before regular files.
- On Windows, zip names with `C:`, `\`, reserved names (`CON`, `NUL`) or trailing dots/spaces escape or fail.
- Over-strict fixes are a risk too: the NDK and platform-tools legitimately contain relative symlinks inside the tree (Unix builds), and rejecting all symlinks breaks the macOS/Linux NDK.

**Why it happens:**
Path checks are written once and tested only against the happy archive.

**How to avoid:**
- Use `filter='data'` everywhere.
- Require a patched interpreter: the bundle pins its own Python (CI pins `3.12.x ≥ 3.12.11` or `3.13.x ≥ 3.13.4`). For dev runs, `toolchain.checks` refuses Pythons below the fixed patch level instead of falling back to unfiltered extraction.
- For zip:
  - Write regular files first and symlinks last.
  - Require `(into / name).resolve()` and `(t.parent / target).resolve()` to stay within `into.resolve()`.
  - Reject absolute targets and names with drive letters, `..` components, or backslashes.
- Add crafted-archive unit tests (zip-slip name, absolute symlink, link-then-write, a valid internal relative link, a tar with a hardlink outside). They run on all three OSes in CI.

**Warning signs:** a test suite that has only "malicious archive is rejected" tests and no "real NDK layout still extracts" test; extraction differs between the dev Python and the bundle Python.

**Phase to address:** P2. Confidence: HIGH (python.org 3.11.13 release notes; code read).

---

### Pitfall 11: An atomic write that is not atomic on Windows, or not durable on macOS

**What goes wrong:**
- `os.replace` onto a file another process has open (antivirus, Search indexer, a second porter) raises `PermissionError` on Windows.
- A temp file created in `/tmp` and renamed to the user dir fails with `EXDEV` across volumes. Fix: create the temp file in the destination directory.
- `os.open(..., 0o600)` sets the mode only when it creates the file. An existing 0644 key stays 0644 unless chmodded, and on Windows the mode is ignored, so the per-user `%APPDATA%` ACL is the protection.
- On macOS, `fsync` does not flush the drive cache (`F_FULLFSYNC` does). On POSIX, fsync the directory too.
- Data pack swap: `rename(new, existing_dir)` fails with `ENOTEMPTY` on POSIX and fails on Windows, so the old pack must be moved aside first. A folder rename on Windows fails if any file inside is open (Explorer, an adb push reading it).

**Why it happens:**
"Write temp, then rename" is copied from a POSIX tutorial.

**How to avoid:**
Write one helper in porter, `atomic_write(path, data, mode=0o600)`:
- create the temp with `tempfile.mkstemp(dir=path.parent)` (already 0600), write, flush and fsync it (`fcntl.F_FULLFSYNC` on macOS);
- `os.replace` with a short retry loop on Windows `PermissionError`;
- fsync the parent directory on POSIX.

For directories, do rename old → `.old-<ts>`, then new → final, then rmtree old. On startup, recover a leftover `.old-*` if the final folder is missing. Test the helper on all three OSes in CI.

**Warning signs:** sporadic `PermissionError: [WinError 5]` in CI on Windows only; a key file with mode 0644 after an upgrade.

**Phase to address:** P2. Confidence: HIGH (documented OS behaviour).

---

### Pitfall 12: The signing key fix silently regenerates or forks the key, or a test overwrites the developer's real key

**What goes wrong:**
- The key writer is `nxnative/dm/android/apk/mkapk.py`, inside the subtree. Patching it there grows the subtree diff.
- A fix that "fails if unparseable" but still regenerates when the file is *missing* breaks every installed port after the user moves to a new machine or OS account, or after a settings-folder change (for example if `user_dir()` changes during the rework).
- New tests for install and pipeline paths that call `paths.signing_key()` without redirecting `user_dir()` can overwrite the developer's real key.
- CI must never create or use a real key.

**Why it happens:**
The key is generated lazily, deep inside a tool, and nobody owns it.

**How to avoid:**
- Let porter own the key: validate it, create it once via mkapk's generator, and write it with `atomic_write(..., 0o600)` before calling mkapk, so mkapk's regenerate branch never runs. Only a small or no subtree diff is needed.
- If a key existed before (record a fingerprint in config) and is now missing, stop and ask; do not create a new one.
- Show the key's fingerprint in Setup and offer "export key".
- Tests set an env override (for example `NX2ANDROID_HOME`) to a temp dir. A test fixture asserts that the real user dir is untouched.

**Warning signs:** `INSTALL_FAILED_UPDATE_INCOMPATIBLE` after an update; a key file mtime changes after a test run.

**Phase to address:** P2. Confidence: HIGH.

---

### Pitfall 13: An env-dict refactor breaks Windows executable lookup

**What goes wrong:**
On Windows, `subprocess.Popen(['dotnet', ...], env=env)` searches the **parent's** `PATH`, not the `PATH` inside `env`. POSIX uses the passed env's PATH. Removing the `os.environ['PATH']` mutation (in scope) therefore breaks `build_nx_extract`, which calls bare `dotnet`, on Windows only. Separately:
- `QProcessEnvironment.systemEnvironment()` on Windows keeps `Path` in its original case, so inserting `PATH` can create a duplicate entry.
- `DOTNET_ROOT` must reach the apphost children (`nx_extract`, `dmsh_xlate`) as well as `dotnet` itself.

**Why it happens:**
The refactor gets tested on the dev Mac.

**How to avoid:**
Resolve every tool to an absolute path once (`self.tools`) and pass absolute paths everywhere. Build the env as `dict(os.environ)` plus overrides, with keys normalised on Windows. Add a test that asserts `os.environ` is unchanged after `Port.run` in-process, and run it on Windows CI.

**Warning signs:** "dotnet is not recognized" or `FileNotFoundError` only on Windows after the refactor.

**Phase to address:** P2. Confidence: HIGH (subprocess docs; CONCERNS.md names the dependency).

---

### Pitfall 14: Pinning hashes for moving targets breaks Setup every month

**What goes wrong:**
The .NET 10 SDK patch version changes about monthly, and Microsoft's release metadata moves to the new one. Google's repository index lists only the latest platform-tools. Pinning "the hash of latest" fails as soon as either vendor publishes a new release, and testers cannot set up. Pinning the FPSLocker-Warehouse fetch to one commit freezes it: configs added later for new game versions never appear.

Two more gaps:
- **NuGet.** The port restores NuGet packages at port time: `LibHac 0.19.0` for `nx_extract`, and unversioned references (`Humanizer`, `MsgPack.Cli`, `Gommon`, `Microsoft.IO.RecyclableMemoryStream`) in the vendored Ryujinx projects. That is an unpinned supply-chain path the CONCERNS list does not mention.
- **Network on the first port.** The restore also needs network access on the first port.

**Why it happens:**
"Pin everything" without separating immutable artifacts from channels.

**How to avoid:**
- Pin an exact version plus hash for each artifact: NDK r27c, a specific `10.0.1xx` SDK, a specific platform-tools release. Download that exact URL rather than "latest", and record them in one manifest in the repo. Updating means changing one manifest line after a test.
- For FPSLocker, record the commit SHA you fetched from (resolve the branch head through the API) and the config's SHA-256 in the build folder and the log. Warn on a change; do not hard-fail.
- For NuGet, enable `RestorePackagesWithLockFile`, commit `packages.lock.json`, restore with `--locked-mode`, and run `dotnet restore` in Setup rather than in the first port, so offline problems show up there.

**Warning signs:** "checksum mismatch" reports right after a Patch Tuesday; a port fails offline at the shader stage.

**Phase to address:** P2 (manifest), P3 (Setup restore). Confidence: MEDIUM-HIGH. The release cadence is well known; that older platform-tools URLs remain downloadable is LOW confidence, so verify it.

---

### Pitfall 15: CI signing secrets leak, block contributors, or hang the job

**What goes wrong:**
- `codesign` waits forever on a keychain access prompt when the p12 is imported without `security set-key-partition-list -S apple-tool:,apple: -k <pw> <kc>` and an unlocked temporary keychain.
- The same secrets are unavailable on PRs from forks (including any upstream contributor), so a required "sign" step fails every external PR.
- Someone "fixes" that with `pull_request_target` plus a checkout of the PR head, which runs untrusted code with the Developer ID secrets.
- Third-party actions referenced by tag can be re-pointed. The tj-actions/changed-files compromise (March 2025) dumped secrets from thousands of workflows.
- Notarization waits can exceed job timeouts.
- An app-specific password tied to a personal Apple ID breaks when the password is rotated.

**Why it happens:**
Signing gets bolted onto a build workflow that also runs on PRs.

**How to avoid:**
- Split the workflows: `build-test.yml` (all OSes, ad-hoc signed, runs on PRs) and `release.yml` (tags or manual dispatch only).
- Put the secrets in a GitHub Environment with a protection rule.
- Use an App Store Connect API key (`notarytool --key/--key-id/--issuer`) instead of an Apple ID password.
- Create a throwaway keychain per job and delete it in an `if: always()` step.
- Pin every action to a full commit SHA.
- Give `notarytool submit --wait --timeout 30m` its own retry.
- Never echo the base64 p12.
- Record the certificate's expiry date in `docs/RELEASE_CHECK.md` (Developer ID Application certificates last about 5 years).

**Warning signs:** a macOS job stuck at "codesign" until the 6 h timeout; a workflow file containing `pull_request_target`; `uses: foo/bar@v3` without a SHA.

**Phase to address:** P1 (workflow skeleton and split), P5 (secrets and notarization). Confidence: HIGH.

---

### Pitfall 16: Builds that cannot be reproduced or that drift with runner images

**What goes wrong:**
`macos-latest`, `ubuntu-latest` and `windows-latest` move to new images, which changes Xcode, the default Python and MSVC toolsets. `actions/setup-python` gets a new patch version. Unpinned PyInstaller, hooks-contrib, PySide6 and capstone resolve differently. A bundle that passed the release check is then not the one rebuilt a week later. On macOS, a Homebrew Python sets the bundle's minimum macOS to the runner's OS. The Windows bootloader compiled from source (`packaging/build_bootloader.py`, to dodge AV false positives) needs a pinned MSVC.

**Why it happens:**
"It built green" is taken to mean "it's the same build".

**How to avoid:**
- Pin runner labels (`macos-15`, `ubuntu-24.04` with a floor container, `ubuntu-24.04-arm`, `windows-2022`) and the exact Python patch version.
- Pin `pip install --require-hashes -r requirements.lock` per OS/arch (pip-tools or uv lock).
- Pin the PyInstaller version and bootloader source hash.
- Set `SOURCE_DATE_EPOCH` and `PYTHONHASHSEED=0`.
- Write a build manifest (versions plus SHA-256 of each bundle) as a release asset.
- Use python.org/setup-python Python on macOS, never Homebrew. Check `LSMinimumSystemVersion` and the `minos` of the main binary (`vtool -show`).

**Warning signs:** the same tag rebuilt gives a different bundle size; a tester on an older macOS gets "You can't use this version of the application with this version of macOS".

**Phase to address:** P1 (pins), P5 (manifest). Confidence: HIGH.

---

### Pitfall 17: The toolkit switch breaks the "bundle executable is also the Python" contract

**What goes wrong:**
`packaging/nx2android.py` makes the single frozen executable the GUI, `-m porter`, the interpreter for every unfrozen engine `.py` tool (`nxnative/…`), and the `multiprocessing` spawn target (with the `WINEXE` hack). Toolkits whose packager is not PyInstaller break this silently. Examples: `flet build` and Briefcase; Tauri or Electron with a Python sidecar, which needs two bundles, sidecar signing and notarization, and a system WebKitGTK 4.1 on Linux. The engine tools then cannot run, or a second Python runtime has to be shipped, signed and notarized.

A "rewrite in the new toolkit, then reconnect" plan also stalls with neither GUI working, because the event protocol is implicit (`gui/runner.py` is its only consumer, and nothing tests it).

**Why it happens:**
The toolkit is chosen on widget features and screenshots, not on packaging and signing on all four hosts.

**How to avoid:**
- Make the toolkit decision in P1 on one criterion first: a hello-world in that toolkit, frozen as one executable that also runs `-m porter` and an `nxnative` `.py` script, signed and notarized on macOS arm64, and starting on the Linux arm64 floor distro. PySide6 already passes most of this, so any alternative must clear the same bar before feature work.
- Freeze the protocol before the rewrite: add a `"v"` field to events, write a JSON schema or dataclasses in porter, and record golden JSON-lines fixtures from real `porter port --progress json` and `--json` runs. Contract tests run against both the old and the new GUI parser.
- Build the new GUI beside the old one (strangler) and remove the old one only at feature parity.
- Keep LGPL compliance: PySide6 is LGPLv3, so ship it as separate shared libraries (onedir) with license texts. PyQt6 is GPL; do not switch to it casually.

**Warning signs:** the toolkit is chosen without a signed macOS build; the GUI parses an event field the porter tests never emit; two weeks into the rewrite, no GUI can run a port.

**Phase to address:** P1 (decision gate), P4 (strangler rewrite with contract tests). Confidence: HIGH for the repo facts; MEDIUM for alternative packagers' limits.

---

### Pitfall 18: The fork or the subtree becomes unmergeable during the rework

**What goes wrong:**
- **History rewrites.** Rebasing the fork onto shirai91 (or squash-merging branches that contain subtree commits) loses the `git-subtree-dir:` / `git-subtree-split:` trailers. `git subtree pull --squash` then fails or re-adds the tree.
- **Two paths for nxnative.** shirai91 itself carries `nxnative/` as a subtree. If the fork also pulls nxnative upstream directly, the same upstream content arrives twice under different squash commits, which guarantees conflicts.
- **Diff growth.** The hardening touches shared files (`porter/fetch.py`, `pipeline.py`, `cli.py`, `adb.py`, `toolchain.py`), and the subtree diff grows (`build.py` host tag, `mkapk.py`).
- **GUI rewrite.** Rewriting or deleting `gui/app.py` turns every upstream GUI fix into a modify/delete conflict.
- **Repo-wide churn.** Adding `.gitattributes` line-ending normalisation, a formatter run or file moves rewrites whole files.
- **Workflow names.** CI files named like upstream's future ones (`ci.yml`) collide.

**Why it happens:**
A large rework is done on a long-lived branch and synced "at the end".

**How to avoid:**
- Merge upstream (never rebase) at least weekly during the milestone.
- Choose one path for nxnative updates: through shirai91 merges, unless shirai91 lags. Write that rule into README "Updating nxnative".
- Offer the platform-neutral hardening fixes (zip-slip, tar filter, env dicts, key atomic write, process group) to shirai91 as small PRs first, so they stop being fork diffs.
- Put the rework in new files (`gui/` new modules, `porter/procs.py`, `porter/atomic.py`, `.github/workflows/fork-*.yml`).
- Add a CI job that prints `git diff --stat <recorded upstream commit> -- nxnative/` and fails above a threshold, and that runs `tests/arch_rules.py`.
- No repo-wide formatting or line-ending changes this milestone.

**Warning signs:** `git subtree pull` says "was never added" or conflicts in files you did not touch; upstream merge conflict count grows each sync; the fork's `nxnative` diff stat grows week over week.

**Phase to address:** the ongoing Upstream sync track (start in P1 with the CI diff check). Confidence: MEDIUM-HIGH. The subtree mechanics are well known; the double-subtree scenario is inferred from PROJECT.md.

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Sign the `.app` with PyInstaller's `--deep` and broad entitlements (`disable-library-validation`, `allow-unsigned-executable-memory`, `allow-dyld-environment-variables`) | Notarization passes on day one | Weaker hardened runtime; hides which library needs what; Apple DTS advises against it | Only as a bisecting step; ship the minimal set |
| `xattr -dr com.apple.quarantine` on whatever the user points Setup at | Downloaded-by-browser toolchains run without prompts | Strips Gatekeeper's check from unvetted binaries | Only with explicit user consent per folder, after hash match against the manifest |
| Keep `taskkill /T` and add `killpg` beside it, without Job Objects or a stdin watchdog | Small diff | GUI crash still orphans the tree; dotnet nodes still linger | MVP only if the dotnet env vars are set |
| Pin "latest" vendor hashes | One less manifest | Setup breaks each vendor release | Never; pin exact versions |
| Build Linux bundles on the runner OS | No container setup | glibc floor silently rises with each runner image | Never for releases; fine for PR smoke builds |
| Disable the arch_rules/subtree diff check to land the rework | Faster merges | Upstream sync becomes a project of its own | Never |
| Skip NuGet lock files | Nothing to maintain | Unpinned packages at port time; first port needs network | Never, since pinning is in scope |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Apple notary service | Uploading a `zip` made with `zip`; stapling a zip; using an Apple ID password | `ditto -c -k --keepParent` or a DMG; staple the DMG/app; App Store Connect API key; fetch the log on Invalid |
| .NET SDK (downloaded) | Running bare `dotnet` and relying on PATH; leaving node reuse on; letting first-run telemetry and the welcome banner pollute parsed output | Absolute path plus `DOTNET_ROOT`; `MSBUILDDISABLENODEREUSE=1`, `-nodeReuse:false`; `DOTNET_NOLOGO=1`, `DOTNET_CLI_TELEMETRY_OPTOUT=1`; on Linux check `libicu` or set `DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1` for the build (verify the tools need no culture data) |
| adb | Letting the first command auto-start the server inside a port's process tree; assuming flags from the latest platform-tools | `adb start-server` once from Setup/GUI with DEVNULL stdio; version and feature gating (`-Z`) |
| Google SDK repository index | Trusting the hash from the same index | Compare against the repo manifest; warn on mismatch |
| FPSLocker-Warehouse | Pinning to one commit forever, or not at all | Record the resolved commit SHA and file SHA-256; show both in the log |
| GitHub Actions arm64 | Assuming `ubuntu-24.04-arm` matches testers' glibc | Build in a floor container; check `GLIBC_` symbols |
| Windows console subsystem | Switching the bundle to `console=False` or a new toolkit and losing the hidden-console behaviour, so every `dotnet`/`clang`/`adb` child flashes a console window | Keep `console=True` plus the hide trick, or start children with `CREATE_NO_WINDOW`; check on Windows 11 with Windows Terminal as the default console, where `ShowWindow(GetConsoleWindow())` may not hide the window (LOW confidence, check it) |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Full-file MD5 in `push_tree` | Memory spikes, slow re-installs | Chunked hashing (`hashlib.file_digest` on 3.11+); cache host hashes per build | Rewritten modules of hundreds of MB |
| Old distro adb without push compression or the newer push protocol | Linux arm64 installs several times slower | Accept it, show the adb version in the log, recommend newer adb | Multi-GB data packs |
| SIGTERM grace too long, or waiting on `dotnet build-server shutdown` | Cancel feels hung | 3–5 s grace, then SIGKILL; run shutdown in the background | Every cancel |
| 2-vCPU arm64 runners in private repos | Linux arm64 CI takes far longer than x64 | Build only the bundle and a smoke test on arm64; run the full test suite on x64 | Every PR |
| Hard-link `link_tree` on exFAT/FAT external drives | Data pack build fails or copies everything | Detect `st_nlink` support; fall back to copy with a disk-space recheck | Games on exFAT USB drives (common on macOS/Windows) |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| `filter='tar'` instead of `'data'`, or a Python older than 3.11.13/3.12.11/3.13.4 | Arbitrary file write from a crafted SDK archive | `'data'` plus a pinned patched interpreter; refuse older Pythons |
| Zip symlink check resolving only one side | Escape through `/private/var` aliasing or link-then-write | Resolve both sides; files first, links last; crafted-archive tests |
| Developer ID p12 available to PR workflows | Certificate theft, then malware signed as you | Release-only workflow, protected Environment, SHA-pinned actions |
| Signing key regenerated silently, or written 0644 | Lost update path for every port; key readable by other local users | porter-owned `atomic_write(0o600)`; refuse when missing after a recorded fingerprint |
| Unpinned NuGet restore at port time | Supply-chain code running in the user's build | Lock files plus `--locked-mode` |
| Game names into rich text unescaped (exists today) | Markup injection in labels | `html.escape` or plain-text widgets; a test with `<b>&` in a name |
| Removing quarantine broadly to "fix" Gatekeeper prompts | Disables the user's malware check | Only for manifest-hash-verified tools, with consent |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Reporting a crash as "no game found" / "could not read download lists" (exists today) | Tester gives up or files the wrong bug | Every CLI path returns a JSON error with cause; the GUI shows it plus a "copy log" button |
| Device listed but `unauthorized` or `no permissions` shown as "no device" | Linux testers stuck at the first step | Show the adb state and the specific fix (accept the RSA prompt; udev rules; replug) |
| Gatekeeper "Open Anyway" instructions for unsigned dev builds | On macOS 15+ the Control-click override is gone; testers can't open the build | Only hand testers notarized builds; CI makes them |
| First port silently needs network for NuGet | Offline first port fails at an odd stage | Setup restores NuGet and reports it |
| Closing the window mid-port (no `closeEvent` today) | Orphaned builds, locked folder | Confirm dialog, then a real tree kill, then wait for exit |
| App run from Downloads or the DMG | Translocated read-only path, inconsistent behaviour | DMG with an Applications alias; detect translocation (path under `/private/var/folders/.../AppTranslocation/`) and ask the user to move the app |

## "Looks Done But Isn't" Checklist

- [ ] **Notarized macOS app:** often missing a re-check after first launch. Run `codesign --verify --strict` after running one port step, and check no `__pycache__` exists in `Contents/`.
- [ ] **Notarized macOS app:** often missing a test on a Mac that never had the dev environment. Download it through a browser (quarantined), open it from Finder, port one title.
- [ ] **Cancel:** often missing grandchildren. After cancel on each OS, `ps`/Task Manager shows no `dotnet`, `MSBuild`, `VBCSCompiler`, `clang` or `nx2android` children, and the build folder can be deleted at once.
- [ ] **Cancel:** often missing cache safety. The next port after a cancel redoes the interrupted stage.
- [ ] **Linux bundles:** often missing the glibc check. Run the highest-`GLIBC_` scan; start on the floor distro under both X11 and Wayland, without `libxcb-cursor0` (expect the helpful message).
- [ ] **Linux arm64:** often missing a real compiler check. Setup shows the clang version and passes a compile-and-link probe, and an arm64-built port of a playable title plays on the device.
- [ ] **adb on Linux:** often missing old-adb coverage. Install works with adb 29.0.6 (Debian 12), or Setup refuses it with a clear message.
- [ ] **Safe extraction:** often missing the positive test. The real NDK r27c (macOS and Linux) and the .NET tarball still extract with symlinks and exec bits intact after hardening.
- [ ] **Signing key:** often missing the "missing after recorded" case. Deleting the key file makes the next port stop and ask, not regenerate.
- [ ] **Env refactor:** often missing Windows. A port on Windows works with a dotnet that is not on the system PATH.
- [ ] **Hash pinning:** often missing the update path. The manifest update procedure is documented and a version bump is a one-line change.
- [ ] **CI:** often missing the fork-PR case. A PR from a fork runs build and test without secrets and goes green.
- [ ] **Upstream:** often missing a merge test. A test merge of current shirai91 into the milestone branch is done before the milestone closes.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Bundle writes into itself (1) | MEDIUM | Split read-only and writable roots in `paths.py`; set bytecode off in the launcher; re-sign; testers reinstall |
| Notarization rejected (2) | LOW | `notarytool log`; sign the listed file inside-out; resubmit |
| Orphaned processes and locked build folders (3) | LOW per user, MEDIUM to fix | Tell users `dotnet build-server shutdown` or reboot; ship the Job Object/killpg fix |
| Corrupt cached stage (4) | LOW | Delete `<title>_build/` or the stage folder; fix the stamp ordering |
| glibc floor too high (5) | MEDIUM | Rebuild in a floor container with an older PySide6 pin |
| Wrong arm64 compiler (8) | HIGH if found late | Switch to the sysroot plus matching-clang fallback; re-verify titles |
| Signing key lost or regenerated (12) | HIGH for users | Restore from backup/export; otherwise every port reinstalls with `--replace-signer` (save data loss on device) |
| Leaked Developer ID certificate (15) | HIGH | Revoke through Apple; rotate; re-sign and re-notarize all releases |
| Subtree trailers lost (18) | MEDIUM | `git subtree split`/`add` again from the recorded upstream commit; hand-merge the next pull once |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1 Bundle self-writes | P1, P5 | `codesign --verify` after a run; read-only Linux copy runs a port |
| 2 Notarization / hardened runtime | P1 spike, P5 | CI notarizes and staples; fresh-Mac Finder launch |
| 3 Process-tree cancel | P2 | Per-OS cancel script shows no survivors; folder deletable |
| 4 Cache after kill | P2 | Kill-mid-stage test reruns the stage |
| 5 glibc floor | P1, P5 | CI `GLIBC_` scan and floor-container start |
| 6 Qt on Linux desktops | P1, P6 | Clean X11 and Wayland VMs on x64 and arm64 |
| 7 Distro adb | P3, P4 | Install with adb 29 and 34; device states shown |
| 8 Community arm64 NDK | P3 (research spike) | clang probe plus on-device parity of one title |
| 9 Finder env / TCC | P3, P4, P6 | Finder launch; game on an external volume |
| 10 Extraction | P2 | Crafted and real-archive tests on 3 OSes |
| 11 Atomic writes | P2 | Helper tests on 3 OSes incl. open-file contention on Windows |
| 12 Signing key | P2 | Missing-key and test-isolation tests |
| 13 Env dicts | P2 | Windows port with dotnet off PATH; `os.environ` unchanged test |
| 14 Pinning | P2, P3 | Manifest-driven Setup; NuGet locked restore |
| 15 CI secrets | P1, P5 | Fork PR green without secrets; no `pull_request_target`; SHA-pinned actions |
| 16 Reproducibility | P1, P5 | Build manifest attached; rebuild gives the same versions |
| 17 Toolkit switch | P1 gate, P4 | Signed hello-world per host before choosing; protocol contract tests |
| 18 Fork/subtree | Upstream sync track from P1 | Weekly upstream merge; subtree diff CI check |

## Sources

- Repository code read this session: `gui/runner.py`, `porter/paths.py`, `porter/fetch.py`, `porter/adb.py`, `porter/toolchain.py`, `packaging/nx2android.py`, `packaging/nx2android.spec`, `nxnative/dm/android/build.py`, the csproj files; `.planning/codebase/CONCERNS.md`, `.planning/PROJECT.md` (HIGH)
- Local `codesign -d --entitlements -` on the python.org 3.12 framework interpreter (HIGH)
- [PyPI PySide6-Essentials JSON, versions 6.12.0 / 6.8.0 / 6.7.3](https://pypi.org/pypi/PySide6-Essentials/json): wheel glibc and macOS tags (HIGH)
- [Python 3.11.13 release notes, gh-135034](https://www.python.org/downloads/release/python-31113/); [OSV CVE-2025-4517](https://osv.dev/vulnerability/CVE-2025-4517); [Debian tracker CVE-2025-4517](https://security-tracker.debian.org/tracker/CVE-2025-4517) (HIGH)
- [Qt QProcess::UnixProcessParameters (6.6+)](https://doc.qt.io/qt-6/qprocess-unixprocessparameters.html); [qprocess.h CreateNewSession](https://codebrowser.dev/qt6/qtbase/src/corelib/io/qprocess.h.html) (HIGH)
- [PyInstaller feature notes: macOS signing](https://pyinstaller.org/en/stable/feature-notes.html); [PyInstaller changelog](https://pyinstaller.org/en/stable/CHANGES.html) (HIGH)
- [Apple: Hardened Runtime](https://developer.apple.com/documentation/security/hardened-runtime); [Apple Developer Forums, quarantine on notarized software](https://developer.apple.com/forums/thread/132908); [Signing and notarizing a Python macOS app](https://haim.dev/posts/2020-08-08-python-macos-app) (MEDIUM-HIGH)
- [dotnet/cli #9458, persistent build server processes](https://github.com/dotnet/cli/issues/9458); [Microsoft Learn: MSBuild server](https://learn.microsoft.com/visualstudio/msbuild/msbuild-server); [dotnet/msbuild #14289](https://github.com/dotnet/msbuild/issues/14289); [MSBuild server on by default in .NET 11 Preview 7 (blog, unverified)](https://startdebugging.net/2026/08/msbuild-server-on-by-default-dotnet-11-preview-7/) (MEDIUM)
- [Debian android-platform-tools tracker](https://tracker.debian.org/pkg/android-platform-tools): oldstable 29.0.6-28, stable 34.0.5-12 (HIGH)
- [SnowNF/ndk-aarch64-linux](https://github.com/SnowNF/ndk-aarch64-linux): r29 only, host-tag mapping caveats; [Android NDK: other build systems (host tags)](https://developer.android.com/ndk/guides/other_build_systems) (MEDIUM)
- [GitHub changelog: arm64 runners in private repositories (2026-01-29)](https://github.blog/changelog/2026-01-29-arm64-standard-runners-are-now-available-in-private-repositories); [arm64 runners GA for public repos](https://github.blog/changelog/2025-08-07-arm64-hosted-runners-for-public-repositories-are-now-generally-available/) (HIGH)
- [Riverbank PyQt list, xcb-cursor0 since Qt 6.5](https://riverbankcomputing.com/pipermail/pyqt/2024-December/046127.html); [Rocky Linux forum, PySide6 missing xcb plugin](https://forums.rockylinux.org/t/pyside6-on-rocky-linux-9-6-is-missing-xcb-plugin/19828); [NixOS discourse, PySide6 wayland plugin](https://discourse.nixos.org/t/python-library-pyside6-with-nixld/75208) (MEDIUM-HIGH)
- Prior knowledge, not re-verified this session (MEDIUM): Windows `CreateProcess` PATH lookup semantics in `subprocess`; macOS Finder launch environment and TCC purpose strings; the tj-actions/changed-files compromise (March 2025); `security set-key-partition-list` for CI keychains; Windows Terminal console hiding (LOW)

---
*Pitfalls research for: cross-platform frozen Python GUI with notarized macOS, Linux x64/arm64 and Windows bundles, and native toolchain subprocesses*
*Researched: 2026-10-29*
