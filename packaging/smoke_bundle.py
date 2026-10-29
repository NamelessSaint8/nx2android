# Smoke test of a built bundle, run by the release workflow (fork-release.yml) and by hand:
#   python packaging/smoke_bundle.py dist/nx2android-<version>-macos-arm64.dmg      (or an .app, or a bundle folder such as dist/nx2android)
# It runs the frozen app from a read-only place (the DMG mounted read-only, or a chmod a-w copy) with a fresh NX2A_HOME, and fails unless doctor and
# profiles answer, the bundle's files are unchanged afterwards (PKG-05: nothing is ever written into the bundle) and, on macOS, the signature still verifies.
# Host Python, standard library only.
import json, os, shutil, stat, subprocess, sys, tempfile
from pathlib import Path

FAILS = []


def check(name, ok, detail=''):
    print(f'PASS {name}' if ok else f'[RED] {name}' + (f': {detail}' if detail else ''), flush=True)
    if not ok: FAILS.append(name)


def listing(root):   # what a write into the bundle would change
    out = {}
    for d, dirs, files in os.walk(root):
        for n in dirs + files:
            p = os.path.join(d, n); s = os.lstat(p); out[os.path.relpath(p, root)] = (s.st_size, s.st_mtime_ns)
    return out


def set_writable(root, on):
    for d, dirs, files in os.walk(root):
        for n in dirs + files:
            p = os.path.join(d, n)
            if not os.path.islink(p): m = os.stat(p).st_mode; os.chmod(p, m | stat.S_IWUSR if on else m & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    m = os.stat(root).st_mode; os.chmod(root, m | stat.S_IWUSR if on else m & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def porter(exe, env, *args):   # (stdout as JSON or None, exit code, stderr's last line)
    try: r = subprocess.run([str(exe), '-m', 'porter', *args], capture_output=True, text=True, env=env, cwd=env['NX2A_HOME'], timeout=120)
    except subprocess.TimeoutExpired: return None, 'timeout', ''
    try: doc = json.loads(r.stdout)
    except ValueError: doc = None
    return doc, r.returncode, (r.stderr.strip().splitlines() or [''])[-1]


def main(argv):
    if len(argv) != 2: sys.exit('usage: python packaging/smoke_bundle.py <.dmg | .app | bundle folder>')
    src = Path(argv[1]).resolve(); tmp = Path(tempfile.mkdtemp(prefix='nx2a-smoke-')); mount = None
    try:
        if src.suffix == '.dmg':
            mount = tmp / 'mnt'; mount.mkdir()
            subprocess.run(['hdiutil', 'attach', '-nobrowse', '-readonly', '-mountpoint', str(mount), str(src)], check=True, capture_output=True)
            root = mount / 'nx2android.app'
        else:
            root = tmp / 'ro' / src.name; shutil.copytree(src, root, symlinks=True); set_writable(root, False)
        exe = next((root / p for p in ('Contents/MacOS/nx2android', 'nx2android.exe', 'nx2android') if (root / p).is_file()), None)
        check('the app is in the bundle', exe is not None, str(root))
        if exe is None: return 1
        home = tmp / 'home'; home.mkdir()
        env = dict(os.environ, NX2A_HOME=str(home))
        before = listing(root)
        doc, code, err = porter(exe, env, 'doctor', '--json')
        check('doctor --json answers a JSON list', isinstance(doc, list) and code in (0, 1), f'exit {code}: {err}')
        doc, code, err = porter(exe, env, 'profiles', '--json')
        check('profiles --json lists the profiles', isinstance(doc, list) and len(doc) > 0 and code == 0, f'exit {code}: {err}')
        after = listing(root)
        changed = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
        check('nothing was written into the bundle', not changed, ', '.join(changed[:10]))
        if sys.platform == 'darwin':
            r = subprocess.run(['codesign', '--verify', '--deep', '--strict', '--verbose=2', str(root)], capture_output=True, text=True)
            check('codesign --verify --deep --strict', r.returncode == 0, r.stderr.strip())
    finally:
        if mount: subprocess.run(['hdiutil', 'detach', str(mount), '-force'], capture_output=True)
        elif (tmp / 'ro').exists(): set_writable(tmp / 'ro', True)
        shutil.rmtree(tmp, ignore_errors=True)
    print(f'\n{len(FAILS)} failed' if FAILS else '\nall checks passed')
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
