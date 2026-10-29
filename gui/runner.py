# Running porter from the GUI: one QProcess per command, its stdout read as JSON. A port (`--progress json`) is a stream of events, one object per line
# (stage, step, progress, stage_end, say, result); the other commands (`--json`) print one JSON document. Stopping ends the whole process tree:
# a port runs dotnet, the rewriter and the NDK's clang as children of its own. POSIX: SIGTERM to the run's session, SIGKILL after GRACE_MS;
# Windows: a "stop" line on stdin (porter ends its own Job Object), porter killed after GRACE_MS. finished comes only once nothing of the run is left.
import json, os, signal, subprocess, sys

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

from porter import paths

PORTER = ['-m', 'porter']   # tests point this at a stand-in (tests/test_bridge.py)
GRACE_MS = 5000   # D-05: about 5 s between the stop request and the force kill


def _env():
    e = QProcessEnvironment.systemEnvironment()
    e.insert('PYTHONIOENCODING', 'utf-8'); e.insert('PYTHONUNBUFFERED', '1'); e.insert('NX2A_GUI', '1')   # porter's stop channel (porter/procs.py)
    if not paths.FROZEN: e.insert('PYTHONPATH', os.pathsep.join(filter(None, [str(paths.REPO), e.value('PYTHONPATH')])))   # cwd no longer finds porter
    return e


def _process(parent, args):
    """Every porter process: run from the player's folder (never the bundle: it is read-only), on POSIX in its own session so a group signal
    reaches dotnet, clang and the shader tools and never the GUI"""
    p = QProcess(parent); p.setProgram(sys.executable); p.setArguments([*PORTER, *args])
    p.setWorkingDirectory(str(paths.user_dir())); p.setProcessEnvironment(_env())
    if os.name != 'nt': p.setUnixProcessParameters(QProcess.UnixProcessFlag.CreateNewSession)
    return p


def _alive(pgid):
    try: os.killpg(pgid, 0); return True
    except (ProcessLookupError, PermissionError): return False


class Porter(QObject):
    """A long porter command (port, install) whose stdout is JSON events"""
    event = Signal(dict)
    finished = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.p, self.buf, self.err, self.pgid, self.stopping, self.ended = None, b'', [], 0, False, True

    def running(self): return not self.ended   # porter or (POSIX) anything left in its session; never stdin closed: porter takes EOF as a stop

    def start(self, args):
        self.p = run = _process(self, args); self.buf, self.err, self.pgid, self.stopping, self.ended = b'', [], 0, False, False
        run.readyReadStandardOutput.connect(self._out)
        run.readyReadStandardError.connect(lambda: self.err.append(bytes(run.readAllStandardError()).decode('utf-8', 'replace')))
        run.started.connect(lambda: setattr(self, 'pgid', run.processId()))   # the session leader: its pid is the group's id
        run.errorOccurred.connect(lambda e: self._failed(run, e))
        run.finished.connect(lambda code, status: self._done(run, code, status))
        run.start()

    def _failed(self, run, e):   # FailedToStart brings no finished signal
        if e != QProcess.FailedToStart or run is not self.p or self.ended: return
        self.ended = True; self.event.emit({'ev': 'error', 'msg': run.errorString()}); self.finished.emit(-1)

    def _kill(self, sig):   # only the run's own session, never group 0 (the GUI's) or 1
        if self.pgid > 1:
            try: os.killpg(self.pgid, sig)
            except (ProcessLookupError, PermissionError): pass

    def stop(self):
        if self.ended or self.stopping: return
        self.stopping = True; run = self.p
        if os.name == 'nt': run.write(b'stop\n')   # D-09: no console group from PySide6, so no CTRL_BREAK
        else:
            self.pgid = self.pgid or run.processId()
            if self.pgid > 1: self._kill(signal.SIGTERM)
            else: run.kill()   # not started yet: nothing else to stop
        QTimer.singleShot(GRACE_MS, lambda: self._force(run))

    def _force(self, run):
        if run is not self.p or self.ended: return   # a later run, or a group id that may be someone else's by now
        if os.name == 'nt':
            if run.state() != QProcess.NotRunning:
                subprocess.run(['taskkill', '/T', '/F', '/PID', str(run.processId())], capture_output=True)   # a porter whose Job Object could not be made
                run.kill()   # closing porter's handle ends its kill-on-close job
        elif _alive(self.pgid): self._kill(signal.SIGKILL)

    def _out(self):
        self.buf += bytes(self.p.readAllStandardOutput())
        *lines, self.buf = self.buf.split(b'\n')
        for ln in lines:
            s = ln.decode('utf-8', 'replace').strip()
            if not s: continue
            try: ev = json.loads(s)
            except ValueError: ev = {'ev': 'say', 'msg': s}
            self.event.emit(ev if isinstance(ev, dict) else {'ev': 'say', 'msg': s})

    def _done(self, run, code, status):
        if run is not self.p or self.ended: return
        self._out()   # every event porter printed comes before finished
        if self.buf.strip(): self.buf += b'\n'; self._out()
        err = ''.join(self.err).strip()
        if code and err: self.event.emit({'ev': 'say', 'msg': '[RED] ' + err.splitlines()[-1]})   # a traceback's last line (the JSON stream has the error's message too)
        crash = status == QProcess.CrashExit
        if self.stopping and (code or crash): code = 130   # a run that exits 0 as Cancel is pressed is done
        elif crash and not code: code = -1   # a crash must not read as success
        self._reap(run, code)

    def _reap(self, run, code):   # POSIX: finished only once the session is empty (a child can outlive porter's own exit)
        if run is not self.p or self.ended: return
        if os.name != 'nt' and self.pgid > 1 and _alive(self.pgid):
            if not self.stopping: self.stopping = True; self._kill(signal.SIGTERM); QTimer.singleShot(GRACE_MS, lambda: self._force(run))
            QTimer.singleShot(200, lambda: self._reap(run, code)); return
        self.ended, self.stopping = True, False   # Windows: porter gone means its kill-on-close job is gone
        self.finished.emit(code)


def call_json(parent, args, done):
    """A short porter command that prints one JSON document: done(obj or None, exit code)"""
    p = _process(parent, args)
    def fin(code, _status):
        out = bytes(p.readAllStandardOutput()).decode('utf-8', 'replace')
        try: obj = json.loads(out)
        except ValueError: obj = None
        done(obj, code); p.deleteLater()
    p.finished.connect(fin); p.start()
    return p
