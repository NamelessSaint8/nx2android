# PyInstaller 6.22.3's own hook-PySide6.QtNetwork.py (pinned in requirements-build.txt; copy the stock hook again on a PyInstaller upgrade) less
# networkinformation/libqglib.so, the only plugin besides the gtk3 theme that links libgio (see hook-PySide6.QtGui.py, UAT G-01-7).
# Nothing in gui/ or porter/ uses QNetworkInformation. The file name gives add_qt6_dependencies the module.
import os
from PyInstaller.utils.hooks.qt import add_qt6_dependencies, pyside6_library_info

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
binaries += pyside6_library_info.collect_qtnetwork_files()
binaries = [b for b in binaries if os.path.basename(b[0]) != 'libqglib.so']
