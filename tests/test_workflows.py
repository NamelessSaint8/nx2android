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


class Release(unittest.TestCase):   # fork-release.yml: who can start it, where the signing secrets reach, and what a draft needs
    @classmethod
    def setUpClass(cls):
        Ci.setUpClass.__func__(cls)
        cls.w = cls.wf.get('fork-release.yml') or {}
        cls.text = (WORKFLOWS / 'fork-release.yml').read_text(encoding='utf-8')

    def job(self, n): return self.w['jobs'][n]
    def runs(self, n): return [s['run'] for s in self.job(n).get('steps') or [] if 'run' in s]
    def ran(self, n, word): return any(word in r for r in self.runs(n))

    def test_triggers(self):
        self.assertIn('fork-release.yml', self.wf)
        on = self.w.get('on', self.w.get(True))
        self.assertEqual(on['push'], {'tags': ['v*-ns.*']})   # upstream's v0.1.x tags never start it (D-10)
        self.assertIn('workflow_dispatch', on)
        self.assertFalse([k for k in on if 'pull_request' in k])
        self.assertNotIn('pull_request', self.text)

    def test_secrets_scoped(self):
        import yaml
        with_secrets = [n for n, j in self.w['jobs'].items() if 'secrets.' in yaml.safe_dump(j)]
        self.assertEqual(with_secrets, ['macos'])
        self.assertEqual(self.job('macos').get('environment'), 'release')
        self.assertNotIn('secrets.', yaml.safe_dump({k: v for k, v in self.w.items() if k != 'jobs'}))
        for s in self.job('macos')['steps']:   # secrets enter through step env: only, never with: or a job-wide env
            self.assertNotIn('secrets.', yaml.safe_dump(s.get('with') or {}))
        self.assertNotIn('secrets.', yaml.safe_dump(self.job('macos').get('env') or {}))

    def test_write_scope(self):
        self.assertEqual(self.w['permissions'], {'contents': 'read'})
        writers = [n for n, j in self.w['jobs'].items() if 'write' in str(j.get('permissions', ''))]
        self.assertEqual(writers, ['release'])
        r = self.job('release')
        self.assertEqual(r['permissions'], {'contents': 'write'})
        self.assertIn("startsWith(github.ref, 'refs/tags/')", r['if'])
        self.assertEqual(set(r['needs']), {'build', 'macos', 'upstream-diff'})

    def test_macos_signs_and_notarizes(self):
        runs = '\n'.join(self.runs('macos'))
        sub = [ln for ln in runs.splitlines() if 'notarytool submit' in ln]
        self.assertTrue(sub and '--wait' in sub[0])
        for w in ('Accepted', 'notarytool log', 'stapler staple', 'stapler validate', 'spctl -a -t open', 'smoke_bundle.py', 'build_bundle.py', 'RUNNER_TEMP'):
            self.assertIn(w, runs)
        self.assertTrue([s for s in self.job('macos')['steps'] if s.get('if') == 'always()' and 'security delete-keychain' in s.get('run', '')])
        self.assertEqual(self.job('macos')['steps'][-1].get('if'), 'always()')
        self.assertEqual(self.job('macos')['runs-on'], 'macos-15')

    def test_builds_and_floors(self):
        b = self.job('build'); inc = b['strategy']['matrix']['include']
        self.assertIs(b['strategy']['fail-fast'], False)
        self.assertEqual({m['os'] for m in inc}, {'windows-2025', 'ubuntu-22.04', 'ubuntu-24.04-arm'})
        self.assertEqual({m['os']: str(m['floor']) for m in inc if 'floor' in m}, {'ubuntu-22.04': '2.35', 'ubuntu-24.04-arm': '2.39'})
        for w in ('build_bundle.py', 'smoke_bundle.py', 'glibc_floor.py', 'build_bootloader.py', '--require-hashes -r requirements.txt -r requirements-build.txt'):
            self.assertTrue(self.ran('build', w), w)
        self.assertTrue(self.ran('macos', '--require-hashes -r requirements.txt -r requirements-build.txt'))
        floor = [s for s in b['steps'] if 'glibc_floor.py' in s.get('run', '')][0]
        self.assertIn('GITHUB_STEP_SUMMARY', floor['run']); self.assertEqual(floor.get('if'), "runner.os == 'Linux'")
        for n in ('build', 'macos', 'upstream-diff'):
            co = [s for s in self.job(n)['steps'] if s.get('uses', '').startswith('actions/checkout@')][0]
            self.assertEqual(co['with'].get('fetch-depth'), 0, n)   # git describe and the merge base need the history
        self.assertTrue(self.ran('upstream-diff', 'shirai91/nx2android') and self.ran('upstream-diff', 'git diff --stat FETCH_HEAD...HEAD -- nxnative/'))

    def test_release_checks_four_assets(self):
        steps = self.job('release')['steps']
        count = next(i for i, s in enumerate(steps) if all(a in s.get('run', '') for a in ('windows-x64.zip', 'macos-arm64.dmg', 'linux-x64.tar.gz', 'linux-arm64.tar.gz')))
        create = next(i for i, s in enumerate(steps) if 'gh release create' in s.get('run', ''))
        self.assertLess(count, create)
        self.assertIn('-eq 4', steps[count]['run'])
        self.assertIn('--draft', steps[create]['run'])

    def test_concurrency(self):
        c = self.w['concurrency']
        self.assertIn('github.ref', c['group']); self.assertIs(c['cancel-in-progress'], False)


if __name__ == '__main__':
    unittest.main()
