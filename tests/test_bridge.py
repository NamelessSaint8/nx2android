# The GUI side of the bridge (gui/runner.py, gui/app.py), headless (QT_QPA_PLATFORM=offscreen): a failed run shows its cause and opens its log,
# Cancel stops the whole tree and says "cancelled" only once it is gone, closing the window mid-run asks first. A stand-in porter
# (tests/fixtures/bridge/fake_porter.py, via runner.PORTER) plays the long runs; the Errors tests run the real porter on an empty folder.
import json, os, re, subprocess, sys, tempfile, time, unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
REPO = Path(__file__).resolve().parent.parent
FAKE = str(REPO / 'tests/fixtures/bridge/fake_porter.py')
sys.path.insert(0, str(REPO))

# a declared floor, not a missing module, so it skips in CI too: PySide6 6.12's refcount bug on True aborts 3.11
OLD = sys.version_info < (3, 12)
MISSING = None
for _m in () if OLD else ('PySide6.QtWidgets', 'lz4.block', 'capstone'):
    try: __import__(_m)
    except ModuleNotFoundError:
        if os.environ.get('CI'): raise   # CI installs the lock: a missing module there is a failure
        MISSING = MISSING or _m.split('.')[0]

HOME = tempfile.mkdtemp()
if not (OLD or MISSING):
    from PySide6.QtTest import QSignalSpy, QTest
    from PySide6.QtCore import QProcess
    from PySide6.QtWidgets import QApplication, QMessageBox
    from gui import app, runner
    from porter import paths
APP = None


def setUpModule():
    global APP
    if OLD: raise unittest.SkipTest('the GUI needs Python 3.12+ (PySide6 6.12 refcount bug on 3.11)')
    if MISSING: raise unittest.SkipTest(f'{MISSING} is not installed (python -m pip install -r requirements.txt)')
    os.environ['NX2A_HOME'] = HOME   # here, not at import: discovery imports other test modules that set their own
    APP = QApplication.instance() or QApplication([])
    APP.setQuitOnLastWindowClosed(False)   # the Close tests close windows; the module's loop goes on


def wait(signal, ms):   # the first emission's arguments, or None
    spy = QSignalSpy(signal)
    return spy.at(0) if spy.count() or spy.wait(ms) else None


def until(pred, ms):   # spin the event loop until pred() holds
    end = time.time() + ms / 1000
    while not pred() and time.time() < end: QTest.qWait(20)
    return pred()


