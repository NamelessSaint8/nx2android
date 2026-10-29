---
phase: 01-bridge-bundles-and-ci
plan: 06
subsystem: infra
tags: [pyinstaller, packaging, macos, codesign, dmg, hdiutil, linux, glibc, tar.gz, smoke-test]

requires:
  - phase: 01-bridge-bundles-and-ci
    provides: "01-01 hashed build lock (PyInstaller 6.22.3) in .venv; 01-05 porter/paths.py REPO = Contents/Resources on macOS and _engine() reading <resource root>/ENGINE"
provides:
  - "packaging/build_bundle.py: version(), target(plat, machine), asset_name(version, os_, arch), bundled(files), engine_id(root, files); writes ENGINE and VERSION; dist/nx2android-<version>-<os>-<arch>.<zip|dmg|tar.gz>"
  - "packaging/nx2android.spec: BUNDLE on darwin (io.github.namelesssaint8.nx2android, LSBackgroundOnly false, macOS 14, five folder purpose strings); codesign_identity from MACOS_SIGN_IDENTITY"
  - "packaging/smoke_bundle.py <dmg|app|folder>: doctor, profiles, offscreen GUI, no-write listing, codesign verify, Linux Qt plugins"
  - "packaging/smoke_gui.py: run by the frozen exe; engine imports, capstone nop, Window lists profiles"
  - "packaging/glibc_floor.py <bundle> <floor>: need(texts), main(argv, texts=None)"
affects: [01-07 CI on four hosts, 01-08 fork-release.yml (notarize, staple, glibc gate, smoke), 01-03 Open log named in INSTALL.md]

actuals:
  tokens: 8900
  tasks: 3
  commits: 7
plan_head_before: 58f55990a4f54c5a47dd598d85a19d6c44b05176
plan_head_after: d9c6331040e7f7ad5c669237574d3bf0b9216f58

tech-stack:
  added: []
  patterns:
    - "Copy resources into the .app after PyInstaller, then re-sign only the outer bundle and verify --deep --strict before the DMG"
    - "Smoke a bundle from a read-only place (DMG mounted -readonly, or a chmod a-w copy) with a fresh NX2A_HOME and a before/after file listing"
    - "Archive per host: zip only on Windows, tar.gz on Linux, DMG on macOS (zip drops PyInstaller 6 symlinks)"

key-files:
  created:
    - packaging/smoke_bundle.py
    - packaging/smoke_gui.py
    - packaging/glibc_floor.py
    - tests/test_packaging.py
  modified:
    - packaging/nx2android.spec
    - packaging/build_bundle.py
    - packaging/INSTALL.md
    - README.md
    - docs/ARCHITECTURE.md

key-decisions:
  - "CFBundleShortVersionString takes the dotted numeric prefix of NX2A_VERSION (0.1.2 of 0.1.2-ns.1) and falls back to 0.0.0 for an untagged hash build"
  - "The build_bootloader.py requirement applies only on Windows; macOS and Linux use PyInstaller's own bootloader"
  - "smoke_gui.py runs from the checkout (not bundled); it adds the checkout to sys.path only when not frozen, so a developer can run it too"

patterns-established:
  - "Bundle smoke lines are PASS or [RED] like arch_rules.py; any [RED] means exit 1"

requirements-completed: [PKG-01, PKG-02, PKG-03, PKG-04, PKG-05]

coverage:
  - id: D1
    description: "On the dev Mac one command builds nx2android-<version>-macos-arm64.dmg holding nx2android.app with the D-11 identity, ENGINE and nxnative/ (minus dmsh_xlate_bin/) in Contents/Resources, verifying with codesign --deep --strict"
    requirement: PKG-02
    verification:
      - kind: integration
        ref: ".venv/bin/python packaging/build_bundle.py && .venv/bin/python packaging/smoke_bundle.py dist/nx2android-*-macos-arm64.dmg"
        status: pass
      - kind: other
        ref: "PlistBuddy CFBundleIdentifier = io.github.namelesssaint8.nx2android; LSBackgroundOnly false; LSMinimumSystemVersion 14.0"
        status: pass
    human_judgment: false
  - id: D2
    description: "The frozen app answers doctor and profiles, starts its Window offscreen and lists 14 profiles from the read-only DMG mount, writes nothing into the bundle, and still verifies with codesign afterwards"
    requirement: PKG-05
    verification:
      - kind: integration
        ref: ".venv/bin/python packaging/smoke_bundle.py dist/nx2android-91755d9-dirty-macos-arm64.dmg (13 PASS lines)"
        status: pass
    human_judgment: false
  - id: D3
    description: "D-10 asset names, host-to-target mapping, dmsh_xlate_bin exclusion, engine id and the glibc floor parse/gate"
    requirement: PKG-03
    verification:
      - kind: unit
        ref: "tests/test_packaging.py (Names, Bundle, Glibc: 5 tests)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Windows zip and Linux x64/arm64 tar.gz built and smoked on their own hosts (Qt xcb/Wayland plugin presence, glibc floor)"
    requirement: PKG-04
    verification: []
    human_judgment: true
    rationale: "Only the macOS host is available here; the Windows and Linux builds run for the first time in plan 01-07/01-08 CI"
  - id: D5
    description: "A full port from the DMG-mounted app with real prod.keys and a game folder, codesign still passing, engine copy under ~/Library/Application Support (path with a space)"
    requirement: PKG-05
    verification: []
    human_judgment: true
    rationale: "Needs the developer's own keys and game dump (human-check of Task 3, recorded in docs/RELEASE_CHECK.md by plan 01-08)"
  - id: D6
    description: "Four-host INSTALL.md (Windows, macOS 14 Apple Silicon, Linux x64 glibc 2.34+, Linux arm64 glibc 2.39+), Linux libraries, Open log and per-OS log folders; README build lines"
    requirement: PKG-01
    verification: []
    human_judgment: true
    rationale: "Whether a tester can follow the guide without help is a reading judgment"

