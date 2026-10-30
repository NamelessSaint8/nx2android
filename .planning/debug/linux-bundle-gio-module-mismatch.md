---
status: diagnosed
trigger: "linux-bundle-gio-module-mismatch: The Linux bundle starts without GLib or GIO module errors on a host whose GLib is newer than the bundle's"
created: 2026-10-30T06:00:00Z
updated: 2026-10-30T07:35:00Z
---

## Current Focus

hypothesis: CONFIRMED (H1). Root cause is packaging: PyInstaller collects the build runner's GLib/GIO/GTK3 stack as dependencies of
  PySide6's gtk3 platform theme plugin; on a GTK-family desktop Qt loads that plugin, gtk_init makes the bundled GIO scan its compiled-in
  Debian-multiarch module dir, and the host's gvfs modules (built for a newer GLib, BIND_NOW) fail to bind.
test: done - reproduced byte-for-byte on the x64 UAT artifact and on arm64, with a 6-case differential matrix
expecting: n/a
next_action: return ROOT CAUSE FOUND to the orchestrator (goal find_root_cause_only); no source changes
bug_class: Bohrbug (deterministic: host GLib version x distro module path x desktop name)
reasoning_checkpoint:
  hypothesis: "The bundled GLib 2.72 (x64) / 2.80 (arm64), collected by PyInstaller with libqgtk3.so, loads the host's gvfs GIO modules from
    /usr/lib/<triplet>/gio/modules when Qt creates the gtk3 theme; those modules need GLib >= 2.76 (x64) / 2.84 (arm64) symbols, so dlopen fails"
  confirming_evidence:
    - "x64 container (trixie, GLib 2.84, gvfs 1.57) prints the user's exact two lines; arm64 prints the same with g_variant_builder_init_static"
    - "Lines appear only when the gtk3 theme loads (GNOME desktop name); clean with desktop unset, KDE, QT_QPA_PLATFORMTHEME=gnome, or libqgtk3 unloadable"
    - "Bundled libgio has the compiled-in path /usr/lib/<triplet>/gio/modules and lacks the reported symbol; host libgvfscommon is BIND_NOW"
  falsification_test: "Errors with the gtk3 theme absent, or none with it present on a newer-GLib Debian host - neither observed"
  fix_rationale: "Either stop the bundled GIO from being initialised (no gtk3 theme plugin), stop it scanning host modules (GIO_MODULE_DIR),
    or use the host's GLib so host modules match (exclude the GLib/GTK family)"
  blind_spots: "User's host not reachable: its exact GLib/desktop name are inferred from the log; real GNOME session (not Xvfb/headless weston) not run;
    Ubuntu 24.04 arm64 (GLib 2.80 = bundle) predicted clean, not run; Fedora/Arch predicted clean from the path string, not run"
  candidate_causes:
    - "code/packaging: PyInstaller collects runner GLib/GTK via libqgtk3.so - CONFIRMED"
    - "environment: host gvfs built for newer GLib under the Debian multiarch module path - CONFIRMED (trigger)"
    - "config: GIO_MODULE_DIR/GIO_EXTRA_MODULES set in the user's env - ELIMINATED (clean container reproduces with neither set)"
    - "code: Qt's glib event dispatcher initialises GIO - ELIMINATED (QtCore needs only libglib; no errors without the gtk3 theme)"
  and_gate: "yes - needs all of: bundled older GLib (packaging) AND gtk3 theme selected and loadable (GTK-family XDG_CURRENT_DESKTOP + host
    libwayland) AND host module dir equal to the compiled-in Debian path AND host gvfs using a symbol newer than the bundled GLib"

## Symptoms

