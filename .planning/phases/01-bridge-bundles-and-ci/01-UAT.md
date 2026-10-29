---
status: testing
phase: 01-bridge-bundles-and-ci
source: [01-VERIFICATION.md]
started: 2026-10-29T21:00:00Z
updated: 2026-10-29T21:00:00Z
---

## Current Test

number: 1
name: Windows x64 zip on a PC with no Python (PKG-01)
expected: |
  The window opens with Port, Setup and Games tabs, the Games tab lists the profiles, and the console window is hidden
awaiting: user response

## Tests

### 1. Windows x64 zip on a PC with no Python (PKG-01)
On a Windows x64 PC with no Python installed, unzip nx2android-<ver>-windows-x64.zip (fork-release run 40940461343 artifact) and double-click nx2android.exe. Watch the first start: it copies about 150 MB of engine files while Defender scans them (review WR-03).
expected: The window opens with Port, Setup and Games tabs, the Games tab lists the profiles, and the console window is hidden
result: [pending]

### 2. Notarized DMG downloaded in a browser (PKG-02)
On a macOS 14+ Apple Silicon Mac, download the DMG in a browser (so it carries the quarantine flag), open it from Finder, drag nx2android.app to Applications and start it.
expected: No Gatekeeper warning; the app starts with a Dock icon
result: [pending]

### 3. Linux x64 and arm64 under X11 and Wayland (PKG-03, PKG-04)
On Linux x64 (glibc 2.35+) and on Linux arm64 (glibc 2.39+), unpack the tarball and start ./nx2android once with QT_QPA_PLATFORM=xcb and once with QT_QPA_PLATFORM=wayland.
expected: The window appears under both, with no Fontconfig or platform-plugin errors
result: [pending]

### 4. Full port from the mounted DMG (PKG-05)
On the Mac, mount the DMG, start /Volumes/nx2android/nx2android.app from the mount, port a playable title with your own prod.keys, then run codesign --verify --deep --strict --verbose=2 /Volumes/nx2android/nx2android.app.
expected: The port succeeds, the engine copy is under ~/Library/Application Support/nx2android/engine/, and codesign still passes
result: [pending]

### 5. Real cancel mid-port on each host (BRDG-01)
On each host, start a real port from the GUI, press Cancel during the shader or host stage, then list processes (ps -ef | grep -E 'dotnet|clang|MSBuild|shader', or Task Manager on Windows) and run adb devices.
expected: The status shows 'stopping…' then 'cancelled'; no dotnet, MSBuild, clang or shader-tool process is left; adb devices still lists the device and does not restart the server
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
