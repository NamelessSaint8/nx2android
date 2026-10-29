# Project Research Summary

**Project:** nx2android, milestone v1 (cross-platform GUI rework, hardening, four-host bundles)
**Domain:** Cross-platform frozen-Python desktop GUI over a headless CLI pipeline that downloads and drives native toolchains (NDK, .NET, adb), with a signed and notarized macOS build, in a fork that syncs upstream and carries a git subtree
**Researched:** 2026-10-29
**Confidence:** MEDIUM-HIGH (versions and codebase facts HIGH; macOS entitlements, Linux arm64 NDK and competitor UX MEDIUM)

## Executive Summary

This milestone is mostly packaging and process plumbing. Keep PySide6 (Qt Widgets) and PyInstaller. All four researchers reached the same conclusion for the same reason: the bundle's one frozen executable is the GUI, `-m porter`, and the interpreter for the unfrozen engine scripts. Any non-Python toolkit (Tauri, Electron, Flutter) would still need a frozen Python next to it, which means two runtimes and two macOS signing paths. Treat the toolkit question as closed in Phase 1 unless the packaging spike shows PySide6 failing.

The architecture rule holds without changes. Each new feature (library, device manager, per-game settings, first run) is one new porter-owned record or command that returns JSON verdicts, plus one GUI view that displays them. Put the work in new files (`porter/cli_ext.py`, `library.py`, `devices.py`, new `gui/` modules) and keep edits to upstream's busy files (`pipeline.py`, `cli.py`, `gui/app.py`) to hook lines. Upstream changed `pipeline.py` 9 times in five days. Per-game settings fill only the options the CLI left unset, so a CLI port and a GUI port produce the same build. Route every setting to the cheapest place it takes effect (`env.txt` for switches and language, `DM_OVERLAY_EXTRA` for layout). Never route one through a modified `android.tsv`, because that invalidates every shader cache.