expected: Starting the Linux x64 tarball prints no GLib or GIO module errors at start-up.
actual: Observed in the user's pasted start-up log (the window still opened and the app worked): the host's gvfs GIO module, built for a newer GLib, fails to load into the bundled GLib.
errors: |
  /usr/lib/x86_64-linux-gnu/gvfs/libgvfscommon.so: undefined symbol: g_task_set_static_name
  Failed to load module: /usr/lib/x86_64-linux-gnu/gio/modules/libgvfsdbus.so
  (Also printed, believed to be the host desktop portal and not the bundle: qt.qpa.theme.gnome: dbus reply error:
  [ "org.freedesktop.DBus.Error.UnknownMethod" ] "No such interface "org.freedesktop.portal.Settings" on object at
  path /org/freedesktop/portal/desktop" -- confirm or refute.)
reproduction: UAT test 7. nx2android-d2ec054-linux-x64.tar.gz from fork-release run 40971470754, unpacked in
  ~/Downloads/nx2android on a Debian-family x64 host (GLib newer than 2.76), started with QT_QPA_PLATFORM=xcb ./nx2android.
  Same bundle under a nested weston Wayland session worked. Host not reachable from here.
started: Discovered during UAT (first Linux bundle tested)

## Eliminated

- hypothesis: GIO modules are loaded whenever the GUI starts on a GTK-family desktop, whatever host libraries exist
  evidence: without libwayland-cursor.so.0 the gtk3 theme plugin fails to load, Qt falls back to the gnome theme, and no gvfs error appears
    (QT_DEBUG_PLUGINS run). The load needs libqgtk3.so to load, i.e. a normal desktop host.
  timestamp: 2026-10-30T06:30:00Z

## Evidence

- timestamp: 2026-10-30T06:05:00Z
  checked: tar listing of nx2android-d2ec054-linux-x64.tar.gz (_internal/)
  found: the bundle ships the whole GTK3/GLib stack from the build runner - libglib-2.0.so.0, libgio-2.0.so.0, libgobject-2.0.so.0,
    libgmodule-2.0.so.0, libgthread-2.0.so.0, libgtk-3.so.0, libgdk-3.so.0, libgdk_pixbuf-2.0.so.0, pango, cairo, atk, atk-bridge, atspi, dbus-1
  implication: the bundled GLib/GIO, not the host's, is the one in the process

- timestamp: 2026-10-30T06:08:00Z
  checked: glib_{major,minor,micro}_version in the bundled libglib-2.0.so.0 (ELF dynsym read with scratchpad/gio-scripts/elfver.py)
  found: x64 bundle = GLib 2.72.4 (ubuntu-22.04 runner); arm64 bundle = GLib 2.80.0 (ubuntu-24.04-arm runner).
    x64 libgio exports g_task_set_name but not g_task_set_static_name (added in GLib 2.76)
  implication: matches the reported undefined symbol exactly: a host gvfs built against GLib >= 2.76 cannot bind to bundled 2.72

- timestamp: 2026-10-30T06:09:00Z
  checked: strings in bundled x64 libgio-2.0.so.0
  found: compiled-in default module dir "/usr/lib/x86_64-linux-gnu/gio/modules"; honours GIO_MODULE_DIR, GIO_EXTRA_MODULES, GIO_USE_VFS
  implication: on a Debian/Ubuntu multiarch host the bundled GIO scans the host's own module dir, where libgvfsdbus.so lives

- timestamp: 2026-10-30T06:12:00Z
  checked: NEEDED entries of every ELF in the x64 _internal tree
  found: libQt6Core/Gui/XcbQpa need only libglib-2.0 (event dispatcher). libgio-2.0 is needed only by
    PySide6/Qt/plugins/platformthemes/libqgtk3.so (plus libgtk-3, libgdk-3), networkinformation/libqglib.so, and the GTK stack itself
  implication: GIO (and its module scan) enters the process through the gtk3 platform theme plugin (or the glib network-information plugin)

- timestamp: 2026-10-30T06:14:00Z
  checked: PyInstaller 6.22.3 (requirements-build.txt pin; same version in .venv) depend/dylib.py and hooks/rthooks.dat
  found: Linux excludes are glibc, GL/EGL, libdrm, nvidia, libxcb/libxcb-dri, libwayland-*; GLib/GTK are not excluded, so binary
    dependency analysis of libqgtk3.so collects the runner's GTK3 stack. The only GIO runtime hook (pyi_rth_gio.py, sets
    GIO_MODULE_DIR=_MEIPASS/gio_modules) is wired to gi.repository.Gio (PyGObject) only; nothing sets it for PySide6
  implication: no stock PyInstaller setting covers this; the collection is PyInstaller default behaviour, not a project spec choice