duration: 9min
completed: 2026-10-29
status: complete
---

# Phase 1 Plan 06: Four-host bundles Summary

**One build script for all four hosts: an ad-hoc or Developer ID-signed nx2android.app in a DMG on macOS (built and smoke-tested here from the read-only mount), a zip on Windows, tar.gz on Linux, plus a glibc floor gate and a read-only smoke test that starts the GUI offscreen**

## Performance

- **Duration:** about 9 min (two full PyInstaller builds of about 55 s each included)
- **Started:** 2026-10-29T08:56:03Z
- **Completed:** 2026-10-29T09:05Z
- **Tasks:** 3 of 3
- **Files modified:** 9

## Accomplishments
- `python packaging/build_bundle.py` on the dev Mac makes `dist/nx2android-<version>-macos-arm64.dmg` (102 MB): nx2android.app with bundle id `io.github.namelesssaint8.nx2android`, display name nx2android, a Dock icon, macOS 14 floor, five folder purpose strings, 1388 committed nxnative files plus `VERSION` and `ENGINE` (16 hex) in `Contents/Resources`. The outer bundle is re-signed after the copy and passes `codesign --verify --deep --strict`. The DMG holds the app, an Applications link and INSTALL.md. With `MACOS_SIGN_IDENTITY` set, every binary gets hardened runtime and timestamp, signing errors are fatal (`PYINSTALLER_STRICT_BUNDLE_CODESIGN_ERROR=1`) and the DMG is signed too.
- `packaging/smoke_bundle.py` mounts the DMG read-only (or makes a chmod a-w copy of a folder or .app). With a fresh NX2A_HOME it checks doctor and profiles, runs `smoke_gui.py` in the frozen app (lz4, capstone, PIL, yaml and zstd imports, a capstone AArch64 nop, an offscreen Window listing 14 profiles), confirms the file listing did not change and runs codesign again. All 13 checks pass on the dev Mac. On Linux it also requires the xcb, Wayland and xdg-shell Qt plugins.
- Windows keeps the zip under the D-10 name, and Linux writes `nx2android-<version>-linux-<arch>.tar.gz`. `packaging/glibc_floor.py <bundle> <floor>` prints the newest GLIBC_ version any ELF in the bundle needs and exits 1 above the floor.
- INSTALL.md now covers all four hosts, the Linux packages, the status line, Open log and where each OS keeps the logs. README has the per-host build lines, and ARCHITECTURE.md's Distribution entry is updated.

## Task Commits

