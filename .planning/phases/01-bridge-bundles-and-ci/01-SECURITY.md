---
phase: "01"
slug: "bridge-bundles-and-ci"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-10-29"
---

# Phase 01 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| PyPI → developer machine | Package archives downloaded by uv (resolution) and pip (install) | third-party code |
| Lock file → every install (dev, CI, release) | The hashes in the lock decide what any later install accepts | package integrity |
| GUI process → porter stdin | The stop line and EOF arrive here; only the parent holds the pipe | control signal |
| porter → `<user dir>/logs` | Run logs testers attach to public GitHub issues | local paths, argv (no key material) |
| porter → build folder | Orphaned children or a cut-off stage can leave outputs the cache trusts | build outputs |
| porter stdout/stderr → GUI widgets | Error text, paths and game names are rendered in Qt labels, some rich text | untrusted text |
| GUI → OS process control | killpg / TerminateJobObject / taskkill act on process ids the GUI holds | process ids |
| GUI → system URL handler | Open log hands a path to QDesktopServices | local file path |
| repository → public GitHub | Committed fixtures are public | recorded event streams |
| Signed, notarized bundle → runtime writes | Any write inside the .app breaks its seal and Gatekeeper's verdict | code signature |
| Bundle resources → per-user engine copy | The copy is what the port executes from | engine source |
| Developer checkout → public bundle | Whatever build_bundle copies ships to testers | shipped files |
| Signing identity → binaries | Developer ID signatures vouch for every Mach-O in the app | code signature |
| Pull requests from forks → CI runners | Untrusted code runs in fork-ci jobs | untrusted code, GITHUB_TOKEN |
| Third-party actions → CI jobs | Action code runs with the job's token | GITHUB_TOKEN |
| GitHub environment `release` → macOS job | Developer ID private key and App Store Connect key enter a runner | signing secrets (high) |
| Release job → public GitHub Release | Assets testers download | release assets |
| Tags pushed to the fork → workflow trigger | Who can start a signing run | release trigger |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-1-SC (01-01) | Tampering | pip/uv installs of the lock | high | mitigate | Every entry of requirements.txt, requirements-build.txt, requirements-dev.txt carries `--hash=sha256` (`uv pip compile --universal --generate-hashes`); CI installs `--require-hashes` (fork-ci.yml:50); Lock.test_every_entry_is_hashed, test_generated_by_uv | closed |
| T-1-01 | Tampering | requirements*.in index config | medium | mitigate | No index-url, extra-index, find-links or trusted-host in any requirements file; no pip.conf, uv.toml or pyproject.toml tracked | closed |
| T-1-02 | Information disclosure | porter/runlog.py log contents | high | mitigate | The log writes only argv, version and stage lines (runlog.py:79-84); RunLogInProcess.test_no_key_material | closed |
| T-1-03 | Denial of service | procs._watch stdin stop channel | low | accept | See AR-01 | closed |
| T-1-04 | Denial of service | procs._watch killpg on POSIX | medium | mitigate | Watcher only under NX2A_GUI=1 (procs.py:16), set by gui/runner.py:21 with a new session (:31); Stop.test_cli_without_gui_has_no_watcher | closed |
| T-1-05 | Tampering | build folder cache after cancel/kill | medium | mitigate | Windows Job Object with KILL_ON_JOB_CLOSE (procs.py:48-67, 83); POSIX session (runner.py:31); `.port-running` cut-off marker (runlog.py:42-62, pipeline.py:150); translator cache swap-in (pipeline.py:319-323); Marker.*, Stop.test_grandchild_dies | closed |
| T-1-06 | Information disclosure | `{"error"}` text and tracebacks with local paths | low | accept | See AR-02 | closed |
| T-1-07 | Denial of service | unbounded run logs | low | mitigate | `LOGS_KEPT = 30`, pruned on every open (runlog.py:11, 65-76); Retention.test_keeps_newest_30 | closed |
| T-1-SC (01-02) | Tampering | package installs | low | accept | See AR-03 | closed |
| T-1-08 | Spoofing | PortTab.step / SetupTab.dl_step | medium | mitigate | Plain-text labels during runs (app.py:97, 307); `&` and `<` escaped before the Open log link (app.py:326-329); Close.test_download_failure_inline | closed |
| T-1-09 | Denial of service | killpg on a stale or reused group | low | mitigate | `_kill` only for pgid > 1, `_force` stops once the run ended, ProcessLookupError ends the reap (runner.py:35-37, 64-67, 80, 108-114); Stop.test_stop_kills_tree_keeps_detached, test_stop_after_exit_is_noop | closed |
| T-1-11 | Tampering | QDesktopServices.openUrl for Open log | low | mitigate | Only `QUrl.fromLocalFile` is opened (app.py:250, 253, 334); link handlers never open the href | closed |
| T-1-SC (01-03) | Tampering | package installs | low | accept | See AR-04 | closed |
| T-1-12 | Spoofing | `failed(fail)` HTML in rich-text labels | medium | mitigate | `html.escape` on the cause and stderr tail before the Retry link (app.py:38-41), used by every rich-text failure path (:127, 299, 354, 385); Errors.test_doctor_crash_shows_stderr, test_undecodable_stderr | closed |
| T-1-13 | Denial of service | hung one-shot porter processes | low | mitigate | Per-call TIMEOUTS with a timer that kills the tree (runner.py:16, 117-132); Timeout.test_kills_tree_at_limit | closed |
| T-1-10 | Information disclosure | committed golden fixtures | medium | mitigate | record.py scrubs `<folder>`, `<home>`, `<user>` (tests/fixtures/bridge/record.py:56-66); Replay.test_fixtures_are_scrubbed; no home or temp paths in the fixtures | closed |
| T-1-SC (01-04) | Tampering | package installs | low | accept | See AR-05 | closed |
| T-1-14 | Tampering | writes into the signed bundle | high | mitigate | Frozen NXNATIVE is the user-folder copy (paths.py:24-49); bytecode off (packaging/nx2android.py:9); listing and `codesign --verify --deep --strict` checked by smoke_bundle.py (:59, 71-76) and passed in fork-release run 40940461343; Launcher.test_no_bytecode_flag, Engine.test_macos_layout, test_plain_layout | closed |
| T-1-15 | Tampering | user-folder engine copy edited by the same user | low | accept | See AR-06 | closed |
| T-1-16 | Tampering | half-made engine copy, racing process | medium | mitigate | Copy to `<id>.tmp-<pid>`, one rename, loser removes its temp (paths.py:32-40); Engine.test_concurrent_first_start | closed |
| T-1-SC (01-05) | Tampering | package installs | low | accept | See AR-07 | closed |
| T-1-17 | Information disclosure | build_bundle.py file selection | high | mitigate | Files come from `git ls-files`, dmsh_xlate_bin skipped (build_bundle.py:17-21, 39-40, 64-66); arch rules 8, 9, 10b; Bundle.test_dmsh_xlate_bin_excluded | closed |
| T-1-18 | Spoofing | unsigned or ad-hoc macOS builds | medium | mitigate | Local builds are ad hoc (build_bundle.py:75); strict codesign errors with an identity (:59); the distributable is signed and notarized only in fork-release.yml:110-129 | closed |
| T-1-19 | Information disclosure | MACOS_SIGN_IDENTITY in build output | low | accept | See AR-08 | closed |
| T-1-SC (01-06) | Tampering | PyInstaller and bootloader | high | mitigate | `pyinstaller==6.22.3` hashed in requirements-build.txt:23; build_bootloader.py:32-36 refuses an sdist whose sha256 differs from PyPI's; fork-release.yml:50, 53 | closed |
| T-1-20 | Elevation of privilege | fork-ci triggers and token scope | high | mitigate | push, pull_request, workflow_dispatch only, no pull_request_target, `contents: read`, persist-credentials false (fork-ci.yml:6-12, 40); Ci.test_no_privileged_pr_trigger, test_ci_matrix | closed |
| T-1-21 | Tampering | re-pointed action tags | high | mitigate | All 10 `uses:` pinned to 40-hex SHAs that resolve upstream; Ci.test_actions_pinned | closed |
| T-1-22 | Elevation of privilege | expression injection into run scripts | medium | mitigate | No `${{` inside any `run:` script; values pass through `env:`; Ci.test_run_scripts_take_no_expressions | closed |
| T-1-SC (01-07) | Tampering | pip installs on runners | high | mitigate | `pip install --require-hashes -r requirements.txt` (fork-ci.yml:50) | closed |
| T-1-23 | Information disclosure | signing secrets | high | mitigate | `environment: release` (fork-release.yml:84) with deployment rules `main` and `v*-ns.*`; secrets only in macOS step `env:`; decoded files in RUNNER_TEMP, removed, plus an always() cleanup (:101-128, 155-159); no PR trigger; no repo-level secrets; Release.test_secrets_scoped | closed |
| T-1-24 | Tampering | release triggered by upstream tags | medium | mitigate | Tag trigger `v*-ns.*` only (fork-release.yml:7-10); `remote.upstream.tagOpt=--no-tags`; Release.test_triggers | closed |
| T-1-25 | Tampering | draft with missing or wrong assets | medium | mitigate | Release job needs every build, is tag-only, checks the four names and four files, then drafts (fork-release.yml:175-202); Release.test_release_checks_four_assets. Not yet exercised live: no `v*-ns.*` tag exists | closed |
| T-1-26 | Spoofing | DMG shipped without notarization | high | mitigate | notarytool `--wait` must return Accepted, then staple, `stapler validate`, `spctl`, and the smoke re-checks codesign (fork-release.yml:123-147, smoke_bundle.py:74-76); Release.test_macos_signs_and_notarizes; live: Accepted, "Notarized Developer ID" | closed |
| T-1-27 | Elevation of privilege | GITHUB_TOKEN write scope | medium | mitigate | Top-level `contents: read`; `contents: write` only in the tag-gated release job (fork-release.yml:12-13, 177-181); Release.test_write_scope | closed |
| T-1-SC (01-08) | Tampering | pip installs in release builds | high | mitigate | `--require-hashes -r requirements.txt -r requirements-build.txt` (fork-release.yml:50, 94); actions SHA-pinned as in T-1-21 | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-01 | T-1-03 | Only the parent GUI holds porter's stdin pipe; the watcher runs only under NX2A_GUI=1 | plan 01-02 threat model | 2026-10-29 |
| AR-02 | T-1-06 | Error text with local paths is shown only in the local GUI and the local log the user chooses to share | plan 01-02 threat model | 2026-10-29 |
| AR-03 | T-1-SC (01-02) | This plan installs nothing; the 01-01 lock governs `.venv` | plan 01-02 threat model | 2026-10-29 |
| AR-04 | T-1-SC (01-03) | No installs in this plan; `.venv` comes from the 01-01 lock | plan 01-03 threat model | 2026-10-29 |
| AR-05 | T-1-SC (01-04) | No installs in this plan | plan 01-04 threat model | 2026-10-29 |
| AR-06 | T-1-15 | Same-user trust boundary; a new bundle version gets a fresh copy under a new id | plan 01-05 threat model | 2026-10-29 |
| AR-07 | T-1-SC (01-05) | Standard library only; no installs in this plan | plan 01-05 threat model | 2026-10-29 |
| AR-08 | T-1-19 | The identity name is public in every signature; no secret value passes through build_bundle | plan 01-06 threat model | 2026-10-29 |