def window(test):   # a Window whose start-up one-shots (doctor, devices, profiles) have answered: one destroyed mid-call is noise
    w = app.Window(); test.addCleanup(w.deleteLater)
    settled = lambda: until(lambda: all(p.state() == QProcess.NotRunning for p in w.findChildren(QProcess)), 30000)
    settled(); test.addCleanup(settled)   # and again before it goes (a failed download re-runs doctor)
    return w


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
        w = window(self)
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

    def stand_in(self, *opts):   # a Window whose start-up one-shots the stand-in answers; then runner.PORTER is fake_porter.py with opts
        runner.PORTER = [FAKE, '--']; w = window(self)
        runner.PORTER = [FAKE, *opts, '--']
        return w

    def card(self, w):   # inspect an empty folder; the card once the call has answered
        w.port.folder.setText(tempfile.mkdtemp()); w.port.inspect()
        self.assertTrue(until(lambda: 'Reading' not in w.port.card.text(), 10000), w.port.card.text())
        return w.port.card.text()

    def test_doctor_crash_shows_stderr(self):
        w = self.stand_in('--stderr', 'Traceback (most recent call last):\\nValueError: <boom>', '--exit', '1')
        self.assertTrue(hasattr(w.setup, 'check_msg'), 'SetupTab has no check_msg')
        with mock.patch.object(w, 'set_ready') as ready:
            w.setup.check()
            self.assertTrue(until(lambda: 'Retry' in w.setup.check_msg.text(), 10000))
        self.assertIn('ValueError: &lt;boom&gt;', w.setup.check_msg.text())
        self.assertIn('href="retry"', w.setup.check_msg.text())
        ready.assert_called_with(False)

    def test_error_document(self):
        fixture = REPO / 'tests/fixtures/bridge/inspect_error.json'
        w = self.stand_in('--fixture', str(fixture), '--exit', '2')
        msg = json.loads(fixture.read_text())['error'].replace('<', '&lt;').replace('>', '&gt;')
        self.assertIn(msg, self.card(w))

    def test_empty_answer(self):
        w = self.stand_in(); runner.PORTER = ['-c', '']
        text = self.card(w)
        self.assertIn('porter gave no answer', text)
        self.assertIn('href="retry"', text)

    def test_undecodable_stderr(self):
        w = self.stand_in('--stderr', '\\xff<b>', '--exit', '1')
        with mock.patch.object(sys, 'excepthook') as hook:
            text = self.card(w)
        hook.assert_not_called()
        self.assertIn('&lt;b&gt;', text)

    def test_failed_to_start(self):
        got = []
        with mock.patch.object(runner.sys, 'executable', str(Path(tempfile.mkdtemp()) / 'no-python')):
            runner.call_json(None, ['doctor', '--json'], lambda *a: got.append(a))
        self.assertTrue(until(lambda: got, 5000)); QTest.qWait(200)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0][:2], (None, -1))
        self.assertTrue(got[0][2])

    def test_concurrent_calls(self):   # each call has its own timer: a hung one does not hold up a quick one
        pf = Path(tempfile.mkdtemp()) / 'pids.json'; seq = []
        runner.PORTER = [FAKE, '--hang', '--pid-file', str(pf), '--']
        runner.call_json(None, ['devices', '--json'], lambda o, c, f: seq.append(('hung', o, f)), timeout=1)
        runner.PORTER = [FAKE, '--']
        runner.call_json(None, ['devices', '--json'], lambda o, c, f: seq.append(('quick', o, f)))
        self.assertTrue(until(lambda: len(seq) == 2, 6000), seq)
        if pf.is_file(): pids = json.loads(pf.read_text()); self.addCleanup(reap, pids['detached']); self.addCleanup(reap, pids['child'])
        self.assertEqual(seq[0], ('quick', [], None))
        self.assertEqual((seq[1][0], seq[1][1], seq[1][2]['timeout']), ('hung', None, 1))

    def test_devices_and_games(self):
        w = self.stand_in('--stderr', 'adb: <bad> cable', '--exit', '1')
        w.port.refresh_devices()
        self.assertTrue(until(lambda: w.port.device.itemText(0).startswith('porter: '), 10000), w.port.device.itemText(0))
        self.assertIn('adb: <bad> cable', w.port.device.itemText(0))
        self.assertIn('adb: <bad> cable', w.port.device.itemData(0, app.Qt.ToolTipRole) or '')
        self.assertEqual(w.port.device.itemData(0), '')
        self.assertTrue(hasattr(w.games, 'note'), 'GamesTab has no note')
        w.games.load()
        self.assertTrue(until(lambda: 'Retry' in w.games.note.text(), 10000))
        self.assertIn('adb: &lt;bad&gt; cable', w.games.note.text())
        with mock.patch.object(QMessageBox, 'warning', side_effect=AssertionError('a dialog')) as warn:
            w.setup.download()
            self.assertTrue(until(lambda: 'Retry' in w.setup.dl_step.text(), 10000), w.setup.dl_step.text())
        warn.assert_not_called()
        self.assertIn('adb: &lt;bad&gt; cable', w.setup.dl_step.text())
        with mock.patch.object(app, 'call_json') as call:
            w.setup.dl_step.linkActivated.emit('retry')
        self.assertEqual(call.call_count, 1)

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
        w = window(self)
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



