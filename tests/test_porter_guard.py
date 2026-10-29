# TEST-02: tests.test_porter's import guard. A missing engine module is a named skip locally and a failure under CI.
import os, subprocess, sys, unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# sys.modules[name] = None makes `import lz4` raise ModuleNotFoundError with e.name == 'lz4', as a missing install does
BOOT = "import sys, unittest; sys.modules['lz4'] = None; unittest.main(module=None, argv=['x', '-v', 'tests.test_porter'])"


def run(ci):
    env = {k: v for k, v in os.environ.items() if k != 'CI'}   # GitHub Actions sets CI=true; the local case must not see it
    if ci: env['CI'] = '1'
    return subprocess.run([sys.executable, '-c', BOOT], cwd=REPO, env=env, capture_output=True, text=True, timeout=300)


class PorterGuard(unittest.TestCase):
    def test_missing_lz4_is_a_named_skip_locally(self):
        r = run(False); out = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, out)
        self.assertIn('lz4 is not installed', out)
        self.assertNotIn('ModuleNotFoundError', out)

    def test_missing_lz4_fails_under_ci(self):
        r = run(True); out = r.stdout + r.stderr
        self.assertNotEqual(r.returncode, 0, out)
        self.assertIn('ModuleNotFoundError', out)
        self.assertNotIn('lz4 is not installed', out)


if __name__ == '__main__': unittest.main()
