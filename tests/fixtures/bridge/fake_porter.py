# Stands in for `python -m porter` in tests/test_bridge.py (runner.PORTER points at it): fake_porter.py [options] -- <porter arguments>.
# A one-shot command (doctor, devices, profiles, tools, inspect) prints [] so a Window starts cleanly. --tree sets up the stop channel with
# porter.procs.setup exactly as porter does, then holds a child (inside the run's tree) and a detached process (outside it) until it is stopped.
#   --tree          the tree above; prints {"ev":"pids","child","detached"} and a stage event, then waits (a one-shot still answers [], so a Window starts)
#   --hang          --tree for a one-shot too: it never answers (gui/runner.call_json's timeout)
#   --pid-file P    also write that pids object to P (a one-shot's stdout is its answer, so a test reads the pids from here)
#   --ignore-stop   the run (and its child) ignore the stop request, so only the GUI's force kill ends them
#   --exit N        exit code when not --tree (a one-shot answers [] only with 0);  --stderr TEXT  a line on stderr first, with \n and \xff escapes
#   --fixture FILE  write FILE's bytes to stdout verbatim instead of any answer (the golden replays, tests/fixtures/bridge/*.jsonl)
import argparse, json, os, signal, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from porter import procs

ONE_SHOT = ('doctor', 'devices', 'profiles', 'tools', 'inspect')


def out(obj): print(json.dumps(obj), flush=True)


def sleeper(ignore=False):   # a python that sleeps 60 s, with no hold on porter's pipes
    code = ('import signal; signal.signal(signal.SIGTERM, signal.SIG_IGN); ' if ignore and os.name != 'nt' else '') + 'import time; time.sleep(60)'
    return [sys.executable, '-c', code]


def main():
    argv = sys.argv[1:]
    i = argv.index('--') if '--' in argv else -1
    ap = argparse.ArgumentParser()
    ap.add_argument('--tree', action='store_true'); ap.add_argument('--hang', action='store_true'); ap.add_argument('--ignore-stop', action='store_true')
    ap.add_argument('--exit', type=int, default=0); ap.add_argument('--stderr'); ap.add_argument('--pid-file'); ap.add_argument('--fixture')
    o, cmd = ap.parse_args(argv[:i] if i >= 0 else []), argv[i + 1:]
    if o.stderr: sys.stderr.buffer.write(o.stderr.encode().decode('unicode_escape').encode('latin-1') + b'\n'); sys.stderr.flush()   # raw bytes: a test's \xff
    if o.fixture: sys.stdout.buffer.write(Path(o.fixture).read_bytes()); sys.stdout.flush(); return o.exit
    if cmd and cmd[0] in ONE_SHOT and not o.hang and not (cmd[0] == 'tools' and '--download' in cmd):
        if not o.exit: print('[]', flush=True)
        return o.exit
    if not (o.tree or o.hang): return o.exit
    quiet = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    nt = os.name == 'nt'
    # first, so it is outside the Windows job procs.setup makes; on POSIX its own session
    detached = subprocess.Popen(sleeper(), start_new_session=not nt, creationflags=(subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP) if nt else 0, **quiet)

    def on_stop():
        out({'ev': 'say', 'msg': '[RED] stop requested'})
        if o.ignore_stop: time.sleep(600)

    procs.setup(argparse.Namespace(cmd='port', install=False), on_stop)
    if o.ignore_stop and not nt: signal.signal(signal.SIGTERM, signal.SIG_IGN)
    child = subprocess.Popen(sleeper(o.ignore_stop), **quiet)
    pids = {'ev': 'pids', 'child': child.pid, 'detached': detached.pid}
    if o.pid_file: Path(o.pid_file).write_text(json.dumps(pids))
    out(pids)
    out({'ev': 'stage', 'k': 1, 'n': 1, 'name': 'waiting'})
    try: time.sleep(600)
    except KeyboardInterrupt:
        out({'ev': 'say', 'msg': '[RED] interrupted'}); return 130
    return 0


if __name__ == '__main__': sys.exit(main())
