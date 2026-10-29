# The GUI side of the bridge (gui/runner.py, gui/app.py), headless (QT_QPA_PLATFORM=offscreen): a failed run shows its cause and opens its log,
# Cancel stops the whole tree and says "cancelled" only once it is gone, closing the window mid-run asks first. A stand-in porter
# (tests/fixtures/bridge/fake_porter.py, via runner.PORTER) plays the long runs; the Errors tests run the real porter on an empty folder.
import json, os, subprocess, sys, tempfile, time, unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
REPO = Path(__file__).resolve().parent.parent
FAKE = str(REPO / 'tests/fixtures/bridge/fake_porter.py')
sys.path.insert(0, str(REPO))

MISSING = None
for _m in ('PySide6.QtWidgets', 'lz4.block', 'capstone'):
    try: __import__(_m)
    except ModuleNotFoundError:
        if os.environ.get('CI'): raise   # CI installs the lock: a missing module there is a failure
        MISSING = MISSING or _m.split('.')[0]

HOME = tempfile.mkdtemp()
os.environ['NX2A_HOME'] = HOME   # before gui.app: the porters it starts read their settings from here
if not MISSING:
    from PySide6.QtTest import QSignalSpy, QTest
    from PySide6.QtWidgets import QApplication, QMessageBox
    from gui import app, runner
    from porter import paths
APP = None


def setUpModule():
    global APP
    if MISSING: raise unittest.SkipTest(f'{MISSING} is not installed (python -m pip install -r requirements.txt)')
    APP = QApplication.instance() or QApplication([])


def wait(signal, ms):   # the first emission's arguments, or None
    spy = QSignalSpy(signal)
    return spy.at(0) if spy.count() or spy.wait(ms) else None


def until(pred, ms):   # spin the event loop until pred() holds
    end = time.time() + ms / 1000
    while not pred() and time.time() < end: QTest.qWait(20)
    return pred()


def reap(pid):   # a test's leftover process (the detached one)
    try: os.kill(pid, 9)
    except OSError: pass


def alive(pid):
    if os.name == 'nt': return str(pid) in subprocess.run(['tasklist', '/FI', f'PID eq {pid}', '/NH'], capture_output=True, text=True).stdout
    try: os.kill(pid, 0); return True
    except ProcessLookupError: return False
    except PermissionError: return True


def gone(pid, s=5):
    end = time.time() + s
    while time.time() < end:
        if not alive(pid): return True
        time.sleep(0.1)
    return False


class Errors(unittest.TestCase):
    def setUp(self):
        keep = runner.PORTER; self.addCleanup(setattr, runner, 'PORTER', keep)

    def test_failed_port_shows_cause_and_log(self):
        w = app.Window(); self.addCleanup(w.deleteLater)
        port = w.port; game = tempfile.mkdtemp()
        port.run(['port', game, '--progress', 'json'])
        got = wait(port.porter.finished, 60000)
        self.assertEqual(got, [1])
        self.assertIn('prod.keys', port.step.text())
        self.assertNotIn('the log says why', port.step.text())
        self.assertTrue(port.log_btn.isEnabled())
        with mock.patch.object(app, 'QDesktopServices') as ds:
            port.log_btn.click()
        url = ds.openUrl.call_args[0][0]
        p = Path(url.toLocalFile())
        self.assertTrue(p.is_file(), p)
        self.assertEqual(p.parent, Path(HOME) / 'logs')

    def test_process_env(self):
        runner.PORTER = ['-c', "import json, os; print(json.dumps({'ev': 'say', 'msg': json.dumps([os.getcwd(), os.environ.get('NX2A_GUI')])}))"]
        p = runner.Porter(); evs = []; p.event.connect(evs.append)
        p.start([])
        self.assertEqual(wait(p.finished, 20000), [0])
        cwd, gui = json.loads(evs[0]['msg'])
        self.assertEqual(os.path.realpath(cwd), os.path.realpath(paths.user_dir()))
        self.assertEqual(gui, '1')


