# porter/paths.py in a frozen bundle (PKG-05): the resource root is read-only, and the port builds from a writable copy of the engine in the player's folder.
# Fake read-only bundles (a macOS .app and a plain folder) are driven in subprocesses that set sys.frozen before importing porter.paths. Stdlib only.
import json, os, shutil, stat, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXE = 'nx2android.exe' if os.name == 'nt' else 'nx2android'
DRIVER = '''import json, os, pathlib, shutil, stat, sys
sys.path.insert(0, {root!r})
sys.frozen = {frozen!r}; sys.executable = {exe!r}; sys.platform = {plat!r}
from porter import paths
print(json.dumps({{'REPO': str(paths.REPO), 'NXNATIVE': str(paths.NXNATIVE)}}))
'''


def writable(root):   # undo the read-only modes so the tempdir can be deleted
    for r, ds, fs in os.walk(root):
        for n in ds + fs:
            p = os.path.join(r, n)
            if not os.path.islink(p): os.chmod(p, os.stat(p).st_mode | stat.S_IWUSR)


def listing(root):
    return sorted((str(p.relative_to(root)), p.stat().st_size, p.stat().st_mtime_ns) for p in Path(root).rglob('*'))


class Engine(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.home = self.tmp / 'home'
        self.addCleanup(lambda: (writable(self.tmp), shutil.rmtree(self.tmp)))

    def bundle(self, mac=True, eid='abc123'):
        """A read-only fake bundle: returns (exe, resource root)"""
        if mac: exe = self.tmp / 'nx2android.app/Contents/MacOS' / EXE; res = self.tmp / 'nx2android.app/Contents/Resources'
        else: exe = self.tmp / 'nx2android' / EXE; res = exe.parent
        exe.parent.mkdir(parents=True); exe.write_bytes(b'')
        (res / 'nxnative/dm/games').mkdir(parents=True); (res / 'nxnative/scripts').mkdir()
        (res / 'nxnative/dm/games/x.tsv').write_text('key\tvalue\n'); (res / 'nxnative/scripts/a.py').write_text('print(1)\n')
        if eid: (res / 'ENGINE').write_text(eid + '\n')
        for r, ds, fs in os.walk(self.tmp / ('nx2android.app' if mac else 'nx2android'), topdown=False):
            for n in fs + ([] if os.name == 'nt' else ds):   # Windows: the read-only attribute is for files only
                p = os.path.join(r, n); os.chmod(p, os.stat(p).st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
        return exe, res

    def start(self, exe=None, mac=True, frozen=True, wait=True):
        code = DRIVER.format(root=str(ROOT), frozen=frozen, exe=str(exe) if exe else sys.executable, plat='darwin' if mac else 'linux')
        env = dict(os.environ, NX2A_HOME=str(self.home))
        p = subprocess.Popen([sys.executable, '-c', code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        return p if not wait else self.result(p)

    def result(self, p):
        out, err = p.communicate(timeout=120)
        self.assertEqual(p.returncode, 0, err)
        return json.loads(out)

    def test_macos_layout(self):
        exe, res = self.bundle(mac=True); before = listing(res)
        r = self.start(exe, mac=True)
        nx = self.home / 'engine/abc123/nxnative'
        self.assertEqual(Path(r['REPO']), res)
        self.assertEqual(Path(r['NXNATIVE']), nx)
        self.assertTrue((nx / 'dm/games/x.tsv').is_file() and (nx / 'scripts/a.py').is_file())
        (nx / 'dm/new.txt').write_text('obj/ goes here')   # the copy is writable
        self.assertEqual(listing(res), before)

    def test_plain_layout(self):
        exe, res = self.bundle(mac=False); before = listing(res)
        r = self.start(exe, mac=False)
        self.assertEqual(Path(r['REPO']), res)
        self.assertEqual(Path(r['NXNATIVE']), self.home / 'engine/abc123/nxnative')
        (Path(r['NXNATIVE']) / 'dm/new.txt').write_text('x')
        self.assertEqual(listing(res), before)

    def test_checkout_unchanged(self):
        r = self.start(frozen=False)
        self.assertEqual(Path(r['NXNATIVE']), ROOT / 'nxnative')
        self.assertFalse((self.home / 'engine').exists())

    def test_missing_engine_id(self):
        exe, res = self.bundle(mac=True, eid=None)
        r = self.start(exe, mac=True)
        self.assertEqual(Path(r['NXNATIVE']), res / 'nxnative')
        self.assertFalse((self.home / 'engine').exists())

    def test_prunes_other_versions(self):
        exe, _ = self.bundle(mac=True)
        (self.home / 'engine/old999/nxnative').mkdir(parents=True); (self.home / 'engine/abc123.tmp-1').mkdir()
        self.start(exe, mac=True)
        self.assertEqual(sorted(p.name for p in (self.home / 'engine').iterdir()), ['abc123', 'abc123.tmp-1'])   # another porter may still be copying

    def test_concurrent_first_start(self):   # the GUI's three start-up calls
        exe, _ = self.bundle(mac=True)
        ps = [self.start(exe, mac=True, wait=False) for _ in range(3)]
        rs = [self.result(p) for p in ps]
        self.assertEqual({r['NXNATIVE'] for r in rs}, {str(self.home / 'engine/abc123/nxnative')})
        self.assertEqual([p.name for p in (self.home / 'engine').iterdir()], ['abc123'])
        self.assertTrue((self.home / 'engine/abc123/nxnative/dm/games/x.tsv').is_file())

    def test_second_start_reuses(self):
        exe, _ = self.bundle(mac=True)
        nx = self.home / 'engine/abc123/nxnative'
        self.start(exe, mac=True); (nx / 'dm/obj.txt').write_text('built')
        before = sorted((str(p), p.stat().st_mtime_ns, p.stat().st_ino) for p in nx.rglob('*'))
        self.start(exe, mac=True)
        self.assertEqual(sorted((str(p), p.stat().st_mtime_ns, p.stat().st_ino) for p in nx.rglob('*')), before)


class Launcher(unittest.TestCase):
    def test_no_bytecode_flag(self):   # the bundle's interpreter writes no __pycache__ beside the bundle's or the engine's scripts
        import ast
        tree = ast.parse((ROOT / 'packaging/nx2android.py').read_text(encoding='utf-8'))
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
        self.assertEqual(ast.unparse(main.body[0]), 'sys.dont_write_bytecode = True')


if __name__ == '__main__':
    unittest.main()
