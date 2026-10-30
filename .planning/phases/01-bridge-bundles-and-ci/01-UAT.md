---
status: diagnosed
phase: 01-bridge-bundles-and-ci
source: [01-VERIFICATION.md]
started: 2026-10-29T21:00:00Z
updated: 2026-10-30T05:29:04Z
---

## Current Test

[testing complete]

## Tests

### 1. Windows x64 zip on a PC with no Python (PKG-01)
On a Windows x64 PC with no Python installed, unzip nx2android-d2ec054-windows-x64.zip (fork-release run 40971470754 artifact, built with the review fixes) and double-click nx2android.exe. Watch the first start: it copies about 150 MB of engine files while Defender scans them (review WR-03).
expected: The window opens with Port, Setup and Games tabs, the Games tab lists the profiles, and the console window is hidden
result: pass

### 2. Notarized DMG downloaded in a browser (PKG-02)
On a macOS 14+ Apple Silicon Mac, download the DMG in a browser (so it carries the quarantine flag), open it from Finder, drag nx2android.app to Applications and start it.
expected: No Gatekeeper warning; the app starts with a Dock icon
result: pass

### 3. Linux x64 and arm64 under X11 and Wayland (PKG-03, PKG-04)
On Linux x64 (glibc 2.35+) and on Linux arm64 (glibc 2.39+), unpack the tarball and start ./nx2android once with QT_QPA_PLATFORM=xcb and once with QT_QPA_PLATFORM=wayland.
expected: The window appears under both, with no Fontconfig or platform-plugin errors
result: pass
note: "Shown on Linux x64 (Debian-family host plex): X11 directly, Wayland in a nested weston session (no Wayland login session there). The arm64 tarball was not shown in this session. Under weston, Download missing tools fetched the NDK, so test 6's TLS failure does not reproduce on this Linux host."

### 4. Full port from the mounted DMG (PKG-05)
On the Mac, mount the DMG, start /Volumes/nx2android/nx2android.app from the mount, port a playable title with your own prod.keys, then run codesign --verify --deep --strict --verbose=2 /Volumes/nx2android/nx2android.app.
expected: The port succeeds, the engine copy is under ~/Library/Application Support/nx2android/engine/, and codesign still passes
result: pass

### 5. Real cancel mid-port on each host (BRDG-01)
On each host, start a real port from the GUI, press Cancel during the shader or host stage, then list processes (ps -ef | grep -E 'dotnet|clang|MSBuild|shader', or Task Manager on Windows) and run adb devices.
expected: The status shows 'stopping…' then 'cancelled'; no dotnet, MSBuild, clang or shader-tool process is left; adb devices still lists the device and does not restart the server
result: pass

### 6. Download missing tools from the signed macOS app
Found during test 2: on the Setup tab of the d2ec054 DMG build, press Download missing tools.
expected: The download lists load and the missing tools (here the Android NDK) download into the nx2android folder
result: issue
reported: "test passes, but there's an issue downloading the rools" (screenshot: porter failed — cannot read the download lists: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1085)>)
severity: major