The main risks are platform-specific, and some will only appear on a tester's machine:
- The frozen bundle writes into itself (`REPO` = the executable's folder, `__pycache__`, dotnet `obj/` inside `nxnative/`), which breaks the macOS seal.
- POSIX cancel kills only the direct child, and MSBuild/VBCSCompiler outlive the port on Windows.
- The Linux arm64 bundle needs glibc 2.39 under PySide6 6.12.
- The community arm64 NDK is not the r27c the 11 titles were tested with.
- Distro adb can be too old for `push -Z`.

Prove the risky parts first. Build a signed, notarized bundle per host, run it read-only, kill a process tree, and then build the views.

## Key Findings

### Recommended Stack

Details: STACK.md. Pin everything and resolve one universal lockfile with uv. Build Linux on the oldest runner each wheel accepts.

**Core technologies:**
- **Python 3.14.10 for bundles** (dev floor stays 3.11+). Every dependency has cp314 wheels on all four hosts, and `compression.zstd` is built in. Don't use 3.15: lz4 has no cp315 wheels.
- **PySide6-Essentials 6.12.\*** (not the `PySide6` meta-package). Qt 6.12 LTS. Ships Wayland/XCB plugins on aarch64. Floors: macOS 14, glibc 2.34 on x64, **glibc 2.39 on aarch64**.
- **Qt Widgets** (no QML). Model/View covers the library and device list, and QWizard covers first run. It tests headless with `QT_QPA_PLATFORM=offscreen`, and with no QML JIT the hardened runtime needs no JIT entitlement.
- **PyInstaller 6.22.\* + hooks-contrib 2026.9.** Its "bundle exe is the interpreter" mode is what Nuitka and Briefcase lack. On macOS it signs each binary with `codesign_identity=`.
- **uv 0.13.6 (dev/CI only).** `uv pip compile --universal --generate-hashes` writes one hashed `requirements.txt` that is valid on all four hosts and installable with plain pip.
- **Pins:** `capstone==5.0.9` (6.0 alpha renames AArch64 APIs), `lz4==4.4.5`, `pillow==13.0.*`, `pyyaml==6.0.3`, `backports.zstd` only below 3.14.
- **CI runners:** `windows-2025`, `macos-15`, `ubuntu-22.04` (x64, glibc 2.35 floor), `ubuntu-24.04-arm` (forced by the 2.39 wheel). Don't use `-latest` labels.
- **macOS release:** `BUNDLE()` `.app` with `nxnative/` in `Contents/Resources`, per-binary signing, hardened runtime, **no entitlements to start**, then a DMG, `notarytool` with an App Store Connect API key, and `stapler`. Exclude `dmsh_xlate_bin/`, which holds the one unsigned tracked Mach-O.
- **Linux:** `.tar.gz`, not zip, AppImage or Flatpak. Document the system Qt libraries (`libxcb-cursor0` and others).

### Expected Features

Details: FEATURES.md. The audience is the developer plus a few remote testers, so failures need to be easy to understand and report. Polish and discovery features are worth little to them.

**Must have (table stakes):**
- A hardened bridge: structured `error` events, process-tree cancel, close confirmation, call timeouts, per-run logs. Every feature uses it.
- A library backed by a porter registry: icon, status, built version, an "update in folder" badge, Re-port with saved options, missing-folder detection, and three separate actions (uninstall from device / delete build files / remove from library).
- A device manager: adb states with fix text (`unauthorized`, `no permissions`), identity, a **compatibility verdict** (BC, Vulkan ≥ 1.3 via `pm list features`, SDK ≥ 29, arm64, free space, with unknown shown as unknown), polling refresh, installed ports per device, install/update/remove, and dialogs for signer mismatch and save loss.
- A per-game settings store and panel (60 fps, language, version, DLC, app name, env switches under Advanced). Each setting shows what applying it costs (data pack only / APK rebuild / full re-port). Reset to defaults.
- A guided first run built over `porter setup/doctor --json`: legal, prod.keys validation, toolchain downloads (progress, cancel, resume, hash), and the device step. It can be skipped and shows a banner until setup is complete.
- Copy diagnostics. It's cheap and is the biggest help for supporting testers remotely.

**Should have (differentiators):**
- A drag-canvas touch-overlay editor. The milestone names it. If time runs short, fall back to a numeric table over the same rows.
- The profile's compatibility line (`tested` device and version, known issues) and a "built version ≠ tested version" warning in the library row.
- The raw GPU/driver string beside the verdict, and a read-only preview of the effective `env.txt`.

**Defer (v1.x / v2+):**
- v1.x: games-root scan, wireless pairing, filtered logcat collection, launch on device, OS notifications, a new-release link.
- v2+: save backup (needs runtime support), cheat manager UI, notes for more device families.
- Anti-features, never build: cover-art scraping, online update checks, desktop copies of pause-menu settings, emulator-style graphics knobs, batch or multi-device jobs, telemetry, a firmware step, help finding keys.

### Architecture Approach

Details: ARCHITECTURE.md. `gui/runner.py` stays the only place that starts porter. It becomes the toolkit seam: it starts porter in its own process group, keeps stderr, applies timeouts and cancels the whole tree. Porter owns every record in `user_dir()`: the existing `config.json` plus new `games/<title ID>.json` files, written atomically by porter only. Device state and "first run done" are never stored. Both are queried live, and `ready` comes from `setup --json`. Protocol changes are additive only, with no protocol versioning, and are documented in `docs/FORK.md`.

**Major components:**
1. **`gui/runner.py` (edit) + `gui/shell.py`, `portview.py`, `library.py`, `devices.py`, `gamecfg.py`, `firstrun.py` (new):** these only display porter JSON. Upstream's `gui/app.py` is left untouched. The entry point switches to `gui.shell` once the new GUI reaches feature parity (strangler).
2. **`porter/cli_ext.py` (new, 2-line hook in `cli.py`):** the `library`, `game`, `device`, `uninstall` and `setup` subcommands.
3. **`porter/library.py` (new):** per-title records, the settings schema, precedence fill (CLI flag > per-game record > config.json > profile), and status joins.
4. **`porter/devices.py` (new):** device facts in one batched `adb shell` round trip, the compatibility verdict, uninstall. A device-side `nx2a-data.json` marks a complete pack.
5. **Engine hook:** `DM_OVERLAY_EXTRA` in `android_profile.py` (about 5 lines, platform-neutral, offer it upstream).
6. **Packaging/CI:** `ci.yml` (4-OS unittest) and `release.yml` (4 bundles, mac sign/notarize, a frozen smoke test running `nx2android -m porter doctor --json`). Hardening fixes go to shirai91 as PRs first.

### Critical Pitfalls

1. **The bundle writes into itself** (all three files agree). Split `REPO` into a read-only resource root (`Contents/Resources` on macOS) and a writable user root. Set `sys.dont_write_bytecode`/`PYTHONDONTWRITEBYTECODE=1`. Run from a user cwd. Avoid `dotnet build` writing `obj/` into the bundle, either by copying `nxnative/` to `user_dir()/engine/<VERSION>/` on first use or by redirecting `BaseIntermediateOutputPath`. Verify by running `codesign --verify --strict` *after* a port step, and by running Linux from a `chmod -R a-w` copy.
2. **Process tree survives cancel.** POSIX: new session (`setUnixProcessParameters(CreateNewSession)`, or porter calling `os.setsid()` under `NX2A_SESSION=1`), then killpg with SIGTERM, 3-5 s, SIGKILL. Windows: Job Object with `KILL_ON_JOB_CLOSE`, keeping `taskkill /T` as a fallback. Set `MSBUILDDISABLENODEREUSE=1`, `-nodeReuse:false` and `UseSharedCompilation=false`. Start the adb server outside any port's group. Corollary: once kills become routine, **stage stamps must be written last and atomically**, or the cache will trust half-written outputs.
3. **glibc floor on Linux arm64.** PySide6 6.12 aarch64 needs 2.39, which rules out Debian 12, Raspberry Pi OS bookworm and Ubuntu 22.04. Choose the floor and the PySide6 pin together. Add a CI `objdump -T` GLIBC scan and a smoke start in a container of the floor distro.
4. **Wrong compiler on Linux arm64.** The community NDK has a different host folder (`linux-arm64`), and `build.py` hardcodes `linux-x86_64`. It may also be a different clang build or lack glslc. Setup should probe `clang --version` plus a compile-and-link test, and pin by SHA-256. Arm64 counts as supported only after one playable title matches its x64 build on the device.
5. **Notarization and hardened runtime.** Every Mach-O needs a Developer ID signature, a timestamp and the runtime flag. Never sign with `--deep`. Start with no entitlements and add `allow-unsigned-executable-memory` only if ctypes (capstone) fails. Run signing from a release-only workflow inside a protected Environment, with SHA-pinned actions and no `pull_request_target`.

Also important: distro adb version gating (`-Z` needs ≥ 30.x; Debian 12 has 29.0.6); Finder launches get a minimal PATH, so resolve tools to absolute paths at Setup; TCC purpose strings in Info.plist; the Windows env-dict refactor breaks bare `dotnet` lookup because Windows searches the parent's PATH; pin exact vendor versions, not "latest"; NuGet lock files; signing-key ownership and test isolation; weekly upstream merges, never rebases.

## Reconciled Disagreements

**1. Linux arm64 NDK source.** STACK.md recommends HomuHomu833/android-ndk-custom (tag `r27`, asset `android-ndk-r27c-aarch64-linux-gnu.tar.xz`, `linux-arm64` host folder, includes glslc and clang-18). PITFALLS.md found only SnowNF (r29) and proposes a sysroot plus distro clang.
**Better supported:** STACK.md. It listed the actual tarball and found r27c with glslc, while PITFALLS.md says it inspected only one project. Use HomuHomu833 as the primary source. Keep PITFALLS' sysroot + matching distro clang as the documented fallback, and keep its verification protocol (clang probe, on-device parity) either way.
**Still to verify:**
- The asset is **re-uploaded in place**, so a pinned SHA-256 will break when the maintainer rebuilds. Pin it anyway. On a mismatch, fail closed with a clear message plus "point Setup at your own NDK". Consider mirroring the verified tarball as a release asset in the fork, but check the redistribution licence first.
- Check whether its clang-18 matches r27c's clang build exactly.
- Check which glibc it was built against.
- `build.py` needs a platform-guarded `platform.machine()` host-folder branch, or porter passes the host folder in.

**2. Build order.** ARCHITECTURE.md puts the bridge/boundary first, with CI and bundles in parallel. PITFALLS.md puts a packaging/CI spike (signed, notarized hello-world per host) before any GUI work.
**Resolution:** these don't really conflict. Both put packaging before the *new GUI*. ARCHITECTURE already runs CI/bundles (shipping today's GUI) in parallel with the porter data commands. Phase 1 below combines the two: bridge fixes are small and known, the packaging spike is the long-lead risk (Apple account, secrets, glibc, read-only layout), and neither depends on the new views. The bundle self-write fix belongs in Phase 1 because both files say a signed macOS bundle cannot work without it.

