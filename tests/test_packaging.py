# packaging/build_bundle.py and packaging/glibc_floor.py: the asset names of the four bundles (D-10), the host-to-target mapping, which nxnative files
# a bundle carries, the engine id porter/paths.py keys its copy by, and the glibc floor of a Linux bundle. Stdlib only: nothing here runs PyInstaller.
import sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'packaging'))
import build_bundle, glibc_floor   # noqa: E402


class Names(unittest.TestCase):
    def test_asset_names(self):
        a = build_bundle.asset_name
        self.assertEqual(a('0.1.2-ns.1', 'macos', 'arm64'), 'nx2android-0.1.2-ns.1-macos-arm64.dmg')
        self.assertEqual(a('0.1.2-ns.1', 'windows', 'x64'), 'nx2android-0.1.2-ns.1-windows-x64.zip')
        self.assertEqual(a('0.1.2-ns.1', 'linux', 'x64'), 'nx2android-0.1.2-ns.1-linux-x64.tar.gz')
        self.assertEqual(a('0.1.2-ns.1', 'linux', 'arm64'), 'nx2android-0.1.2-ns.1-linux-arm64.tar.gz')

    def test_target_mapping(self):
        t = build_bundle.target
        self.assertEqual(t('darwin', 'arm64'), ('macos', 'arm64'))
        self.assertEqual(t('win32', 'AMD64'), ('windows', 'x64'))
        self.assertEqual(t('linux', 'x86_64'), ('linux', 'x64'))
        self.assertEqual(t('linux', 'aarch64'), ('linux', 'arm64'))


class Bundle(unittest.TestCase):
    def test_dmsh_xlate_bin_excluded(self):
        keep = 'nxnative/dm/games/010015100B514000/game.tsv'
        self.assertEqual(build_bundle.bundled(['nxnative/dm/gfx/tools/dmsh_xlate_bin/Gommon.dll', keep]), [keep])

    def test_engine_id_stable(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'a').write_bytes(b'one'); (Path(d) / 'b').write_bytes(b'two')
            first = build_bundle.engine_id(d, ['a', 'b'])
            self.assertEqual(first, build_bundle.engine_id(d, ['b', 'a']))
            self.assertRegex(first, r'^[0-9a-f]{16}$')   # porter/paths.py _engine() takes only an alphanumeric id
            (Path(d) / 'b').write_bytes(b'twO')
            self.assertNotEqual(first, build_bundle.engine_id(d, ['a', 'b']))


OBJDUMP = {
    'libQt6Gui.so.6': '0000000000000000      DF *UND*  0000000000000000 (GLIBC_2.17) memcpy\n0000000000000000      DF *UND*  0000000000000000 (GLIBC_2.34) pthread_create\n',
    'nx2android': '0000000000000000      DF *UND*  0000000000000000 (GLIBC_2.28) fcntl64\n',
}


class Glibc(unittest.TestCase):
    def test_floor_parse(self):
        need = glibc_floor.need(OBJDUMP)
        self.assertEqual(max(need, default=None), (2, 34))
        self.assertEqual(need.get((2, 34)), {'libQt6Gui.so.6'})
        self.assertEqual(glibc_floor.main(['glibc_floor.py', 'dist/nx2android', '2.34'], OBJDUMP), 0)
        self.assertEqual(glibc_floor.main(['glibc_floor.py', 'dist/nx2android', '2.33'], OBJDUMP), 1)


if __name__ == '__main__':
    unittest.main()