class Close(Fake):
    def window(self):
        w = window(self); w.show()
        for porter in (w.port.porter, w.setup.fetch): self.addCleanup(self.finish, porter)
        return w

    def finish(self, porter):   # a run a test left going
        if porter.running():
            fin = QSignalSpy(porter.finished); porter.stop(); fin.wait(10000)

    def ask(self, w, answer):
        m = mock.patch.object(w, 'ask_stop', create=True, return_value=answer); self.addCleanup(m.stop); return m.start()

    def running_port(self, w, args):
        evs = []; w.port.porter.event.connect(evs.append)
        w.port.run(args)
        self.assertTrue(until(lambda: any(e.get('ev') == 'pids' for e in evs), 10000))
        pids = next(e for e in evs if e.get('ev') == 'pids'); self.addCleanup(reap, pids['detached'])
        return pids

    def test_idle_close_quits(self):
        w = self.window(); ask = self.ask(w, True)
        self.assertTrue(w.close())
        ask.assert_not_called()

    def test_keep_running(self):
        w = self.window(); self.ask(w, False)
        self.running_port(w, ['port', 'x', '--progress', 'json'])
        self.assertFalse(w.close())
        self.assertTrue(w.port.porter.running())
        self.assertTrue(w.isVisible())

    def test_stop_and_quit(self):
        w = self.window(); self.ask(w, True)
        pids = self.running_port(w, ['port', 'x', '--progress', 'json'])
        fin = QSignalSpy(w.port.porter.finished)
        self.assertFalse(w.close())
        self.assertEqual(w.port.step.text(), 'stopping…')
        self.assertTrue(w.isVisible())
        self.assertTrue(fin.wait(10000))
        self.assertTrue(until(lambda: not w.isVisible(), 3000))
        self.assertTrue(gone(pids['child']))

    def test_install_wording(self):
        for args, installing in ((['install', 'd', '--apk', 'a.apk', '--progress', 'json'], True), (['port', 'x', '--progress', 'json', '--install'], True),
                                 (['port', 'x', '--progress', 'json'], False)):
            with self.subTest(args=args):
                w = self.window(); ask = self.ask(w, False)
                self.running_port(w, args)
                self.assertFalse(w.close())
                ask.assert_called_once_with(installing)
                self.finish(w.port.porter)

    def test_download_counts(self):
        w = self.window(); ask = self.ask(w, False)
        w.setup.fetch.start(['tools', '--download', '--progress', 'json'])
        self.assertTrue(until(lambda: w.setup.fetch.pgid, 10000))
        self.assertFalse(w.close())
        ask.assert_called_once_with(False)

    def test_download_failure_inline(self):
        runner.PORTER = [FAKE, '--']   # the Window's own one-shots
        w = self.window()
        runner.PORTER = ['-c', "import json, os, sys; d = os.path.join(os.environ['NX2A_HOME'], 'logs'); os.makedirs(d, exist_ok=True); "
                               "p = os.path.join(d, 'replay-tools.log'); open(p, 'w').close(); print(json.dumps({'ev': 'log', 'path': p})); "
                               "print(json.dumps({'ev': 'error', 'msg': 'bad <thing> & co', 'type': 'FetchError', 'log': p})); sys.exit(1)"]
        fin = QSignalSpy(w.setup.fetch.finished)
        with mock.patch.object(QMessageBox, 'warning', side_effect=AssertionError('a dialog')) as warn:
            w.setup.fetch.start(['tools', '--download', '--progress', 'json'])
            self.assertTrue(fin.wait(10000))
            QTest.qWait(50)
        warn.assert_not_called()
        text = w.setup.dl_step.text()
        self.assertIn('bad &lt;thing> &amp; co', text)
        self.assertIn('<a href="log">Open log</a>', text)
        with mock.patch.object(app, 'QDesktopServices') as ds:
            w.setup.dl_step.linkActivated.emit('log')
        self.assertEqual(Path(ds.openUrl.call_args[0][0].toLocalFile()), Path(HOME) / 'logs/replay-tools.log')


class Timeout(Fake):   # a one-shot that never answers is killed at its own limit, with its children, and the view offers Retry
    def hung(self, args, done, timeout=1, parent=None):   # a one-shot that holds a --tree; its pids once the stand-in wrote them
        pf = Path(tempfile.mkdtemp()) / 'pids.json'
        runner.PORTER = [FAKE, '--hang', '--pid-file', str(pf), '--']
        runner.call_json(parent, args, done, timeout=timeout)
        self.assertTrue(until(pf.is_file, 10000))
        until(lambda: pf.read_text(), 2000); pids = json.loads(pf.read_text())
        self.addCleanup(reap, pids['detached']); self.addCleanup(reap, pids['child'])
        return pids

    def test_kills_tree_at_limit(self):
        got = []
        pids = self.hung(['inspect', 'x', '--json'], lambda *a: got.append(a))
        self.assertTrue(until(lambda: got, 4000))
        self.assertEqual(len(got), 1)
        obj, _code, fail = got[0]
        self.assertIsNone(obj)
        self.assertEqual(fail['timeout'], 1)
        self.assertTrue(gone(pids['child']))

    def test_inspect_card_retry(self):
        runner.PORTER = [FAKE, '--']   # the Window's own one-shots
        w = window(self); port = w.port
        port.on_inspect(None, -1, {'timeout': 60, 'error': '', 'stderr': ''})
        self.assertIn("didn't answer in 60 s", port.card.text())
        self.assertIn('href="retry"', port.card.text())
        self.assertNotIn('No game found', port.card.text())
        port.folder.setText(tempfile.mkdtemp())
        with mock.patch.object(app, 'call_json') as call:
            port.card.linkActivated.emit('retry')
        self.assertEqual(call.call_count, 1)
        self.assertNotIn('href="retry"', port.card.text())

    def test_owner_gone_mid_call(self):   # the app quits while a one-shot runs: no callback into destroyed views, no RuntimeError, no leftover child
        import shiboken6
        from PySide6.QtWidgets import QWidget
        owner = QWidget(); got = []
        pids = self.hung(['doctor', '--json'], lambda *a: got.append(a), timeout=30, parent=owner)
        with mock.patch.object(sys, 'excepthook') as hook:
            shiboken6.delete(owner); QTest.qWait(300)
        hook.assert_not_called()
        self.assertEqual(got, [])
        self.assertTrue(gone(pids['child']))

    def test_default_limits(self):
        self.assertEqual(runner.TIMEOUTS, {'devices': 15, 'doctor': 30, 'inspect': 60, 'profiles': 20, 'tools': 60})