**3. Tar safety floor.** PROJECT.md says "pre-3.11.4 tar". PITFALLS.md says `filter='data'` (not `'tar'`, which `fetch.py` uses today) **and** a patched interpreter: 3.11.13 / 3.12.11 / 3.13.4 or later (gh-135034, CVE-2025-4517 and related).
**Better supported:** PITFALLS.md, which cites python.org release notes. Bundles on 3.14.10 already include the fix. For dev runs, `toolchain.checks` should refuse Pythons below those patch levels instead of falling back to unfiltered extraction. Update the PROJECT.md requirement text to match.

**Minor:** ARCHITECTURE lists `windows-latest`/`macos-14` and PITFALLS lists `windows-2022`. Use STACK's explicit labels (`windows-2025`, `macos-15`). ARCHITECTURE argues against protocol versioning, while PITFALLS suggests a `"v"` field plus golden fixtures. Take the golden JSON-lines contract fixtures, which are high value, and skip the version field, since the GUI and porter always ship together.

## Implications for Roadmap

### Phase 1: Bridge fixes + packaging/CI spike (4 hosts)
**Rationale:** This is the long-lead risk, and it is independent of the new views. Once it works, every later phase gets tested on all four OSes.
**Delivers:**
- `runner.py`: process-group cancel, kept stderr, timeouts. `closeEvent`. The structured `error` event. The `cli_ext` hook. `test_bridge.py` with golden fixtures.
- The `REPO` read-only/writable split, bytecode off, and the `nxnative` staging or `obj/` redirect.
- uv lockfile and pins. `ci.yml` (4-OS unittest, offscreen Qt).
- `release.yml` building today's GUI: Windows zip, signed and notarized DMG, two tarballs. A frozen smoke test, `codesign --verify` after a run, a GLIBC scan, and SHA-pinned actions with secrets in a release Environment.
**Avoids:** Pitfalls 1, 2, 5, 6, 15, 16, 17 (toolkit gate).

