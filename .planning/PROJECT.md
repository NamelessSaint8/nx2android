# nx2android

## What This Is

nx2android turns a player's own Nintendo Switch game dump into a native Android app. It rewrites the game's ARM64 code to run on Android, replays NVN graphics on Vulkan, translates the shaders, and builds a signed APK plus a data pack, then installs both over adb. Today the shipped tool is a thin PySide6 GUI over a headless CLI, available only as a Windows bundle. This milestone reworks that GUI and ships it on Windows, macOS and Linux for the developer and a few testers.

## Core Value

A tester on any supported host (Windows x64, macOS Apple Silicon, Linux x64, Linux arm64) can take their own Switch dump and get a working port onto their Android device through the GUI, without help.

## Requirements

### Validated

<!-- Inferred from the existing code (.planning/codebase/, mapped 2026-10-29). -->

- ✓ Port a Switch NSP/XCI (base game, update, DLC) to a signed Android APK and data pack, using the player's own prod.keys — existing
- ✓ Detect the game in a folder and match it to a profile (`porter inspect`) — existing
- ✓ Cache the slow stages (extract, rewrite, shader split, translator build, Vulkan shaders) and skip them when their inputs are unchanged — existing
- ✓ Install a port to a connected device over adb, resuming and verifying pushed files — existing
- ✓ Optional 60 fps through FPSLocker-Warehouse configs (`--fps60`) — existing
- ✓ Setup checks, plus downloads of NDK r27c, .NET 10 and platform-tools from vendor URLs — existing
- ✓ 11 titles playable on the Legion Y700 (Snapdragon 8 Elite): 13 Sentinels, Advance Wars 1+2, DKC Returns HD, Graveyard Keeper 2, Hades II, Mario vs. DK, NEO TWEWY, Super Mario Bros. Wonder, Tales of Eternia, Unpacking, Viractal. Unicorn Overlord boots; Xenoblade 3 is WIP — existing
- ✓ PySide6 GUI (Port, Setup, Games tabs) that drives `python -m porter` over JSON-lines events and holds no pipeline logic — existing
- ✓ Windows x64 PyInstaller bundle that needs no Python install — existing
- ✓ Architecture rules enforced by tests: no game-specific code in `nxnative/dm/android/`, profiles are data only — existing
- ✓ Conventional Commits hook in `.githooks/` (opt-in via `core.hooksPath`) — existing

### Active

<!-- Milestone v1: cross-platform GUI rework. Hypotheses until shipped and verified by testers. -->

**Reworked GUI**
- [ ] Game library: every ported game in one view, with status, version, re-port after an update, and uninstall
- [ ] Device manager: pick from connected devices, show GPU compatibility (BC textures, Vulkan 1.3), and install, update or remove per device
- [ ] Per-game settings in the UI (60 fps, language, controller/touch overlay layout, env switches) instead of CLI flags
- [ ] Guided first run: prod.keys, toolchain downloads and the first device, in place of the Setup checklist
- [ ] GUI stays on PySide6 (Qt Widgets) per research, keeping the GUI ↔ porter process boundary

**Cross-platform bundles**
- [ ] Windows x64 bundle
- [ ] macOS Apple Silicon `.app`, signed with a Developer ID and notarized
- [ ] Linux x64 bundle
- [ ] Linux arm64 bundle, using distro adb and a community arm64 NDK build that Setup detects or fetches
- [ ] GitHub Actions builds every bundle, signs and notarizes the macOS one, and runs the test suite on each OS

**Hardening (all of `.planning/codebase/CONCERNS.md`)**
- [ ] Cancel stops the whole process tree on every OS; closing the window during a port asks first and stops the run
- [ ] Errors from the CLI reach the GUI with their real cause (no swallowed stderr, no "no game found" for a crash)
- [ ] Zip and tar extraction cannot write outside the unpack folder (symlinks, `..`, absolute paths; tar uses `filter='data'` and refuses Pythons without the CVE-2025-4517 fix: 3.11.13 / 3.12.11 / 3.13.4+)
- [ ] The signing key is written atomically with mode 0600, and the tool refuses to silently regenerate it
- [ ] Downloads and FPSLocker configs are checked against pinned or recorded hashes
- [ ] A lock per build folder prevents two ports of the same game running at once
- [ ] The pipeline passes env dicts to subprocesses instead of mutating `os.environ`; upstream monkey-patches are named and asserted
- [ ] Python dependencies are pinned; devtools dependencies are declared
- [ ] Tests cover the GUI event bridge, downloads/unpacking, adb/install, toolchain detection and CLI error paths
- [ ] Data pack swap is atomic; install hashes files in chunks
- [ ] Remaining smaller items in CONCERNS.md (rich-text escaping, font choice, call timeouts, duplicate `probes/app/mkapk.py`, FLIP version record, Ryujinx patch file, hooks bootstrap)

**Verification**
- [ ] On each of the four hosts, a tester ports and installs at least one already-playable title end to end through the new GUI

### Out of Scope

