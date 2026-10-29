---
last_mapped_commit: 9d67edec2175ae5f4beadbd65f37eaa88105d132
last_mapped_at: 2026-10-29
---
# External Integrations

**Analysis Date:** 2026-10-29

nx2android has no server, database, user accounts or webhooks. Its external contacts are a short list of HTTP downloads made by the desktop tool, the USB/adb link to the player's device, and the player's own local files. Every outbound request is a plain `urllib.request` call with `User-Agent: nx2android`.

## APIs & External Services

**Android toolchain downloads (Google SDK repository):**
- Service: Google's Android SDK package repository, used to fetch the Android NDK r27c and platform-tools.
- Code: `porter/fetch.py` (`GOOGLE = 'https://dl.google.com/android/repository/'`, `GOOGLE_INDEX = .../repository2-3.xml`). The index is parsed with `xml.etree.ElementTree`, and the archive matching the host OS is chosen (`_google_os()`: `windows`, `macosx`, `linux`).
- Request: `GET` on the index, `GET` on the archive, `HEAD` for size when the index gives none.
- Integrity: each archive is checked against the SHA-1 (`checksum type` in the index) by `_download()` in `porter/fetch.py`; a mismatch deletes the file.
- Triggered by: the GUI's Setup tab button "Download missing tools" or `python -m porter tools --download`.
- Auth: none.
- Licenses shown to the player: `https://developer.android.com/studio/terms` (`porter/fetch.py` `LICENSES`).

**.NET SDK downloads (Microsoft):**
- Service: Microsoft's .NET release metadata, `https://builds.dotnet.microsoft.com/dotnet/release-metadata/10.0/releases.json`.
- Code: `porter/fetch.py` `DOTNET_INDEX`, `_dotnet()`. Picks the newest SDK 10 file for the player's RID (`win-x64`, `osx-arm64`, `linux-x64`, ...).
- Integrity: SHA-512 from the release JSON (`algo='sha512'`).
- License link: `https://github.com/dotnet/core/blob/main/license-information.md`.
- Auth: none.

**FPSLocker community configs (masagrator / SaltySD):**
- Service: GitHub raw content, `https://raw.githubusercontent.com/masagrator/FPSLocker-Warehouse/v4/SaltySD/plugins/FPSLocker/patches/{tid}/{bid}.yaml`.
- Code: `porter/fpslocker.py` (`RAW`, `url()`, fetch with `urllib.request.urlopen`, decoded as `utf-8-sig`). Parsed with `pyyaml`.
- Used only when the player passes `--fps60` to a port. One file is fetched per game build at port time.
- Constraints documented in the code: the warehouse has no license, so configs are fetched per port and never committed or redistributed.
- Auth: none. Failure to fetch leaves the game at its own frame rate.

**Python package index (build time only):**
- Service: PyPI JSON API, `https://pypi.org/pypi/pyinstaller/{ver}/json`, and the PyInstaller sdist it names.
- Code: `packaging/build_bootloader.py`. Downloads the sdist and checks its SHA-256 against PyPI's `digests` before building the bootloader.
- Not run by the player; only by a developer building the bundle on Windows.

**Upstream project and GitHub:**
- `https://github.com/seedds/nxnative` - upstream of the vendored engine. Pulled by a developer with `git subtree pull --prefix nxnative https://github.com/seedds/nxnative.git main --squash` (README.md, `docs/ARCHITECTURE.md`). Not called by the tool at run time.
- `https://github.com/shirai91/nx2android/releases/latest` - where the Windows player bundle (`nx2android-<version>-windows-x64.zip`) is published, per README.md. Manual download; the tool does not check for updates.

**Not present:** no analytics, crash reporting, telemetry, update checks, payment, or AI/LLM API calls were found in the code (`grep` for `urlopen`, `requests`, `socket`, `connect(` across `porter/`, `gui/`, `devtools/`, `packaging/` returns only the calls listed above).

## Data Storage

**Databases:**
- Not applicable. No database client or ORM is used.

