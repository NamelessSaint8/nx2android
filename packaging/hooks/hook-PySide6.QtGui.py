# PyInstaller 6.22.3's own hook-PySide6.QtGui.py (pinned in requirements-build.txt; copy the stock hook again on a PyInstaller upgrade) less
# platformthemes/libqgtk3.so. On Linux that plugin pulls the build runner's GTK3/GLib/GIO stack into the bundle; on a GTK-family desktop Qt loads it,
# the bundled older GIO scans the host's /usr/lib/<triplet>/gio/modules and the host's gvfs fails to bind (UAT G-01-7: undefined symbol
# g_task_set_static_name). Without it Qt takes its built-in gnome theme and its own file dialog. The file name gives add_qt6_dependencies the module.
import os
from PyInstaller.utils.hooks.qt import add_qt6_dependencies

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
binaries = [b for b in binaries if os.path.basename(b[0]) != 'libqgtk3.so']