- timestamp: 2026-10-30T06:25:00Z
  checked: Debian trixie containers (GLib 2.84.4, gvfs 1.57.2, amd64 via emulation and arm64 native); module FLAGS and imported symbols
    (scratchpad/gio-scripts/symcheck.sh)
  found: host modules in /usr/lib/<triplet>/gio/modules: libgvfsdbus.so (gio-vfs, gio-volume-monitor), libgioremote-volume-monitor.so,
    libdconfsettings.so (gsettings-backend). libgvfscommon.so is linked BIND_NOW (FLAGS 0x8, FLAGS_1 NOW), so a missing symbol fails dlopen.
    Missing from bundled x64 GLib 2.72: g_task_set_static_name (2.76), g_string_free_and_steal (2.76), g_once_init_enter/leave_pointer (2.80),
    g_variant_builder_init_static (2.84), and for dconf g_assertion_message_cmpint. Missing from bundled arm64 GLib 2.80: g_variant_builder_init_static only (gvfs; dconf binds)
  implication: arm64 bundle has the same exposure on hosts with GLib >= 2.84 (Debian 13, Ubuntu 25.04+); x64 on any Debian-family host with GLib >= 2.76

- timestamp: 2026-10-30T06:30:00Z
  checked: first container runs of the GUI under Xvfb, XDG_CURRENT_DESKTOP=GNOME, QT_QPA_PLATFORM=xcb (no libwayland in the image)
  found: no gvfs error; QT_DEBUG_PLUGINS showed libqgtk3.so failed to load (libwayland-cursor.so.0 missing: PyInstaller excludes libwayland-*),
    so Qt fell back to the "gnome" theme and GIO was never initialised
  implication: GIO module loading needs the gtk3 theme to actually load; a desktop host always has libwayland-client/cursor/egl

- timestamp: 2026-10-30T06:35:00Z
  checked: arm64 bundle, trixie arm64 + libwayland-client0/cursor0/egl1, XDG_CURRENT_DESKTOP=GNOME, QT_LOGGING_RULES=qt.qpa.theme*=true
  found: REPRODUCED. Between "Attempting to create platform theme gtk3" and "Successfully created platform theme gtk3" it prints
    "/usr/lib/aarch64-linux-gnu/gvfs/libgvfscommon.so: undefined symbol: g_variant_builder_init_static" and
    "Failed to load module: /usr/lib/aarch64-linux-gnu/gio/modules/libgvfsdbus.so". The window still starts (run ends only by timeout)
  implication: the trigger is QGtk3Theme construction (gtk_init), not Qt's glib event dispatcher; same symptom shape as the user's x64 log

- timestamp: 2026-10-30T06:45:00Z
  checked: arm64 environment matrix (scratchpad/gio-scripts/run.sh, trixie arm64, Xvfb, QT_QPA_PLATFORM=xcb, 25 s per case)
  found: A XDG_CURRENT_DESKTOP=GNOME -> gvfs error; B desktop unset -> clean; C GNOME + GIO_MODULE_DIR=<empty dir> -> clean;
    D GNOME + GIO_USE_VFS=local -> gvfs error still printed; E GNOME + QT_QPA_PLATFORMTHEME=gnome -> clean; F KDE -> clean
  implication: the module scan comes only from the gtk3 theme; GIO_USE_VFS=local is not a fix (GIO still loads every module of the
    gio-vfs extension point before picking "local"); GIO_MODULE_DIR or not loading the gtk3 theme both remove it

