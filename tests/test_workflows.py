# The repository's supply-chain and CI rules, checked on the committed files (python -m unittest tests.test_workflows)
import os, re, unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO / '.github' / 'workflows'
LOCKS = ('requirements.txt', 'requirements-build.txt', 'requirements-dev.txt')


def entries(path):
    # (name line, whole entry) per requirement: backslash-continued lines joined, comments skipped
    out = []
    for ln in (REPO / path).read_text(encoding='utf-8').splitlines():
        s = ln.strip()
        if not s or s.startswith('#'): continue
        if re.match(r'[A-Za-z0-9]', s): out.append([s, s])
        elif out: out[-1][1] += ' ' + s
    return [tuple(e) for e in out]


class Lock(unittest.TestCase):
    def test_every_entry_is_hashed(self):
        for f in LOCKS:
            es = entries(f)
            self.assertGreaterEqual(len(es), 5, f)
            for name, text in es: self.assertIn('--hash=sha256:', text, f'{f}: {name}')

    def test_arch_modules(self):
        req = (REPO / 'requirements.txt').read_text(encoding='utf-8').lower()
        for m in ('lz4', 'capstone', 'pillow', 'pyside6'): self.assertIn(m, req)

    def test_generated_by_uv(self):
        for f in LOCKS:
            head = '\n'.join((REPO / f).read_text(encoding='utf-8').splitlines()[:5])
            for w in ('uv pip compile', '--universal', '--generate-hashes'): self.assertIn(w, head, f)

    def test_build_tools_apart(self):
        names = lambda f: [n for n, _ in entries(f)]
        self.assertFalse([n for n in names('requirements.txt') if n.startswith('pyinstaller==')])
        self.assertTrue([n for n in names('requirements-build.txt') if n.startswith('pyinstaller==')])

    def test_dev_apart(self):
        pkgs = lambda f: {re.match(r'[A-Za-z0-9._-]+', n).group().lower() for n, _ in entries(f)}
        self.assertTrue({'numpy', 'av'} <= pkgs('requirements-dev.txt'))
        self.assertFalse({'numpy', 'av'} & pkgs('requirements.txt'))


class Ci(unittest.TestCase):   # every workflow file, so the release workflow is held to the same pin, trigger, script and checkout rules
    @classmethod
    def setUpClass(cls):
        try: import yaml
        except ModuleNotFoundError:
            if os.environ.get('CI'): raise   # CI installs the lock: a missing module there is a failure
            raise unittest.SkipTest('yaml is not installed (python -m pip install -r requirements.txt)')
        cls.files = sorted(p for p in WORKFLOWS.glob('*') if p.suffix in ('.yml', '.yaml'))
        cls.wf = {p.name: yaml.safe_load(p.read_text(encoding='utf-8')) for p in cls.files}

    def jobs(self): return [(f, n, j) for f, w in self.wf.items() for n, j in (w.get('jobs') or {}).items()]
    def steps(self): return [(f'{f} {n}', s) for f, n, j in self.jobs() for s in j.get('steps') or []]

    def test_actions_pinned(self):
        self.assertIn('fork-ci.yml', self.wf)
        uses = [(f'{f} {n}', j['uses']) for f, n, j in self.jobs() if 'uses' in j] + [(w, s['uses']) for w, s in self.steps() if 'uses' in s]
        self.assertTrue(uses)
        for where, u in uses: self.assertRegex(u, r'^[\w.-]+/[\w.-]+(/[\w./-]+)?@[0-9a-f]{40}$', where)

    def test_no_privileged_pr_trigger(self):
        bad = 'pull_request' + '_target'
        for f, w in self.wf.items():
            on = w.get('on', w.get(True))   # PyYAML reads the bare on: key as the boolean True
            self.assertNotIn(bad, on if isinstance(on, (dict, list)) else [on], f)
            self.assertNotIn(bad, (WORKFLOWS / f).read_text(encoding='utf-8'), f)

    def test_run_scripts_take_no_expressions(self):
        for where, s in self.steps():
            if 'run' in s: self.assertNotRegex(s['run'], r'\$\{\{\s*(github|secrets)\.', where)

    def test_checkout_without_credentials(self):
        for where, s in self.steps():
            if s.get('uses', '').startswith('actions/checkout@'): self.assertIs((s.get('with') or {}).get('persist-credentials'), False, where)

    def test_ci_matrix(self):
        w = self.wf['fork-ci.yml']; on = w.get('on', w.get(True))
        self.assertTrue({'push', 'pull_request'} <= set(on))
        self.assertEqual(w['permissions'], {'contents': 'read'})
        self.assertIn('github.ref', w['concurrency']['group']); self.assertIs(w['concurrency']['cancel-in-progress'], True)
        j = w['jobs']['test']
        self.assertIs(j['strategy']['fail-fast'], False)
        hosts = {(m['os'], str(m['python'])) for m in j['strategy']['matrix']['include']}
        self.assertEqual(hosts, {(h, '3.14') for h in ('windows-2025', 'macos-15', 'ubuntu-22.04', 'ubuntu-24.04-arm')} | {('ubuntu-22.04', '3.11')})
        self.assertEqual({**w.get('env', {}), **j.get('env', {})}.get('QT_QPA_PLATFORM'), 'offscreen')
        runs = [s['run'] for s in j['steps'] if 'run' in s]
        self.assertTrue([r for r in runs if '--require-hashes -r requirements.txt' in r])
        self.assertTrue([r for r in runs if 'unittest discover' in r])
        self.assertTrue([r for r in runs if 'Ran [1-9]' in r], 'a run that collects no tests must fail')


if __name__ == '__main__':
    unittest.main()
