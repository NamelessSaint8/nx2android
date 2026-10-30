# porter/tls.py, the SSL context of every porter download (UAT G-01-6: the bundled OpenSSL's CA path is the CI runner's, so a player's host loads no CA).
# Standard library only, so it runs on all four CI hosts without the engine modules.
import os, re, ssl, sys, unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from porter import tls   # noqa: E402

CA = str(REPO / 'tests' / 'fixtures' / 'tls' / 'test-ca.pem')
MISSING = str(REPO / 'tests' / 'fixtures' / 'tls' / 'no-such-ca.pem')


def empty(): return ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)   # what the frozen bundles get; SSL_CERT_FILE cannot empty it on Windows, whose system stores load anyway


def cas(c): return c.cert_store_stats()['x509_ca']


class Context(unittest.TestCase):
    def test_empty_default_takes_first_host_file(self):
        with mock.patch.object(tls.ssl, 'create_default_context', empty): self.assertEqual(cas(tls.context(ca_files=(MISSING, CA))), 1)

    def test_no_host_file_stays_verifying(self):
        with mock.patch.object(tls.ssl, 'create_default_context', empty): c = tls.context(ca_files=(MISSING,))
        self.assertEqual(cas(c), 0); self.assertEqual(c.verify_mode, ssl.CERT_REQUIRED); self.assertTrue(c.check_hostname)

    def test_working_default_is_kept(self):
        def working(): c = empty(); c.load_verify_locations(cafile=CA); return c
        isfile = mock.Mock(return_value=True)
        with mock.patch.object(tls.ssl, 'create_default_context', working), mock.patch.object(tls.os.path, 'isfile', isfile): c = tls.context(ca_files=(CA,))
        isfile.assert_not_called(); self.assertEqual(cas(c), 1)

    def test_environment_untouched(self):
        before = dict(os.environ)
        with mock.patch.object(tls.ssl, 'create_default_context', empty): tls.context(ca_files=(MISSING, CA))
        self.assertEqual(dict(os.environ), before)

    def test_every_urlopen_passes_the_context(self):
        calls, bare = 0, []
        for f in sorted((REPO / 'porter').glob('*.py')):
            for n, ln in enumerate(f.read_text(encoding='utf-8').splitlines(), 1):
                code = ln.split('#', 1)[0]
                if not re.search(r'urlopen\(', code): continue
                calls += 1
                if 'context=' not in code: bare.append(f'{f.relative_to(REPO).as_posix()}:{n}')
        self.assertEqual(bare, [], 'urlopen without context=tls.context(): the bundles would load no CA there')
        self.assertGreaterEqual(calls, 4)


if __name__ == '__main__': unittest.main()