1. **Task 1: macOS end to end (tracer)**: `8d8cad1` (feat). Tracer gate row 3 (interactive, end-of-phase, automated-only verify): after the version fix, the rebuild and smoke were run again and passed, so expansion went ahead
2. **Task 2: Windows zip, Linux tar.gz, glibc floor (TDD)**: RED `47d3afd` (test), GREEN `6d497c6` (feat), then `ff43d15` (test: keeps the gate's `[RED]` line out of the test output)
3. **Task 3: offscreen GUI start and the install guide (TDD)**: RED `91755d9` (test), GREEN `b16c88a` (feat)
4. **Docs:** `d9c6331` (docs: ARCHITECTURE.md Distribution)

## TDD Gate Compliance

- **Task 2 RED:** `NO_COLOR=1 python3 -m unittest tests.test_packaging -v` exited 1. The target `test_floor_parse` failed on its assertion `None != (2, 34)` against a `need()` skeleton that returns `{}` (the skeleton is the "make it compile" step, so the failure is an assertion, not an import error). `gsd-tools check tdd-red-evidence` returned `RED_EVIDENCE_OK` (format unittest, 5 tests, 1 fail). Semantic assessment: the target ran and failed on the planned floor assertion. Names and Bundle already passed because Task 1 implemented those helpers, as the plan says it should.
- **Task 2 GREEN:** 5/5 OK.
- **Task 3 RED:** an integration RED, which the classifier does not parse. smoke_bundle.py with the new step printed `[RED] offscreen GUI start (smoke_gui.py): exit 1` (the script did not exist yet) and exited 1.
- **Task 3 GREEN:** after a rebuild, all 13 checks pass, including `Window: 14 profiles`.

## Files Created/Modified
- `packaging/nx2android.spec`: BUNDLE on darwin with the D-11 identity and info_plist. `codesign_identity` comes from MACOS_SIGN_IDENTITY, with no entitlements.
- `packaging/build_bundle.py`: per-host layout and archive, the helper functions, ENGINE, outer re-sign, verify and DMG.
- `packaging/smoke_bundle.py`: read-only smoke of a DMG, .app or folder.
- `packaging/smoke_gui.py`: in-bundle check of the imports, capstone and the GUI.
- `packaging/glibc_floor.py`: glibc floor of a Linux bundle.
- `tests/test_packaging.py`: Names, Bundle and Glibc.
- `packaging/INSTALL.md`, `README.md`, `docs/ARCHITECTURE.md`: four-host docs.

## Decisions Made
- The bundle version is the numeric dotted prefix of the fork tag, and `0.0.0` for hash builds. Without the dot rule, a hash build gave `58` (from `58f5599`).
- The bootloader requirement and its import apply on Windows only.
- smoke_gui.py stays in the checkout. The frozen exe runs it as a script, as it does the engine's tools, so the bundle is not changed for the test.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] CFBundleShortVersionString came from a commit hash**
- **Found during:** Task 1 (first build)
- **Issue:** `re.match(r'\d+(\.\d+)*')` on `58f5599-dirty` gave `58`.
- **Fix:** the version now needs at least one dot (`\d+(\.\d+)+`), and falls back to `0.0.0`.
- **Files modified:** packaging/nx2android.spec
- **Verification:** the rebuilt Info.plist shows 0.0.0, and `0.1.2-ns.1` gives 0.1.2.
- **Committed in:** 8d8cad1

**2. [Rule 2 - Missing critical] Test output printed a `[RED] ` line**
- **Found during:** full suite after Task 3
- **Issue:** glibc_floor.main's "[RED] above 2.33" line showed up in the unittest output. CI and the GUI read `[RED] ` as a real failure.
- **Fix:** the test captures stdout and asserts the floor line.
- **Files modified:** tests/test_packaging.py
- **Committed in:** ff43d15

**3. [CLAUDE.md docs rule] ARCHITECTURE.md Distribution updated**
- The project rule keeps docs with a changed layer, so the bundle names, ENGINE and the new scripts are listed there. Committed in d9c6331.

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical) plus 1 docs addition required by CLAUDE.md
**Impact on plan:** none on scope.

## Issues Encountered
- `hdiutil create` prints a deprecation warning that points to `diskutil image create`. It still works on this macOS, and nothing else was changed for it.
- Local builds are signed ad hoc and have no hardened runtime, so RESEARCH Assumption A9 (capstone and ctypes need no entitlement) is not settled yet. smoke_gui.py checks it as soon as plan 01-08's signed build runs it.
- No `v*-ns.*` tag exists yet, so local asset names carry the commit hash (for example `nx2android-91755d9-dirty-macos-arm64.dmg`).

## Known Stubs
None.

## User Setup Required
None. Developer ID signing and notarization secrets belong to plan 01-08.

## Next Phase Readiness
- Plan 01-07/01-08 can call `build_bundle.py`, `smoke_bundle.py <archive>` and `glibc_floor.py dist/nx2android 2.34|2.39` on each runner.
- Not checked here: the Windows and Linux builds, the Linux Qt plugin check and the glibc values. The first CI run is where they get tested.
- Human-check left for end of phase: a full port from the mounted DMG with real keys and a game (Task 3 `<human-check>`).

## Self-Check: PASSED
- All 9 key files found on disk; commits 8d8cad1, 47d3afd, 6d497c6, 91755d9, b16c88a, ff43d15, d9c6331 are ancestors of HEAD.
- Acceptance greps: spec identity 1, LSBackgroundOnly 1, tracked('nxnative') 1, gztar 1, GLIBC_ 3, libqxcb 1, smoke_gui 3, INSTALL macOS 4 / Linux 5 / Open log 1, README requirements-build.txt 1.
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover tests`: OK (skipped=1); `tests/arch_rules.py`: all checks passed.

---
*Phase: 01-bridge-bundles-and-ci*
*Completed: 2026-10-29*