*Accepted risks do not resurface in future audit runs.*

---

## Notes Outside the Register (non-blocking)

Found by the auditor while verifying; not counted in threats_open.

1. **Inspect card renders porter text as rich text unescaped.** `gui/app.py:131-136` (`on_inspect` success path) puts `name`, `reason`, `tested` and `pack` into the RichText card without `html.escape`, and `:121` does the same with the typed path. Older code (0cfbb40), outside T-1-12's component. Impact is limited to mis-rendering: the card's link handler only calls `inspect()`.
2. **`docs/images` is copied without the git-tracked filter.** `packaging/build_bundle.py:69` uses `copytree`, so a local build could ship untracked files from that folder. CI bundles come from a clean checkout and are unaffected.
3. **The dev lock was not reviewed by a person.** `requirements-dev.txt` is hashed but was outside plan 01-01's Task 2 review. Nothing in this phase installs it in CI or the bundles.
4. **GUI tests skip on the Python 3.11 CI row.** `tests/test_bridge.py` (the GUI side of T-1-08/09/10/11/12/13) skips below 3.12 by the plan 01-07 decision; it runs on the four 3.14 CI rows and locally.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-10-29 | 35 | 35 | 0 | gsd-security-auditor (secure-phase, ASVS 1, block_on high) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-10-29