### 7. Linux bundle starts without GLib module errors
Found during test 3: the x64 tarball started with QT_QPA_PLATFORM=xcb on a Debian-family host with a newer GLib than the bundle's.
expected: No GLib or GIO module errors at start-up
result: issue
reported: "/usr/lib/x86_64-linux-gnu/gvfs/libgvfscommon.so: undefined symbol: g_task_set_static_name / Failed to load module: /usr/lib/x86_64-linux-gnu/gio/modules/libgvfsdbus.so" (from the user's pasted start-up log; the window still opened)
severity: minor

## Summary

total: 7
passed: 5
issues: 2
pending: 0
skipped: 0
blocked: 0

## Gaps

- gap_id: G-01-6
  truth: "Download missing tools loads the download lists and fetches the missing tools from the signed macOS app"
  status: failed
  reason: "User reported: test passes, but there's an issue downloading the rools (CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate)"
  severity: major
  test: 6
  root_cause: "The bundle freezes CI's Python with its own OpenSSL, whose CA location is compiled in as a build-machine path (macOS: /Library/Frameworks/Python.framework/Versions/3.14/etc/openssl, the python.org framework from actions/setup-python, never populated and never reading the keychain; Linux: /usr/lib/ssl from Ubuntu). porter's HTTPS calls pass no SSL context, so on a player's Mac (and on Fedora/RHEL/Arch/openSUSE) 0 CA certificates load and every request fails with CERTIFICATE_VERIFY_FAILED. Reproduced from the signed app; the same app with SSL_CERT_FILE=/etc/ssl/cert.pem loads 128 CAs and reaches dl.google.com, so signing, entitlements and network are not involved. Windows is unaffected (load_default_certs reads the system stores). Side effect: --fps60 catches the URLError and silently keeps the game's own frame rate on those hosts."
  artifacts:
    - path: "porter/fetch.py"
      issue: "_get, the HEAD request in plan, and _download call urllib.request.urlopen with no SSL context"
    - path: "porter/fpslocker.py"
      issue: "fetch() calls urlopen with no SSL context (the --fps60 config download)"
    - path: ".github/workflows/fork-release.yml"
      issue: "explains the cause (macOS job uses the python.org framework Python via actions/setup-python); not the place for the fix"
  missing:
    - "One SSL context built in porter (not the GUI) and passed as context= to every urlopen call in porter/fetch.py and porter/fpslocker.py, trusting the OS store on macOS and Windows and a CA file that exists on the host on Linux when OpenSSL's compiled-in location is empty"
    - "No process-wide SSL_CERT_FILE: children inherit it and .NET on Linux honours it (NuGet restore in the translator build)"
    - "A unit test for the context selection, and a check of downloads from the notarized DMG and from the Linux bundle in a Fedora container before closing"
  debug_session: ".planning/debug/macos-bundle-tls-cert-verify.md"

- gap_id: G-01-7
  truth: "The Linux bundle starts without GLib or GIO module errors on a host whose GLib is newer than the bundle's"
  status: failed
  reason: "Observed in the user's pasted log: the host's gvfs GIO module (built for a newer GLib) fails to load into the bundled GLib: undefined symbol g_task_set_static_name"
  severity: minor
  test: 7
  root_cause: "PyInstaller traces PySide6's gtk3 platform theme (PySide6/Qt/plugins/platformthemes/libqgtk3.so) and copies the build runner's whole GLib/GIO/GTK3 stack into _internal (GLib 2.72.4 in x64 from ubuntu-22.04, 2.80.0 in arm64 from ubuntu-24.04-arm). On a GTK-family desktop (XDG_CURRENT_DESKTOP GNOME, Unity, Cinnamon, MATE, XFCE...) Qt loads that theme under xcb and wayland alike; gtk_init makes the bundled libgio scan its compiled-in module dir /usr/lib/<triplet>/gio/modules, which on Debian-family hosts is the host's own, and the host gvfs (BIND_NOW) needs symbols the older bundled GLib lacks (g_task_set_static_name on x64; g_variant_builder_init_static for arm64 on GLib 2.84 hosts). Reproduced exactly in a Debian trixie container. Effect: start-up noise, and the GTK file chooser opens without gvfs (no Trash, network locations or unmounted drives). The qt.qpa.theme.gnome portal line is host-side and stays regardless. CI misses it because the smoke test runs QT_QPA_PLATFORM=offscreen on the build runner with no desktop name."
  artifacts:
    - path: "packaging/nx2android.spec"
      issue: "no Linux filtering of collected binaries: platformthemes/libqgtk3.so pulls in the runner's GTK3/GLib/GIO (26 libs, 15.4 MiB); networkinformation/libqglib.so is collected but unused"
    - path: ".github/workflows/fork-release.yml"
      issue: "the Linux smoke test (offscreen, on the build runner) cannot see a host-vs-bundle GLib mismatch"
  missing:
    - "The Linux bundles stop shipping the runner's GTK3/GLib/GIO stack (e.g. leave platformthemes/libqgtk3.so and the unused networkinformation/libqglib.so out on Linux), so GIO is never initialised from bundled copies and nothing new leaks into child processes"
    - "A build-time check that fails when a Linux bundle contains libgio-2.0 or libgtk-3, so the stack cannot come back unnoticed"
    - "A check of the x64 and arm64 tarballs in a Debian trixie container with XDG_CURRENT_DESKTOP=GNOME showing a clean start and a working folder picker"
  debug_session: ".planning/debug/linux-bundle-gio-module-mismatch.md"
