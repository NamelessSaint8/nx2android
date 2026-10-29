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
    from PySide6.QtTest import QSignalSpy
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


if __name__ == '__main__': unittest.main()
