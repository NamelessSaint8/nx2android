# The repository's supply-chain and CI rules, checked on the committed files (python -m unittest tests.test_workflows)
import re, unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
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


if __name__ == '__main__':
    unittest.main()