### Phase 2: Porter hardening core
**Rationale:** Every long-running feature depends on it. The build lock and env-dict refactor touch `pipeline.py` and must land before Re-port and per-game env go live. Upstream PRs go first.
**Delivers:**
- Windows Job Object and dotnet node-reuse env.
- Atomic stage stamps, an `atomic_write` helper, an atomic data-pack swap, chunked hashing.
- `filter='data'` and the patched-Python floor, plus zip checks that resolve both sides, with crafted and real-archive tests.
- Porter-owned signing key (0600, refuse to regenerate once a fingerprint is recorded, test isolation through `NX2ANDROID_HOME`).
- Env dicts with absolute tool paths. A build-folder lock. An exact-version hash manifest. NuGet lock files. The smaller CONCERNS items (rich-text escaping and the others).
**Avoids:** Pitfalls 3, 4, 10, 11, 12, 13, 14.

### Phase 3: Porter data commands + host toolchains
**Rationale:** The views only display these documents, and all of this work is headless and unit-testable. The Linux arm64 toolchain work produces the per-OS facts that `setup --json` reports.
**Delivers:**
- `library.py` (registry, precedence fill, `--fps60` as BooleanOptionalAction), `devices.py` (batched probe, verdict, uninstall), `setup --json`, the `game` schema/set, the `env.txt` hook, `DM_OVERLAY_EXTRA`.
- arm64 NDK detection and fetch with a clang probe, the `build.py` host-folder branch, distro adb detection with version and `-Z` gating.
- Absolute-path tool discovery for Finder launches. NuGet restore in Setup.
**Avoids:** Pitfalls 7, 8, 9, and Anti-patterns 1 and 2.