**Local file storage (the player's machine):**
- Player settings: `<user dir>/config.json`, written by `porter/config.py` (keys: `keys`, `ndk`, `dotnet`, `adb`, `out`, `device`, `language`).
- User dir: `%APPDATA%\nx2android` (Windows), `~/Library/Application Support/nx2android` (macOS), `$XDG_CONFIG_HOME` or `~/.config/nx2android` (others); override with `NX2A_HOME` (`porter/paths.py`).
- Toolchains: `<user dir>/toolchains/` (`player_tools()`), where the downloads are unpacked.
- Translator build: `<user dir>/tools/dmsh_xlate/` (`porter/pipeline.py`).
- Game inputs and outputs: the game folder the player picks (NSP/XCI, update and DLC), with build output in `<game folder>/<title ID>_build/` (`docs/ARCHITECTURE.md`). `.gamedump/` is the gitignored working area for the NSP script.

**On-device storage (Android):**
- The app's external files folder: `/sdcard/Android/data/<package>/files` (`nxnative/dm/android/front_android.c`, `porter/datapack.py`). Holds `mods/`, `RomFS/`, `aoc/`, `shaders.dmsv`, `env.txt`, `settings.txt`, `nx2a-data.json`, `log.txt`, and saves. Falls back to the internal data path when no external path is given.
- Captured shaders are written by the app to `captured_shaders/<key>.bin` in that folder and pulled back by `porter/install.py` (see `docs/ARCHITECTURE.md`).

**File storage (cloud):**
- None. Nothing is uploaded; game files never leave the player's machine.

**Caching:**
- Local only: the port's stage outputs are keyed by a fingerprint of their inputs (`porter/pipeline.py`, `nsp.fingerprint(...)`) and reused on later runs. No external cache service.

## Device Link (USB / adb)

**Android device over adb:**
- Tool: `adb` from Android platform-tools, located by `porter/toolchain.py` `find_adb()` (configured path, `PATH`, Android SDK folders, the player's toolchains).
- Code: `porter/adb.py` (`Adb` class: `devices -l`, `install`, `push`, `shell`, `wait-for-device` retries), `porter/install.py` (install flow), `devtools/device.py` (dev tools).
- Operations: list devices, read device properties (`ro.product.model`, GPU), check BC texture support, install the APK (`adb install -r`, with `replace_signer` uninstall path), push the data pack in chunks, remove stale files, start the app once so Android creates its files folder.
- Transport: USB or Wi-Fi ADB (`devtools/device.json` example uses `192.168.1.20:5555`). Selected by serial from `config.json` `device`, `NX2A_DEVICE`, or the only connected device.
- Auth: the device's own ADB authorization (USB debugging prompt). No credentials are stored by the tool.
- Constraints: `porter/adb.py` notes that large pushes can wedge `adbd`; pushes are short transfers with `-Z` (no compression).

**Vulkan / Android system services used by the app (on device, not network):**
- Vulkan loader `libvulkan.so`, AAudio, MediaCodec (`libmediandk`), `ANativeWindow`, Vibrator (haptics via `nxnative/dm/android/haptics_android.c`), performance hints (`perf_android.c`).
- The app requests `android.permission.VIBRATE` only (`nxnative/dm/android/apk/mkapk.py`).

## Game Services (emulated, not contacted)

The games' own network services are emulated as unavailable. The host has no socket or outbound connection in the Android runtime (`nxnative/dm/host/hle_net.c`, `hle_offline.c`, `hle_account.c`). Specifically:
- `nn::socket` and `nn::nifm` report success or "no network" and create no session (`hle_net.c`).
- Online accounts, friends, telemetry and SSL-backed services return failure so the game takes its offline branch (`hle_offline.c`, `hle_account.c`).
- A local user named `Player` is used; the nickname is set with `DM_NICK`.

## Authentication & Identity

- None for the tool itself. No user accounts.
- Code signing: each port's APK is signed by `nxnative/dm/android/apk/mkapk.py` with a per-player key stored at `<user dir>/signing-key.json` (`porter/paths.py` `signing_key()`); created on first use and reused so updates install over earlier ports. Gitignored (`*-signing-key.json`).
- Switch keys: the player's own `prod.keys` (path stored as `keys` in `config.json`). The tool reads it locally; it is never copied into the repository or the app. `.gitignore` excludes `prod.keys` and `title.keys`.

## Monitoring & Observability

**Error tracking:** None. No external service.

**Logs:**
- Desktop: stdout/stderr of the port process; `--progress json` emits one JSON object per line for the GUI (`docs/ARCHITECTURE.md`). Logs are written under the build folder (`self.logs`, e.g. `android_translator_build.log`).
- Device: `log.txt` in the app's files folder (`docs/ARCHITECTURE.md`). Vulkan validation messages go there when `DM_VK_VALIDATE=1` (`nxnative/dm/android/gfx_vk_core.c`).
- Debug build: `DM_CTL` control interface in the development build (`build.py --debug`); ignored in release builds (`DM_RELEASE`).

## CI/CD & Deployment

**Hosting:**
- Not applicable. No deployed service.
- Distribution: GitHub Releases (manual) of the Windows bundle; the bundle is built locally with `python packaging/build_bundle.py` (`packaging/build_bundle.py`, `packaging/nx2android.spec`).

**CI Pipeline:**
- None detected. No `.github/workflows`, `.gitlab-ci.yml` or similar in the repository. Checks are local: `python -m unittest discover tests`, the commit-msg hook (`.githooks/commit-msg`, enabled with `git config core.hooksPath .githooks`), and the device checks in `devtools/`.

**Release check:**
- `devtools/port_check.py` records the bundle version (`VERSION` written by `packaging/build_bundle.py` from `git describe`) against the games that were checked (`docs/RELEASE_CHECK.md`).

## Environment Configuration

**Required environment (player, via the GUI or `config.json`):**
- Path to `prod.keys` (required for any port).
- Android NDK r27c folder (or `ANDROID_NDK_HOME`).
- .NET SDK 10 (`dotnet` path, or `DOTNET_ROOT`).
- adb path (only to install on a device).
- Optional: output folder (`out`), device serial (`device`), game language (`language`).

**Required environment (developer):**
- Same as above, plus Python 3.11+ with `requirements.txt`.
- `NX2A_GAME`, `NX2A_PACKAGE`, `NX2A_DEVICE` for the dev tools (`devtools/device.py`), or `devtools/device.json` (gitignored).
- `DM_ROOT` for the shader chain's work directory (defaults to `~/dm-work`, `nxnative/dm/gfx/tools/dmsh_chain.py`).

**Secrets location:**
- `prod.keys` and `title.keys`: the player's own files, located by path. Never committed (`.gitignore`).
- APK signing key: `<user dir>/signing-key.json`. Gitignored by pattern `*-signing-key.json`; the `tools/` folder in the repository (developer toolchains) is also gitignored.
- No `.env` file is read by the code. `.env` files were not read for this analysis.

## Webhooks & Callbacks

**Incoming:**
- None. The tool does not listen on any port. The GUI and CLI are local processes; the Android app exposes no network endpoint.

**Outgoing:**
- None at run time beyond the downloads listed above (Google SDK repository, Microsoft .NET metadata, GitHub raw for FPSLocker configs). Build-time only: PyPI (`packaging/build_bootloader.py`).

## Legal / Licensing Touchpoints

- The tool never ships or downloads Nintendo files, `prod.keys` or game content (README.md). The player supplies them.
- Third-party code is vendored under `nxnative/dm/third_party/` with license files (`nxnative/dm/third_party/README.md`); the Android toolchains are downloaded under their makers' terms (`porter/fetch.py` `LICENSES`).
- The FPSLocker-Warehouse configs are fetched per port and not redistributed (`porter/fpslocker.py`).

---

*Integration audit: 2026-10-29*
