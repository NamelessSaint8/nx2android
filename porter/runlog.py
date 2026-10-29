# The run's own log (D-01, D-02): porter, not the GUI, writes each long command (port, install, tools --download) to <user dir>/logs/<time>-<command>.log,
# as readable text: the lines the GUI's log pane shows (stage start and end with times, say lines, [RED] errors) and the traceback of a crash.
# The protocol gets {"ev":"log","path"} first, {"ev":"error","msg","type","log"} when the run fails and "log" on the result event (docs/ARCHITECTURE.md).
# A one-shot --json command that crashes answers {"error": "<Type>: <message>"} on stdout instead of a bare traceback.
import json, platform, re, sys, threading, time, traceback

from porter import paths

LONG = ('port', 'install')   # and tools --download
RED = re.compile(r'(?:\[\d\d:\d\d:\d\d\] )?\[RED\] (.*)', re.S)   # upstream's say() puts the clock first
_lock = threading.Lock()   # PROG.say runs on other threads too (the stage pollers)
S = {}


def reset():   # the run's state: the open log, its path, the stage it is in, the last [RED] message
    S.clear(); S.update(f=None, path=None, stage='', red='', t0=time.time())


reset()


def _w(text):
    with _lock:
        if S['f']: S['f'].write(text.rstrip('\n') + '\n')


def _close(last):   # the last lines, then the log is closed (a second call does nothing)
    with _lock:
        f, S['f'] = S['f'], None
        if not f: return
        f.write(f'{last}\n[{time.strftime("%H:%M:%S")}] ended after {int(time.time() - S["t0"])} s\n'); f.close()


def _event(a, obj):
    if getattr(a, 'progress', '') == 'json': print(json.dumps({**obj, 't': round(time.time(), 3)}, ensure_ascii=False), flush=True)


def _open(a):
    d = paths.user_dir() / 'logs'; d.mkdir(exist_ok=True)
    stem = f'{time.strftime("%Y%m%d-%H%M%S")}-{a.cmd}'; p, n = d / f'{stem}.log', 1
    while True:   # two runs started in the same second get -2, -3 …
        try: f = open(p, 'x', encoding='utf-8', buffering=1); break   # line-buffered: a killed run's log is whole up to the kill
        except FileExistsError: n += 1; p = d / f'{stem}-{n}.log'
    try: ver = (paths.REPO / 'VERSION').read_text(encoding='utf-8').strip()
    except OSError: ver = 'dev'
    # argv only: the paths of prod.keys and the game, never a file's contents
    f.write(f'$ porter {" ".join(sys.argv[1:])}\nnx2android {ver} · {platform.platform()} · Python {platform.python_version()}\nstarted {time.strftime("%Y-%m-%d %H:%M:%S")}\n')
    S.update(f=f, path=p, t0=time.time())
    return p


def _wrap(prog, nsp):
    """Mirror the progress view into the log: wrapping the instance's public methods keeps the log the same in json, lines, bar and off modes"""
    orig = {n: getattr(prog, n) for n in ('stage', 'end', 'say', '_json')}

    def stage(name, poll=None, step='', **kw):
        orig['stage'](name, poll, step, **kw)
        S['stage'] = name; _w(f'[{nsp.clock()}] [{prog.k}/{prog.n}] {name}' + (f' · {step}' if step else ''))

    def end(summary='', ok=True):
        with prog.lock:
            st = prog.cur; orig['end'](summary, ok)
            if st: _w(f'[{nsp.clock()}] {"✓" if ok else "✗"} [{prog.k}/{prog.n}] {st.name} ({nsp.hms(time.time() - st.t0)})' + (f': {summary}' if summary else ''))

    def say(msg):
        orig['say'](msg); _w(msg)
        m = RED.fullmatch(msg)
        if m: S['red'] = m.group(1)

    def _json(obj):
        if obj.get('ev') == 'result': obj = {**obj, 'log': str(S['path'])}
        orig['_json'](obj)

    prog.stage, prog.end, prog.say, prog._json = stage, end, say, _json
    return lambda: [prog.__dict__.pop(n, None) for n in orig]   # the class's methods again (tests run several commands in one process)


def run(a, fn):
    """Run one command; a long one inside its log"""
    if not (a.cmd in LONG or (a.cmd == 'tools' and getattr(a, 'download', False))):
        if not getattr(a, 'json', False): return fn(a)
        try: return fn(a)
        except Exception as e:   # a missing lz4 used to look like a network failure to the GUI
            traceback.print_exc(); print(json.dumps({'error': f'{type(e).__name__}: {e}'}, ensure_ascii=False), flush=True); return 1
    reset(); p = _open(a)
    _event(a, {'ev': 'log', 'path': str(p)})   # first, so a run that dies at once still names its log
    unwrap = lambda: None
    try:
        from porter.upstream import PROG, nsp   # needs lz4: only the long commands import it here
        unwrap = _wrap(PROG, nsp)
        try: code = fn(a)
        except KeyboardInterrupt: code = 130   # a stop before _with_progress took over
    except Exception as e:
        _w(traceback.format_exc().rstrip())
        _event(a, {'ev': 'error', 'msg': str(e), 'type': type(e).__name__, 'log': str(p)})
        _close(f'[RED] {type(e).__name__}: {e}'); unwrap()
        raise
    unwrap()
    if code == 1:
        _event(a, {'ev': 'error', 'msg': S['red'] or 'failed', 'type': 'BuildError', 'log': str(p)})
        _close('failed')
    elif code == 130: _close(f'[RED] cancelled during {S["stage"] or "the start"}')
    else: _close('done' if code == 0 else f'exit code {code}')
    return code
