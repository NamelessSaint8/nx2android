# The run side of the GUI bridge (porter/runlog.py, porter/procs.py): the saved run log and its protocol events, one-shot JSON errors,
# the stop channel, the cut-off marker and log retention. Each test runs porter with its own NX2A_HOME; no game files, toolchains or device.
import argparse, contextlib, io, json, os, signal, subprocess, sys, tempfile, time, unittest
from pathlib import Path
from unittest import mock

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


class InProcess(unittest.TestCase):   # runlog.run on a Namespace in this process, with its own NX2A_HOME
    def setUp(self):
        keep = dict(os.environ); self.addCleanup(lambda: (os.environ.clear(), os.environ.update(keep)))
        os.environ.pop('NX2A_GUI', None)
        self.home = Path(tempfile.mkdtemp()); os.environ['NX2A_HOME'] = str(self.home)
        from porter import procs
        adb = mock.patch.object(procs, 'adb_server', lambda: None); adb.start(); self.addCleanup(adb.stop)   # WR-06: install never starts the machine's adb server
        self.work = Path(tempfile.mkdtemp()) / '0100000000AAA000_build'; self.work.mkdir()

    def run_cmd(self, fn, cmd='port', progress='off'):
        from porter import runlog
        out = io.StringIO()
        with contextlib.redirect_stdout(out): code = runlog.run(argparse.Namespace(cmd=cmd, progress=progress, json=False, install=False), fn)
        return code, out.getvalue()

    def log(self): return max((self.home / 'logs').glob('*.log')).read_text(encoding='utf-8')


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


class RunLogInProcess(InProcess):
    def test_traceback_in_log(self):
        from porter import runlog
        out = io.StringIO()
        def boom(a): raise ValueError('boom')
        with self.assertRaises(ValueError), contextlib.redirect_stdout(out): runlog.run(argparse.Namespace(cmd='port', progress='json', json=False, install=False), boom)
        text = self.log()
        self.assertIn('Traceback', text); self.assertIn('ValueError: boom', text)
        self.assertIn('ValueError', [e['type'] for e in events(out.getvalue()) if e['ev'] == 'error'])

    def test_tool_logs_listed(self):
        from porter import runlog
        self.run_cmd(lambda a: runlog.build_folder(self.work, self.work / 'logs') or 0)
        self.assertIn(str(self.work / 'logs'), self.log().rstrip('\n').splitlines()[-1])

    def test_no_key_material(self):
        game, keys = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp()) / 'prod.keys'
        keys.write_text('header_key = SECRETVALUE\n', encoding='utf-8')
        r = porter('port', game, '-k', keys, '--progress', 'json', home=self.home)
        text = Path(json.loads(r.stdout.splitlines()[0])['path']).read_text(encoding='utf-8')
        self.assertIn(str(keys), text)
        self.assertNotIn('SECRETVALUE', text); self.assertNotIn('SECRETVALUE', r.stdout)


class Marker(InProcess):
    def marker(self): return self.work / '.port-running'

    def test_written_and_removed_on_success(self):
        from porter import runlog
        for code, kept in ((0, False), (1, False), (130, True)):
            seen = []
            def fn(a):
                runlog.build_folder(self.work, self.work / 'logs'); seen.append(self.marker().is_file()); return code
            self.assertEqual(self.run_cmd(fn)[0], code)
            self.assertEqual((seen, self.marker().is_file()), ([True], kept), code)

    def test_cut_off_redoes_stages(self):
        from porter import runlog
        old = [self.work / 'aoc.key', self.work / 'android/shaders.dmsv.key']; game_file = self.work / 'extract/RomFS/data.key'
        for f in old + [game_file]: f.parent.mkdir(parents=True, exist_ok=True); f.write_text('k', encoding='utf-8')
        self.marker().write_text('1 earlier', encoding='utf-8')
        fresh = []
        def fn(a):
            runlog.build_folder(self.work, self.work / 'logs'); fresh.append(self.marker().read_text(encoding='utf-8')); return 130
        self.run_cmd(fn)
        self.assertEqual([f.exists() for f in old], [False, False])
        self.assertTrue(game_file.is_file())
        self.assertNotEqual(fresh, ['1 earlier'])
        self.assertIn('the last port of this game was cut off', self.log())


class Retention(InProcess):
    def test_keeps_newest_30(self):
        d = self.home / 'logs'; d.mkdir()
        for i in range(35): (d / f'20200101-0000{i:02d}-port.log').write_text('old', encoding='utf-8')
        self.run_cmd(lambda a: 0, cmd='install')
        names = sorted(p.name for p in d.glob('*.log'))
        self.assertEqual(len(names), 30)
        self.assertTrue(names[-1].endswith('-install.log'))
        self.assertEqual(names[0], '20200101-000006-port.log')   # 29 old ones beside the new one: the 6 oldest are gone


class OneShot(unittest.TestCase):
    def test_broken_import_is_a_json_error(self):
        home, fake = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
        (fake / 'lz4').mkdir(); (fake / 'lz4/__init__.py').write_text('', encoding='utf-8')   # lz4 without lz4.block
        r = porter('profiles', '--json', home=home, env={'PYTHONPATH': os.pathsep.join([str(fake), str(REPO)])})
        self.assertEqual(r.returncode, 1, r.stdout)
        doc = json.loads(r.stdout)
        self.assertTrue(doc['error'].startswith('ModuleNotFoundError'), doc)
        self.assertIn('Traceback', r.stderr)