- timestamp: 2026-10-30T06:50:00Z
  checked: bundle probe scripts run as `nx2android probe.py env|gio|xdgopen|openurl` (scratchpad/gio-scripts/probe.py)
  found: the frozen process has LD_LIBRARY_PATH=<bundle>/_internal (LD_LIBRARY_PATH_ORIG unset) and every child inherits it.
    Bare g_vfs_get_default() via the bundled libgio reproduces the gvfs error without Qt. Host `gio info /tmp` started with that env fails:
    "gio: symbol lookup error: gio: undefined symbol: g_unix_mount_entry_get_options" (rc 127), and works outside it.
    QDesktopServices.openUrl(file:///tmp) under the gtk3 theme starts xdg-open with LD_LIBRARY_PATH=<bundle>/_internal (fake xdg-open on PATH)
  implication: ADJACENT BUG, not this symptom: host programs the GUI launches (xdg-open -> gio open / file manager, and on arm64 the
    distro adb) load the bundle's older libraries first. Any env-var fix for GIO must be judged against this existing leak

- timestamp: 2026-10-30T07:05:00Z
  checked: x64 bundle (the UAT build), trixie amd64 under emulation, same matrix
  found: REPRODUCED BYTE-FOR-BYTE: case A prints "/usr/lib/x86_64-linux-gnu/gvfs/libgvfscommon.so: undefined symbol: g_task_set_static_name"
    and "Failed to load module: /usr/lib/x86_64-linux-gnu/gio/modules/libgvfsdbus.so" - the user's two lines. B clean, C (GIO_MODULE_DIR empty)
    clean, D (GIO_USE_VFS=local) still fails, as on arm64
  implication: mechanism confirmed on the exact artifact the user ran

- timestamp: 2026-10-30T07:15:00Z
  checked: arm64 bundle under headless weston, QT_QPA_PLATFORM=wayland, XDG_CURRENT_DESKTOP=GNOME (scratchpad/gio-scripts/wl.sh)
  found: the same two gvfs lines, printed while Qt creates the gtk3 theme
  implication: the session type does not matter, the desktop name does. The UAT's clean nested-weston run most likely had no
    GTK-family XDG_CURRENT_DESKTOP in the weston terminal's environment (not verifiable from here)

- timestamp: 2026-10-30T07:16:00Z
  checked: strings in bundled libQt6Gui.so.6 and the container runs
  found: "qt.qpa.theme.gnome" / "dbus reply error: [" / "org.freedesktop.portal.Settings" live in the PySide6 wheel's libQt6Gui
    (QGnomeTheme's portal colour-scheme query, also run under the gtk3 theme). The container prints the same line with
    ServiceUnknown (no portal at all); it is still printed in the clean cases C and E
  implication: CONFIRMED host-side, not a library mismatch: Qt asks the host's xdg-desktop-portal for org.freedesktop.appearance and logs
    whatever the host answers. The user's UnknownMethod reply means the host portal runs but exports no Settings interface (no portal backend
    for that session). Qt falls back to defaults; harmless, and no GIO fix will remove it

- timestamp: 2026-10-30T07:18:00Z
  checked: closure of NEEDED edges in the x64 bundle without libqgtk3.so (scratchpad/gio-scripts/closure.py); gui/ and porter/ for QNetworkInformation
  found: 26 libs / 15.4 MiB are reachable only through libqgtk3.so (gtk-3, gdk-3, gdk_pixbuf, pango*, cairo*, atk*, atspi, epoxy, harfbuzz,
    fribidi, thai, Xi/Xcomposite/...); libgio/libgobject stay reachable only via networkinformation/libqglib.so (33 libs / 18.9 MiB with it).
    Nothing in gui/ porter/ packaging/ uses QNetworkInformation, so libqglib.so is never loaded
  implication: without the gtk3 theme plugin nothing in the process ever initialises GIO; libglib (QtCore) alone does not load modules

- timestamp: 2026-10-30T07:30:00Z
  checked: Qt folder dialog opened through the bundle (scratchpad/gio-scripts/dialog.sh, probe.py dialog), arm64, XDG_CURRENT_DESKTOP=GNOME
  found: bare container (no gdk-pixbuf, no icon theme): GTK's native chooser aborted the process ("Gtk:ERROR ... ensure_surface_for_gicon ...
    image-missing.png: Unrecognized image file format", "Bail out!"). Desktop-like container (libgtk-3-0t64, adwaita/hicolor icons, librsvg2,
    dconf backend): the GTK chooser opens and closes normally; opening it prints two more failures, libgioremote-volume-monitor.so and
    libgvfsdbus.so (same missing symbol). With GIO_MODULE_DIR=<empty>: GTK chooser opens, no errors. With QT_QPA_PLATFORMTHEME=gnome:
    Qt's own dialog opens, no errors
  implication: user-visible effect today is limited to the GTK chooser running without gvfs (no Trash, network locations, MTP/phone/camera
    or not-yet-mounted drives in its sidebar; local and mounted paths work). The abort needs a host with no gdk-pixbuf loaders/icon theme,
    which a GTK-family desktop does not have: a latent risk of the same bundled-GTK design, not the reported symptom

