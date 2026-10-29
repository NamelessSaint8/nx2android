# The run side of the GUI bridge (porter/runlog.py, porter/procs.py): the saved run log and its protocol events, one-shot JSON errors,
# the stop channel, the cut-off marker and log retention. Each test runs porter with its own NX2A_HOME; no game files, toolchains or device.
import json, os, re, subprocess, sys, tempfile, unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

MISSING = None
for _m in ('lz4.block', 'capstone'):
    try: __import__(_m)
    except ModuleNotFoundError:
        if os.environ.get('CI'): raise   # CI installs the lock: a missing module there is a failure
        MISSING = MISSING or _m


def setUpModule():   # not a module-level SkipTest: `python -m unittest tests.test_runlog` crashes on one
    if MISSING: raise unittest.SkipTest(f'{MISSING} is not installed (python -m pip install -r requirements.txt)')


def porter(*args, home, env=None, **kw):
    e = dict(os.environ, NX2A_HOME=str(home), PYTHONIOENCODING='utf-8'); e.pop('NX2A_GUI', None); e.update(env or {})
    return subprocess.run([sys.executable, '-m', 'porter', *map(str, args)], cwd=REPO, env=e, capture_output=True, text=True, encoding='utf-8', timeout=120, **kw)


def events(out): return [json.loads(ln) for ln in out.splitlines() if ln.startswith('{')]


class RunLog(unittest.TestCase):
    def test_port_error_has_log_and_error_event(self):
        home, game = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
        r = porter('port', game, '--progress', 'json', home=home)
        self.assertEqual(r.returncode, 1, r.stderr)
        first = json.loads(r.stdout.splitlines()[0])
        self.assertEqual(first['ev'], 'log')
        p = Path(first['path'])
        self.assertEqual(p.parent, home / 'logs')
        self.assertRegex(p.name, r'^\d{8}-\d{6}-port\.log$')
        err = [e for e in events(r.stdout) if e['ev'] == 'error']
        self.assertEqual(len(err), 1, r.stdout)
        self.assertEqual((err[0]['type'], err[0]['log']), ('BuildError', str(p)))
        self.assertIn('prod.keys', err[0]['msg'])
        text = p.read_text(encoding='utf-8')
        self.assertIn('$ porter port ', text)
        self.assertRegex(text, r'\[RED\] no prod\.keys')

    def test_cli_run_writes_log_too(self):
        home, game = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
        r = porter('port', game, '--progress', 'lines', home=home)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertFalse(events(r.stdout), r.stdout)
        logs = list((home / 'logs').glob('*-port.log'))
        self.assertEqual(len(logs), 1)
        self.assertIn('no prod.keys', logs[0].read_text(encoding='utf-8'))


class OneShot(unittest.TestCase):
    def test_broken_import_is_a_json_error(self):
        home, fake = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
        (fake / 'lz4').mkdir(); (fake / 'lz4/__init__.py').write_text('', encoding='utf-8')   # lz4 without lz4.block
        r = porter('profiles', '--json', home=home, env={'PYTHONPATH': os.pathsep.join([str(fake), str(REPO)])})
        self.assertEqual(r.returncode, 1, r.stdout)
        doc = json.loads(r.stdout)
        self.assertTrue(doc['error'].startswith('ModuleNotFoundError'), doc)
        self.assertIn('Traceback', r.stderr)


if __name__ == '__main__':
    unittest.main()