# A port that sits in one stage with a grandchild, as a GUI-started porter does (NX2A_GUI=1, its own session on POSIX as gui/runner.py starts it)
DRIVER = '''
import argparse, subprocess, sys, time
from porter import cli, runlog
from porter.upstream import PROG
def body():
    PROG.plan(1); PROG.stage('slow stage')
    c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
    PROG.say(f'ready {c.pid}'); time.sleep(60)
a = argparse.Namespace(cmd='port', progress='json', json=False, install=False)
sys.exit(runlog.run(a, lambda a: cli._with_progress(a.progress, body)))
'''

# WR-02: a child porter starts without stdin= gets an empty stdin, not the GUI's stop channel
INHERIT = '''
import argparse, subprocess, sys
from porter import procs
procs.setup(argparse.Namespace(cmd='port', progress='json'), lambda: None)
try: got = subprocess.run([sys.executable, '-c', 'import os; print(os.read(0, 64))'], capture_output=True, text=True, timeout=5).stdout.strip()
except subprocess.TimeoutExpired: got = 'blocked'
print(got, flush=True)
'''


def gone(pid, wait=5):   # True once the process no longer exists (an orphaned zombie is reaped by init in that time)
    t = time.time() + wait
    while time.time() < t:
        if os.name == 'nt':
            if str(pid) not in subprocess.run(['tasklist', '/FI', f'PID eq {pid}', '/NH'], capture_output=True, text=True).stdout: return True
        else:
            try: os.kill(pid, 0)
            except ProcessLookupError: return True
        time.sleep(0.1)
    return False


class Stop(unittest.TestCase):
    def start(self, gui=True):
        home = Path(tempfile.mkdtemp())
        e = dict(os.environ, NX2A_HOME=str(home), PYTHONIOENCODING='utf-8'); e.pop('NX2A_GUI', None)
        if gui: e['NX2A_GUI'] = '1'
        p = subprocess.Popen([sys.executable, '-c', DRIVER], cwd=REPO, env=e, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding='utf-8',
                             start_new_session=os.name != 'nt')
        self.addCleanup(self.kill, p)
        log, pid = None, None
        for ln in p.stdout:   # wait for the stage: a stop before it would find no stage to name
            ev = json.loads(ln)
            if ev['ev'] == 'log': log = Path(ev['path'])
            if ev['ev'] == 'say' and ev['msg'].startswith('ready '): pid = int(ev['msg'].split()[1]); break
        self.assertTrue(log and pid, 'the driver never reached its stage')
        return p, log, pid

    def kill(self, p):
        if p.poll() is None:
            if os.name == 'nt': subprocess.run(['taskkill', '/T', '/F', '/PID', str(p.pid)], capture_output=True)
            else: os.killpg(p.pid, 9)
            p.wait()
        for f in (p.stdin, p.stdout):
            try: f.close()
            except OSError: pass

    def stopped(self, p, log):
        self.assertEqual(p.wait(timeout=10), 130)
        self.assertIn('cancelled during slow stage', log.read_text(encoding='utf-8'))

    @unittest.skipIf(os.name == 'nt', 'POSIX only')
    def test_sigterm_to_group(self):
        p, log, _ = self.start()
        os.killpg(p.pid, signal.SIGTERM)
        self.stopped(p, log)

    def test_stdin_stop(self):
        p, log, _ = self.start()
        p.stdin.write('stop\n'); p.stdin.flush()
        self.stopped(p, log)

    def test_stdin_eof(self):
        p, log, _ = self.start()
        p.stdin.close()
        self.stopped(p, log)

    def test_grandchild_dies(self):
        p, log, pid = self.start()
        p.stdin.write('stop\n'); p.stdin.flush()
        self.stopped(p, log)
        self.assertTrue(gone(pid), f'grandchild {pid} outlived the stop')

    def test_windows_stop_without_job_kills_tree(self):   # WR-01: no Job Object, so the watcher taskkills porter's own tree before it exits
        from porter import procs
        with mock.patch.object(procs.os, 'read', side_effect=[b'stop\n']), mock.patch.object(procs.os, 'name', 'nt'), \
             mock.patch.object(procs.subprocess, 'run') as run, mock.patch.object(procs.os, '_exit') as ex, contextlib.redirect_stdout(io.StringIO()):
            procs._watch(None, lambda: None)
        self.assertEqual(run.call_args[0][0], ['taskkill', '/T', '/F', '/PID', str(os.getpid())])
        ex.assert_called_once_with(130)

    def test_children_get_no_stop_channel(self):
        e = dict(os.environ, NX2A_HOME=tempfile.mkdtemp(), NX2A_GUI='1', PYTHONIOENCODING='utf-8')
        p = subprocess.Popen([sys.executable, '-c', INHERIT], cwd=REPO, env=e, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding='utf-8',
                             start_new_session=os.name != 'nt')
        self.addCleanup(self.kill, p)
        self.assertEqual(p.stdout.readline().strip(), "b''")

    def test_msbuild_env(self):
        from porter import procs
        keep = dict(os.environ); self.addCleanup(lambda: (os.environ.clear(), os.environ.update(keep)))
        os.environ.pop('NX2A_GUI', None)
        procs.setup(argparse.Namespace(cmd='doctor', json=True), lambda: None)
        self.assertEqual((os.environ.get('MSBUILDDISABLENODEREUSE'), os.environ.get('DOTNET_CLI_USE_MSBUILD_SERVER'), os.environ.get('UseSharedCompilation')),
                         ('1', '0', 'false'))

    def test_cli_without_gui_has_no_watcher(self):
        p, log, _ = self.start(gui=False)
        p.stdin.close()
        with self.assertRaises(subprocess.TimeoutExpired): p.wait(timeout=2)


if __name__ == '__main__':
    unittest.main()