- macOS Intel: there is no Intel test hardware, so it was dropped rather than shipped unverified
- Public-release polish (installer UX, public docs, support channels): this milestone is for the developer and a few testers
- Mali and PowerVR GPUs: they can't read BC-compressed textures, which the runtime requires
- Shipping game files, keys or FPSLocker configs: players supply their own dumps and prod.keys; the warehouse configs have no license
- **Deferred to the next milestone** (split by priority, cross-platform GUI first):
  - Make BotW, TotK, Mario Kart 8 Deluxe, Super Mario Odyssey and Smash Ultimate playable (status `playable`, tested on a device)
  - Bring Unicorn Overlord (boots) and Xenoblade 3 (WIP) to playable
  - Fix the known issues: Mario Wonder dips to 40 fps and shows button icons as `?`
  - More devices: other Snapdragon/Adreno phones and tablets, Snapdragon retro handhelds (AYN, Retroid), Samsung Xclipse
  - Cheat manager: Atmosphère cheat files supplied by the player plus default cheats in profiles, run by an in-engine cheat VM, with individual cheats toggled in game
  - Wii and Wii U native compiles: a feasibility study only (research plus a throwaway spike on whether PowerPC static recompilation fits this pipeline), with a written verdict

## Context

- **Brownfield.** The codebase map is in `.planning/codebase/` (ARCHITECTURE, STACK, CONCERNS, CONVENTIONS, INTEGRATIONS, STRUCTURE, TESTING), mapped at commit `9d67ede` on 2026-10-29.
- **Fork.** `origin` is NamelessSaint8/nx2android; `upstream` is shirai91/nx2android. The engine under `nxnative/` is a separate git subtree with its own upstream.
- **Layers.** `gui/` (about 440 lines of PySide6) → `porter/` (CLI and pipeline, the single implementation) → engine tools run as subprocesses → device over adb. The GUI and the CLI talk only through `--progress json` events and `--json` documents; `gui/runner.py` is the only consumer of that protocol.
- **Existing cross-platform groundwork.** `porter/paths.py`, `porter/toolchain.py`, `porter/fetch.py` and `nxnative/dm/android/build.py` already branch per OS. The blockers sit in the GUI (cancel, fonts), packaging (Windows-only bootloader, spec and `is_local()` check) and the release check.
- **Known GUI bugs.** Cancel on macOS and Linux leaves `dotnet`/`clang` children running. `call_json` discards stderr. There's no `closeEvent` and no call timeouts. Game names go into rich text unescaped. `PortTab.update_port_button` duplicates a pipeline decision.
- **Test hosts available.** Windows x64, macOS Apple Silicon (the dev machine), Linux x64, Linux arm64. Android devices: Legion Y700 TB322FC (8 Elite, Adreno 830) and TB320FC (8+ Gen 1, Adreno 730); more device families are available for the next milestone.
- **Tests today.** Python `unittest` under `tests/`. `tests/test_porter.py` imports the full engine and fails without `lz4`. The C tests need a compiler. There are no GUI tests and no CI.

## Constraints

- **Upstream compatibility**: keep syncing shirai91/nx2android, so diffs to shared files stay small and mergeable. The rework should live mostly in new or GUI-owned files.
- **Engine subtree**: changes to `nxnative/dm/{host,gfx,tools,third_party}` stay small and platform-guarded, because they merge with `git subtree pull`.
- **Architecture**: the GUI holds no pipeline logic; every rule lives in `porter/` and reaches the GUI through the JSON protocol. A new CLI flag is added in `porter/cli.py` first. This is enforced by `docs/ARCHITECTURE.md` and `tests/arch_rules.py`.
- **No game-specific code in the Android runtime**: per-title data goes in `nxnative/dm/games/<title ID>/` (enforced by `tests/arch_rules.py`).
- **Toolchains are not bundled**: NDK, .NET and adb are downloaded by Setup or supplied by the player. On Linux arm64 there are no official Google NDK or platform-tools builds, so the tool uses distro adb and a community arm64 NDK.
- **macOS distribution**: Developer ID signing plus notarization, which means hardened runtime and entitlements for the frozen Python and the child processes it launches. The signing secrets live in GitHub Actions.
- **Python**: 3.11+ for dev runs; bundles ship 3.14. Safe tar extraction needs `filter='data'` and the CVE-2025-4517 fix (3.11.13 / 3.12.11 / 3.13.4+).
- **Android target**: arm64-v8a, Android 10+ (minSdk 29), Vulkan 1.3, BC texture support.
- **Legal**: never ship keys, game files or FPSLocker configs.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Split by priority: v1 = cross-platform GUI rework + hardening + bundles; games, devices, cheats and Wii/Wii U next | The developer ranked the cross-platform GUI first; keeps the first milestone shippable | — Pending |
| Rework the GUI (library, device manager, per-game settings, guided first run) rather than only packaging it | Testers need more than today's three tabs | — Pending |
| GUI toolkit: keep PySide6 (Qt Widgets) | Research: the frozen executable is also porter's and the engine scripts' Python, so any other toolkit ships two runtimes and two signing paths | — Pending (gated on the Phase 1 packaging spike) |
| Hosts: Windows x64, macOS Apple Silicon, Linux x64, Linux arm64; macOS Intel dropped | Matches the test hardware the developer has | — Pending |
| Linux arm64 uses distro adb and a community arm64 NDK | Google publishes no linux-arm64 host builds | — Pending |
| macOS bundle signed and notarized with a Developer ID | Testers open it without Gatekeeper warnings | — Pending |
| GitHub Actions builds, signs and tests all bundles | Four hosts are too many to build and check by hand | — Pending |
| Hardening covers all of CONCERNS.md | The developer chose a solid base before adding features | — Pending |
| Keep syncing upstream shirai91/nx2android | Upstream fixes keep flowing into the fork | — Pending |
| Next-milestone titles must reach `playable`, not just boot | Same bar as today's 11 playable titles | — Pending |
| Cheats: Atmosphère files plus profile defaults, toggled in game | The standard format, plus curated defaults | — Pending |
| Wii/Wii U is a feasibility study only | It needs a PowerPC static recompiler, which is a new engine | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-10-29 after initialization*
