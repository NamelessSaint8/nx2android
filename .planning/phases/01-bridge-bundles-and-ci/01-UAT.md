---
status: complete
phase: 01-bridge-bundles-and-ci
source: [01-VERIFICATION.md]
started: 2026-10-29T21:00:00Z
updated: 2026-10-30T04:48:58.855Z
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
  artifacts: []  # Filled by diagnosis
  missing: []    # Filled by diagnosis

- gap_id: G-01-7
  truth: "The Linux bundle starts without GLib or GIO module errors on a host whose GLib is newer than the bundle's"
  status: failed
  reason: "Observed in the user's pasted log: the host's gvfs GIO module (built for a newer GLib) fails to load into the bundled GLib: undefined symbol g_task_set_static_name"
  severity: minor
  test: 7
  artifacts: []  # Filled by diagnosis
  missing: []    # Filled by diagnosis
