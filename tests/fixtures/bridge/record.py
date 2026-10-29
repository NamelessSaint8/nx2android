# Regenerates the golden JSON-lines fixtures that tests/test_bridge.py's Replay feeds through gui/runner.Porter:
#   .venv/bin/python tests/fixtures/bridge/record.py
# port_ok.jsonl and install_ok.jsonl come from porter's own emitter (upstream PROG in json mode inside runlog.run, which adds the log event and result.log),
# driving the stages Port.run (a base game and one update) and install.install go through; port_build_error.jsonl is a real `porter port` of a
# folder that is not there (its first check, the same on every machine; an empty one fails on the tools or prod.keys first, which differ). The protocol only grows additively (no version field), so old fixtures stay valid. Every line has the tmp folder, NX2A_HOME and the
# home folder replaced by <folder>, <home> and <user>. edge.jsonl is written by hand (malformed input on purpose) and is not made here.
import argparse, json, os, subprocess, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PORT = [   # Port.run's stages for a base game plus one update, in order (porter/pipeline.py; extract, rewrite and shader split are upstream's)
    ('build nx_extract', '', None, ''),
    ('extract 1.0.0', '', (3_000_000_000, 'B'), '9,412 files'),
    ('extract 1.1.0', '', None, '1,107 files'),
    ('rewrite', 'checking the inputs', None, '2 module(s)'),
    ('shader split', 'checking the inputs', None, '1,234 shaders'),
    ('Vulkan shaders', 'building the translator', (1234, 'shaders'), '1,234 shaders'),
    ('host', 'NDK android-ndk-r27c', None, '3.1 MB'),
    ('APK', '', None, 'Game.apk, 4.0 MB'),
    ('data pack', 'linking', None, '9,412 files, 2.8 GB'),
]


def _stages(PROG, stages):
    for name, step, count, summary in stages:
        PROG.stage(name, step=step)
        if count:   # a step with a few counts, JSON_INTERVAL apart (a count change alone is held back that long)
            total, unit = count; PROG.set(step=f'{name}: working', total=total, unit=unit, done=0)
            for f in (0.5, 1.0): time.sleep(PROG.JSON_INTERVAL + 0.05); PROG.set(done=int(total * f))
        PROG.end(summary)


def emit(cmd, folder):   # in a child: porter's runlog and emitter, stdout is the stream
    sys.path.insert(0, str(REPO))
    from porter import cli, procs, runlog
    procs.adb_server = lambda: None   # recording never starts the machine's adb server
    from porter import pipeline
    from porter.upstream import PROG, say
    f = Path(folder)
    def port():
        say(f'game folder: {f}'); PROG.plan(len(PORT)); _stages(PROG, PORT)
        pipeline.emit_result({'apk': str(f / 'Game.apk'), 'data': str(f / 'Game-data'), 'title_id': '0100000000010000', 'name': 'Game', 'package': 'com.nx2android.game',
                              'version': '1.1.0', 'display': '1.1.0', 'language': 'en', 'status': 'playable', 'derived': False, 'installed': False})
    def install():
        PROG.plan(1); PROG.stage('install', step='finding the device')
        say('device: Tablet (SERIAL0001), GPU Adreno (TM) 740')
        for step in ('installing Game.apk', 'letting the app create its files folder'): PROG.set(step=step)
        PROG.set(step='pushing the game data', done=0, total=3_000_000_000, unit='B')
        for d, piece in ((1_500_000_000, 12), (3_000_000_000, 24)): time.sleep(PROG.JSON_INTERVAL + 0.05); PROG.set(done=d, note=f'{piece} of 24 pieces')
        PROG.set(step='removing 3 stale files'); PROG.end('Game on Tablet'); say('installed: open "Game" on the device')
    a = argparse.Namespace(cmd=cmd, progress='json', folder=str(f), install=False, json=False)
    return runlog.run(a, lambda _a: cli._with_progress('json', port if cmd == 'port' else install))


def scrub(text, folder, home):
    for p, ph in ((folder, '<folder>'), (home, '<home>'), (str(Path.home()), '<user>')):
        for form in sorted({p, os.path.realpath(p)}, key=len, reverse=True):   # /private/var/… before /var/… (macOS)
            text = text.replace(json.dumps(form)[1:-1], ph).replace(form, ph)   # the JSON-escaped form first (Windows backslashes)
    return text


def record(name, argv, folder, home):
    env = dict(os.environ, NX2A_HOME=home, PYTHONIOENCODING='utf-8'); env.pop('NX2A_GUI', None)
    out = subprocess.run(argv, cwd=REPO, env=env, capture_output=True, encoding='utf-8').stdout
    (HERE / name).write_text(scrub(out, folder, home), encoding='utf-8', newline='\n')
    print(f'{name}: {len(out.splitlines())} lines')


def main():
    if len(sys.argv) == 4 and sys.argv[1] == '--emit': return emit(sys.argv[2], sys.argv[3])
    for name, cmd in (('port_ok.jsonl', 'port'), ('install_ok.jsonl', 'install'), ('port_build_error.jsonl', None)):
        folder, home = tempfile.mkdtemp(), tempfile.mkdtemp()
        argv = [sys.executable, __file__, '--emit', cmd, folder] if cmd else [sys.executable, '-m', 'porter', 'port', str(Path(folder) / 'missing'), '--progress', 'json']
        record(name, argv, folder, home)
    return 0


if __name__ == '__main__': sys.exit(main())