## Resolution

root_cause: |
  Packaging. PyInstaller 6.22.3's binary dependency analysis of PySide6's platformthemes/libqgtk3.so collects the build runner's whole
  GTK3/GLib stack into _internal (GLib 2.72.4 on the ubuntu-22.04 x64 runner, 2.80.0 on ubuntu-24.04-arm); PyInstaller excludes only glibc,
  GL, libxcb and libwayland on Linux, and its only GIO runtime hook (pyi_rth_gio) is for PyGObject. On a GTK-family desktop
  (XDG_CURRENT_DESKTOP GNOME, Unity, Cinnamon, MATE, XFCE, ...) Qt loads the gtk3 theme under xcb and wayland alike; gtk_init makes the bundled
  libgio scan its compiled-in module dir /usr/lib/<triplet>/gio/modules, which on Debian/Ubuntu is the host's own dir. The host's
  libgvfsdbus.so -> libgvfscommon.so (BIND_NOW) needs g_task_set_static_name (GLib 2.76) that bundled 2.72 lacks, so GIO prints the two
  lines and skips the module. arm64 bundle: same failure on hosts with GLib >= 2.84 (g_variant_builder_init_static), e.g. Debian 13.
  The qt.qpa.theme.gnome portal line is unrelated: Qt (from the PySide6 wheel) reports the host portal's D-Bus reply; it is host-side and harmless.
fix: (diagnose only - not applied)
fix_directions: |
  A. Drop PySide6/Qt/plugins/platformthemes/libqgtk3.so (and networkinformation/libqglib.so, unused) from the Linux bundle in
     packaging/nx2android.spec. Shown equivalent by QT_QPA_PLATFORMTHEME=gnome and by the run where libqgtk3 could not load: Qt falls back to
     its built-in gnome theme and GIO is never initialised. Removes 26 libs / 15.4 MiB (33 / 18.9 MiB with libqglib) of runner GTK stack and
     the other host-plugin mismatches it carries (gdk-pixbuf loaders, GTK immodules, the pixbuf abort). Cost: Qt's own file dialog instead of
     GTK's on GTK desktops (the app already forces Fusion); no env leaks to children.
  B. Exclude the GLib/GTK family from the bundle so the host's are used (as for a pip-installed PySide6). Restores gvfs in the GTK chooser
     and fixes the GLib part of the LD_LIBRARY_PATH leak. Cost: a host-library floor, a maintained exclude list, untested mixes if only part
     of the family is excluded; CI (runner == bundle) cannot catch regressions.
  C. GIO_MODULE_DIR=<empty dir in the bundle> before Qt starts (launcher GUI branch or a runtime hook). Verified clean at start-up and when
     the chooser opens. Cost: every child inherits it; porter, the tools, dotnet, clang and adb do not use GIO, but host programs the GUI
     opens through xdg-open would run without gvfs/dconf unless their env is scrubbed. GTK chooser stays without gvfs (as today).
  REFUTED: GIO_USE_VFS=local (case D still prints both lines). The lines are g_printerr, so log handlers cannot filter them.
  SEPARATE BUG (not this gap): children inherit LD_LIBRARY_PATH=<bundle>/_internal; host `gio` fails under it (symbol lookup error) and
     QDesktopServices.openUrl hands it to xdg-open, so Open folder / Open log (gui/app.py 250, 253, 334) and distro adb are at risk.
verification: (diagnose only)
files_changed: []
