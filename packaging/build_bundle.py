# Build the player's bundle on the host it runs on: the app (one executable that is the GUI and the Python the pipeline runs the engine's tools with),
# the committed nxnative/ tree in its resource root (the engine the port builds from), and the install guide, archived as
#   dist/nx2android-<version>-windows-x64.zip       Windows: dist/nx2android/ with nx2android.exe, unsigned
#   dist/nx2android-<version>-macos-arm64.dmg       macOS: nx2android.app (resources in Contents/Resources), signed with MACOS_SIGN_IDENTITY or ad hoc
#   dist/nx2android-<version>-linux-x64.tar.gz      Linux: dist/nx2android/ with nx2android
#   dist/nx2android-<version>-linux-arm64.tar.gz
#   python packaging/build_bundle.py      (pip install -r requirements.txt -r requirements-build.txt; on Windows only, PyInstaller's bootloader compiled on
#                                          this PC first: python packaging/build_bootloader.py, since antivirus engines flag the prebuilt one. macOS and
#                                          Linux use PyInstaller's own bootloader, which those hosts do not flag)
# The bundle holds no toolchain: the Setup tab downloads NDK r27c, the .NET SDK 10 and platform-tools from their makers, or the player installs them (packaging/INSTALL.md).
# Notarization and stapling of the DMG run in the release workflow, which holds the API key. packaging/smoke_bundle.py checks the result.
import hashlib, os, platform, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST, WORK = ROOT / 'dist', ROOT / 'build/pyinstaller'
SKIP = 'nxnative/dm/gfx/tools/dmsh_xlate_bin/'   # a Mach-O shader translator the Android port never runs; unsigned code in Contents/Resources fails codesign


def tracked(prefix):
    return [p for p in subprocess.run(['git', '-C', str(ROOT), 'ls-files', '-z', prefix], capture_output=True, text=True, check=True).stdout.split('\0') if p]


def version():   # fork tags are v<upstream>-ns.<n>, which never clash with upstream's v0.1.x
    r = subprocess.run(['git', '-C', str(ROOT), 'describe', '--tags', '--match', 'v*-ns.*', '--always', '--dirty'], capture_output=True, text=True)
    v = r.stdout.strip() if r.returncode == 0 else ''
    return v.removeprefix('v') or 'dev'


def target(plat=sys.platform, machine=platform.machine()):
    os_ = 'macos' if plat == 'darwin' else 'windows' if plat == 'win32' else 'linux'
    return os_, {'x86_64': 'x64', 'amd64': 'x64', 'aarch64': 'arm64'}.get(machine.lower(), machine.lower())


def asset_name(version, os_, arch):
    return f'nx2android-{version}-{os_}-{arch}.' + {'windows': 'zip', 'macos': 'dmg'}.get(os_, 'tar.gz')


def bundled(files):
    return [f for f in files if not f.startswith(SKIP)]


def engine_id(root, files):   # over the copied bytes, so a dirty tree gets its own id (a git tree hash would not)
    h = hashlib.sha256()
    for f in sorted(files): h.update(f.encode() + b'\0' + (Path(root) / f).read_bytes())
    return h.hexdigest()[:16]


def run(*cmd): subprocess.run([str(c) for c in cmd], check=True)


def main():
    os_, arch = target(); ver = version(); sign = os.environ.get('MACOS_SIGN_IDENTITY')
    if os_ == 'windows':
        sys.path.insert(0, str(ROOT / 'packaging'))
        import build_bootloader
        if not build_bootloader.is_local(): sys.exit('PyInstaller has its prebuilt bootloader, which antivirus engines flag: run python packaging/build_bootloader.py first')
    env = dict(os.environ, NX2A_VERSION=ver)
    if sign: env['PYINSTALLER_STRICT_BUNDLE_CODESIGN_ERROR'] = '1'   # else a failed signature is only a warning
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--distpath', str(DIST), '--workpath', str(WORK), str(ROOT / 'packaging/nx2android.spec')],
                   check=True, env=env)
    app = DIST / ('nx2android.app' if os_ == 'macos' else 'nx2android')
    res = app / 'Contents/Resources' if os_ == 'macos' else app   # porter/paths.py REPO
    files = bundled(tracked('nxnative'))   # the committed engine and profiles only: no local builds, keys or game files
    for f in files:
        d = res / f; d.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / f, d)
    for src, dst in (('packaging/INSTALL.md', 'INSTALL.md'), ('README.md', 'README.md'), ('docs/ARCHITECTURE.md', 'docs/ARCHITECTURE.md'), ('docs/PORT_STATUS.md', 'docs/PORT_STATUS.md'), ('nxnative/LICENSE', 'LICENSE')):
        (res / dst).parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / src, res / dst)
    shutil.copytree(ROOT / 'docs/images', res / 'docs/images', dirs_exist_ok=True)   # PORT_STATUS.md's screenshots
    (res / 'VERSION').write_text(ver + '\n', encoding='utf-8')   # the release check (devtools/port_check.py) records it
    (res / 'ENGINE').write_text(engine_id(ROOT, files) + '\n', encoding='utf-8')   # porter/paths.py _engine(): the player's engine copy is keyed by it
    out = DIST / asset_name(ver, os_, arch)
    if os_ == 'macos':
        # the copied resources broke the seal PyInstaller made: sign the outer bundle again, then check it as Gatekeeper will
        run('codesign', '--force', '--sign', *((sign, '--options', 'runtime', '--timestamp') if sign else ('-',)), app)
        run('codesign', '--verify', '--deep', '--strict', '--verbose=2', app)
        stage = WORK / 'dmg'; shutil.rmtree(stage, ignore_errors=True); stage.mkdir(parents=True)
        run('ditto', app, stage / app.name)
        (stage / 'Applications').symlink_to('/Applications'); shutil.copy2(ROOT / 'packaging/INSTALL.md', stage / 'INSTALL.md')
        run('hdiutil', 'create', '-volname', 'nx2android', '-srcfolder', stage, '-ov', '-format', 'UDZO', out)
        if sign: run('codesign', '--sign', sign, '--timestamp', out)
    elif os_ == 'windows':
        out = Path(shutil.make_archive(str(out).removesuffix('.zip'), 'zip', DIST, 'nx2android'))
    else:   # tar keeps PyInstaller 6's symlinks, which zip would turn into copies or drop (never zip on Linux or macOS)
        out = Path(shutil.make_archive(str(out).removesuffix('.tar.gz'), 'gztar', DIST, 'nx2android'))
    print(f'{app} ({len(files)} nxnative files)\n{out} ({out.stat().st_size / 2**20:.0f} MB)')


if __name__ == '__main__':
    main()
