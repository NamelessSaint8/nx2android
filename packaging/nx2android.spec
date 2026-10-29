# PyInstaller spec of the bundle: python packaging/build_bundle.py runs it (docs/ARCHITECTURE.md "Distribution").
# One folder, one executable (packaging/nx2android.py) that is both the app and the Python the pipeline runs the engine's tools with. The tools are not
# frozen (they run from nxnative/ beside the executable), so the bundle carries the whole standard library and the modules they import.
# On macOS the folder is wrapped in nx2android.app (BUNDLE below), whose data files live in Contents/Resources.
import os, re, sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).parent
NOT_STDLIB = {'tkinter', 'turtle', 'turtledemo', 'idlelib', 'test', 'lib2to3', 'ensurepip', 'venv', 'pydoc_data', 'antigravity', 'this', '__phello__'}
hidden = collect_submodules('porter') + collect_submodules('gui')
for m in sorted(sys.stdlib_module_names - NOT_STDLIB):
    if m.startswith('_') and m not in ('__future__',): hidden.append(m); continue
    hidden += collect_submodules(m, filter=lambda n: not any(p in NOT_STDLIB or p in ('tests', 'test') for p in n.split('.'))) or [m]
datas, binaries = [], []
for pkg in ('capstone', 'lz4', 'PIL', 'yaml') + (('backports.zstd',) if sys.version_info < (3, 14) else ()):
    d, b, h = collect_all(pkg); datas += d; binaries += b; hidden += h

a = Analysis([str(ROOT / 'packaging/nx2android.py')], pathex=[str(ROOT)], binaries=binaries, datas=datas, hiddenimports=hidden,
             excludes=sorted(NOT_STDLIB - {'test'}), noarchive=False)
pyz = PYZ(a.pure)
# MACOS_SIGN_IDENTITY: a Developer ID (release workflow); unset, PyInstaller signs ad hoc, which arm64 needs. No entitlements to start (hardened runtime as is)
SIGN = os.environ.get('MACOS_SIGN_IDENTITY') or None
# u: unbuffered, so the GUI gets each progress line as it is printed; X utf8: the engine's tools write their tables with open() and no encoding
exe = EXE(pyz, a.scripts, [('u', None, 'OPTION'), ('X utf8', None, 'OPTION')], exclude_binaries=True, name='nx2android', console=True, upx=False,
          codesign_identity=SIGN, entitlements_file=None)
coll = COLLECT(exe, a.binaries, a.datas, name='nx2android', upx=False)
if sys.platform == 'darwin':
    VER = re.match(r'\d+(\.\d+)+', os.environ.get('NX2A_VERSION', ''))   # 0.1.2 of 0.1.2-ns.1 (build_bundle.py version())
    FOLDER = 'nx2android reads the game folder you pick and writes the port beside it.'
    app = BUNDLE(coll, name='nx2android.app', bundle_identifier='io.github.namelesssaint8.nx2android',
                 version=VER[0] if VER else '0.0.0',
                 info_plist={'CFBundleDisplayName': 'nx2android',
                             'LSBackgroundOnly': False,   # console=True writes True, which hides the Dock icon and the menu bar
                             'NSHighResolutionCapable': True, 'LSMinimumSystemVersion': '14.0',
                             **{k: FOLDER for k in ('NSDocumentsFolderUsageDescription', 'NSDownloadsFolderUsageDescription', 'NSDesktopFolderUsageDescription',
                                                    'NSRemovableVolumesUsageDescription', 'NSNetworkVolumesUsageDescription')}})
