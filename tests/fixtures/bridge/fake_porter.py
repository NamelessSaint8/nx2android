# Stands in for `python -m porter` in tests/test_bridge.py (runner.PORTER points at it): fake_porter.py [options] -- <porter arguments>.
# A one-shot command (doctor, devices, profiles, tools, inspect) prints [] so a Window starts cleanly. --tree sets up the stop channel with
# porter.procs.setup exactly as porter does, then holds a child (inside the run's tree) and a detached process (outside it) until it is stopped.
#   --tree          the tree above; prints {"ev":"pids","child","detached"} and a stage event, then waits
#   --ignore-stop   the run (and its child) ignore the stop request, so only the GUI's force kill ends them
#   --exit N        exit code when not --tree;  --stderr TEXT  a line on stderr first
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
    ap.add_argument('--tree', action='store_true'); ap.add_argument('--ignore-stop', action='store_true')
    ap.add_argument('--exit', type=int, default=0); ap.add_argument('--stderr')
    o, cmd = ap.parse_args(argv[:i] if i >= 0 else []), argv[i + 1:]
    if o.stderr: print(o.stderr, file=sys.stderr, flush=True)
    if cmd and cmd[0] in ONE_SHOT and not (cmd[0] == 'tools' and '--download' in cmd): print('[]', flush=True); return 0
    if not o.tree: return o.exit
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
    out({'ev': 'pids', 'child': child.pid, 'detached': detached.pid})
    out({'ev': 'stage', 'k': 1, 'n': 1, 'name': 'waiting'})
    try: time.sleep(600)
    except KeyboardInterrupt:
        out({'ev': 'say', 'msg': '[RED] interrupted'}); return 130
    return 0


if __name__ == '__main__': sys.exit(main())