### Phase 4: New GUI (library, devices, per-game settings, overlay editor)
**Rationale:** Needs Phase 3's documents. Ships through Phase 1's pipeline. Built beside `gui/app.py` and switched over at feature parity.
**Delivers:** shell, portview, library, device manager, settings panel with cost badges, overlay editor (numeric fallback), copy diagnostics, TCC purpose strings.
**Avoids:** Pitfall 17 (strangler, contract tests) and GUI-side verdict logic.

### Phase 5: Guided first run
**Rationale:** Needs `setup --json` and the per-OS toolchain story, including Linux arm64 adb and NDK.
**Delivers:** a skippable wizard (legal, prod.keys validation, downloads, device step), license acceptance stored once, native open panel for the game folder.

### Phase 6: Release hardening + tester verification
**Rationale:** Final checks against the "looks done but isn't" list.
**Delivers:**
- Build manifest asset and certificate-expiry note.
- On each host, a tester ports and installs a playable title through the new GUI.
- macOS: browser download, then Finder launch.
- Linux: clean X11 and Wayland VMs.
- Per-OS cancel check: no surviving processes.
- A test merge of current upstream.

**Ongoing track: upstream sync.** Merge weekly (never rebase). CI check on the `nxnative/` diff stat. Use one path for nxnative updates (through shirai91). No repo-wide formatting changes.

### Phase Ordering Rationale
- Phases 1 and 2 can overlap. Phase 1 needs only the bridge, and Phase 2 touches porter internals.
- Phase 3's data commands could start alongside Phase 2, but Re-port and per-game env must wait for the lock and env-dict work.
- The order follows dependencies: views display porter documents, the wizard is a view over `setup`, and everything long-running uses the hardened bridge.

### Research Flags

Need `/gsd-plan-phase --research-phase`:
- **Phase 1:** hardened-runtime entitlements for frozen Python plus ctypes. `sys.executable`/`REPO` inside `.app`. Whether PySide6 binds `setUnixProcessParameters`/`CreateNewSession` (Qt 6.6 vs 6.7 is disputed; the fallback is porter-side `setsid`). Whether PyInstaller's hook collects the `wayland-*` plugin folders. The glibc floor decision (see Gaps).
- **Phase 3:** the Linux arm64 NDK (hash drift, clang build parity, glibc, fallback viability). The minimum distro adb version and when `-Z` was added. Presence of the Vulkan feature flag on the Y700 (`pm list features`). `pm list packages --show-versioncode` reliability.
- **Phase 2 (light):** .NET 10 MSBuild server env-var names. Whether older platform-tools URLs stay downloadable after a pin.