class Fake(unittest.TestCase):   # runner.PORTER points at the stand-in; GRACE_MS is restored
    def setUp(self):
        keep = runner.PORTER, getattr(runner, 'GRACE_MS', 5000)
        self.addCleanup(lambda: (setattr(runner, 'PORTER', keep[0]), setattr(runner, 'GRACE_MS', keep[1])))
        runner.PORTER = [FAKE, '--tree', '--']

    def tree(self, porter, log=None):   # start a --tree port; its pids once they are printed
        evs = log if log is not None else []; porter.event.connect(evs.append)
        porter.start(['port', 'x', '--progress', 'json'])
        self.assertTrue(until(lambda: any(e.get('ev') == 'pids' for e in evs), 10000), evs)
        pids = next(e for e in evs if e.get('ev') == 'pids')
        self.addCleanup(reap, pids['detached']); self.addCleanup(reap, pids['child'])
        return pids


class Stop(Fake):
    def test_stop_kills_tree_keeps_detached(self):
        p = runner.Porter(); fin = QSignalSpy(p.finished)
        pids = self.tree(p)
        p.stop()
        self.assertTrue(fin.wait(10000))
        self.assertEqual(fin.at(0), [130])
        self.assertTrue(gone(pids['child']))
        self.assertTrue(alive(pids['detached']))

    def test_force_after_grace(self):
        runner.GRACE_MS = 1000; runner.PORTER = [FAKE, '--tree', '--ignore-stop', '--']
        p = runner.Porter(); fin = QSignalSpy(p.finished)
        pids = self.tree(p)
        t = time.time(); p.stop()
        self.assertTrue(until(lambda: fin.count(), 6000))
        self.assertLess(time.time() - t, 6)
        self.assertEqual(fin.at(0), [130])
        self.assertTrue(gone(pids['child']))

    def test_events_before_finished(self):
        p = runner.Porter(); seq = []
        p.finished.connect(lambda c: seq.append(('finished', c)))
        self.tree(p, seq)
        p.stop()
        self.assertTrue(until(lambda: any(isinstance(x, tuple) for x in seq), 10000))
        QTest.qWait(500)
        self.assertEqual(seq[-1], ('finished', 130))
        self.assertIn({'ev': 'say', 'msg': '[RED] interrupted'}, seq[:-1])
        self.assertEqual(sum(isinstance(x, tuple) for x in seq), 1)

    def test_stop_when_idle_is_noop(self):
        p = runner.Porter(); fin, ev = QSignalSpy(p.finished), QSignalSpy(p.event)
        p.stop(); QTest.qWait(200)
        self.assertEqual((fin.count(), ev.count()), (0, 0))

    def test_stop_after_exit_is_noop(self):
        runner.PORTER = [FAKE, '--exit', '0', '--']
        p = runner.Porter(); fin = QSignalSpy(p.finished)
        p.start(['port', 'x'])
        self.assertTrue(fin.wait(10000))
        self.assertEqual(fin.at(0), [0])
        p.stop(); QTest.qWait(500)
        self.assertEqual(fin.count(), 1)

    def test_port_tab_status(self):
        w = app.Window(); self.addCleanup(w.deleteLater)
        port = w.port; fin = QSignalSpy(port.porter.finished); evs = []
        port.porter.event.connect(evs.append)
        port.run(['port', 'x', '--progress', 'json'])
        self.assertTrue(until(lambda: any(e.get('ev') == 'pids' for e in evs), 10000))
        pids = next(e for e in evs if e.get('ev') == 'pids'); self.addCleanup(reap, pids['detached'])
        port.cancel()
        self.assertEqual(port.step.text(), 'stopping…')
        self.assertFalse(port.cancel_btn.isEnabled())
        self.assertNotIn('cancelled', port.log.toPlainText())
        self.assertTrue(fin.wait(10000))
        self.assertEqual(port.step.text(), 'cancelled')
        self.assertEqual(port.log.toPlainText().splitlines()[-1], 'cancelled')


if __name__ == '__main__': unittest.main()