FIXTURES = REPO / 'tests/fixtures/bridge'


class Replay(unittest.TestCase):   # golden JSON-lines streams (tests/fixtures/bridge/record.py) through runner.Porter: the protocol the GUI parses
    def setUp(self):
        keep = runner.PORTER; self.addCleanup(setattr, runner, 'PORTER', keep)

    def replay(self, name, code=0):   # the events and the exit code runner.Porter gives for the fixture
        runner.PORTER = [FAKE, '--fixture', str(FIXTURES / name), '--exit', str(code), '--']
        p = runner.Porter(); evs = []; p.event.connect(evs.append); fin = QSignalSpy(p.finished)
        p.start(['port'])
        self.assertTrue(fin.wait(10000))
        return evs, fin.at(0)[0]

    def golden(self, name):   # every non-blank line is one JSON object
        rows = [json.loads(ln) for ln in (FIXTURES / name).read_text(encoding='utf-8').splitlines() if ln.strip()]
        self.assertTrue(rows and all(isinstance(r, dict) for r in rows), name)
        return rows

    def test_port_ok(self):
        evs, code = self.replay('port_ok.jsonl')
        self.assertEqual((evs, code), (self.golden('port_ok.jsonl'), 0))
        self.assertEqual(evs[0]['ev'], 'log')
        self.assertEqual(evs[-1]['ev'], 'result')
        self.assertTrue({'apk', 'data', 'log'} <= evs[-1].keys())

    def test_port_build_error(self):
        evs, code = self.replay('port_build_error.jsonl', 1)
        self.assertEqual((evs, code), (self.golden('port_build_error.jsonl'), 1))
        self.assertEqual((evs[-1]['ev'], evs[-1]['type']), ('error', 'BuildError'))

    def test_install_ok(self):
        evs, code = self.replay('install_ok.jsonl')
        self.assertEqual((evs, code), (self.golden('install_ok.jsonl'), 0))
        kinds = [e['ev'] for e in evs if e['ev'] in ('stage', 'step', 'stage_end')]
        self.assertEqual((kinds[0], kinds[-1]), ('stage', 'stage_end'))
        self.assertIn('step', kinds)
        self.assertTrue(all(e['name'] == 'install' for e in evs if e['ev'] in ('stage', 'step', 'stage_end')))

    def test_edge_lines(self):   # a non-JSON line and a JSON array become say, a blank line nothing, a last line with no newline still arrives
        evs, code = self.replay('edge.jsonl')
        self.assertEqual(evs, [{'ev': 'say', 'msg': 'porter 1.2 starting'}, {'ev': 'say', 'msg': '["not", "an", "event"]'}, {'ev': 'say', 'msg': 'last'}])
        self.assertEqual(code, 0)

    def test_fixtures_are_scrubbed(self):   # the fixtures are public: no user paths, no key material
        bad = re.compile(r'/Users/|/home/|C:\\\\Users|C:\\Users|AppData|prod\.keys\s*[=:]\s*[0-9a-fA-F]{16}|\b[0-9a-fA-F]{32}\b')
        for f in sorted(FIXTURES.iterdir()):
            if f.is_file():
                with self.subTest(f.name): self.assertIsNone(bad.search(f.read_text(encoding='utf-8', errors='replace')), f.name)


if __name__ == '__main__': unittest.main()