Standard patterns, skip research: Phase 4 (Qt Model/View, QGraphicsScene), Phase 5 (QWizard over a JSON doc), Phase 6.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Versions and wheel tags from the PyPI/GitHub/Microsoft APIs; the arm64 NDK tarball was listed directly. Entitlements MEDIUM (2020-21 practitioner sources) |
| Features | MEDIUM | Codebase-derived needs are HIGH; competitor patterns come from training knowledge and LOW web sources |
| Architecture | HIGH | Read from code at `95b2324` plus upstream churn data; platform facts (Qt flags, `.app` layout, MSBuild) MEDIUM |
| Pitfalls | MEDIUM-HIGH | Code-verified items and Apple/Python rules HIGH; arm64 NDK and .NET 11 defaults MEDIUM |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

1. **TOP OPEN QUESTION, for the developer: which distro and glibc does the Linux arm64 tester run?** PySide6 6.12's aarch64 wheel needs glibc 2.39 (Ubuntu 24.04+, Debian 13, Fedora 40+). If the tester is on Debian 12, Raspberry Pi OS bookworm or Ubuntu 22.04, **pin PySide6 6.8.\* for the arm64 bundle (`manylinux_2_31_aarch64`, glibc 2.31)** and build it inside a container matching that floor instead of on `ubuntu-24.04-arm`. Check two things with that fallback: whether 6.8 needs a separate lock or marker per arch, and whether its Wayland plugins are equivalent. Settle this before Phase 1's release job is final.
2. **HomuHomu833 NDK hash drift and compiler parity.** Phase 3 spike, described above.
3. **Minimum macOS version:** PySide6 6.12 requires macOS 14. Confirm that no tester runs macOS 13; otherwise pin 6.11.
4. **Entitlements:** whether no entitlements is enough under the signed build (capstone ctypes). Only a CI smoke test answers this.
5. **Vulkan 1.3 detection:** confirm that `feature:android.hardware.vulkan.version=4206592` appears on the Y700 before relying on it.
6. **Old adb:** support adb 29.0.6 without `-Z`, or refuse it in Setup.
7. **Apple Developer ID account and secrets:** must exist before Phase 1's release job can go green.

## Sources

### Primary (HIGH confidence)
- Codebase at `95b2324`: `gui/runner.py`, `gui/app.py`, `porter/*`, `packaging/*`, `nxnative/dm/android/{build.py,tools/android_profile.py,front_android.c}`, `nxnative/scripts/build_ipa_from_nsp.py`, `.planning/codebase/CONCERNS.md`; upstream `git log` churn
- PyPI JSON API (PySide6-Essentials 6.7 to 6.12, PyInstaller, lz4, capstone, pillow, uv and others); remote listing of the PySide6 aarch64 wheel
- GitHub releases API plus the streamed tarball listing for HomuHomu833/android-ndk-custom
- Microsoft .NET 10 release metadata; Debian/Launchpad/Fedora/Arch package APIs for adb
- python.org 3.11.13 release notes (gh-135034), OSV/Debian CVE-2025-4517
- PyInstaller feature notes and common pitfalls; Qt QProcess UnixProcessParameters docs; GitHub signing and runner docs

### Secondary (MEDIUM confidence)
- Apple notarization and hardened runtime docs and forums; haim.dev and fman entitlement write-ups
- dotnet/cli #9458, dotnet/msbuild #14289, Microsoft Learn on the MSBuild server
- SnowNF/ndk-aarch64-linux; Android NDK host-tag docs
- AOSP Vulkan implementation guide (feature encoding)
- Riverbank/Rocky/NixOS threads on Qt xcb-cursor and Wayland plugins

### Tertiary (LOW confidence)
- Competitor UX (Ryujinx/Eden, Dolphin GameINI, SideQuest, Lutris, Cemu, EmuDeck) from secondary guides and training knowledge
- `pm list packages --show-versioncode` man-page source; Windows Terminal console hiding; .NET 11 MSBuild-server default (blog)

---
*Research completed: 2026-10-29*
*Ready for roadmap: yes*
