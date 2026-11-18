import json
from pathlib import Path
import tempfile
import unittest

from sync_version import sync


class VersionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / 'firmware/main').mkdir(parents=True)
        (self.root / 'firmware/main/main.c').write_text('void app_main(void) {}\n')
        (self.root / 'version.json').write_text(json.dumps({'sw_version': '1.1.0', 'source_sha256': ''}))

    def test_changed_build_increments_once_and_both_consumers_agree(self):
        first = sync(self.root)
        header = self.root / 'firmware/main/sw_version.h'
        timestamp = header.stat().st_mtime_ns
        self.assertEqual(sync(self.root), first)
        self.assertEqual(header.stat().st_mtime_ns, timestamp)
        (self.root / 'firmware/main/main.c').write_text('void app_main(void) { /* changed */ }\n')
        second = sync(self.root)
        self.assertEqual(second['sw_version'], '1.1.1')
        self.assertIn('"1.1.1"', header.read_text())
        self.assertIn('"1.1.1"', (self.root / 'frontend/src/sw_version.ts').read_text())
        self.assertEqual(sync(self.root, check=True), second)

    def test_stale_source_rejected_and_missing_output_repaired_without_bump(self):
        first = sync(self.root)
        header = self.root / 'firmware/main/sw_version.h'
        header.unlink()
        with self.assertRaises(ValueError):
            sync(self.root, check=True)
        self.assertEqual(sync(self.root), first)
        (self.root / 'firmware/main/main.c').write_text('changed')
        with self.assertRaises(ValueError):
            sync(self.root, check=True)
        self.assertEqual(json.loads((self.root / 'version.json').read_text()), first)

    def test_explicit_release_bump_and_line_endings(self):
        sync(self.root)
        (self.root / 'firmware/main/main.c').write_bytes(b'void app_main(void) {}\r\n')
        self.assertEqual(sync(self.root)['sw_version'], '1.1.0')
        self.assertEqual(sync(self.root, bump=True)['sw_version'], '1.1.1')


if __name__ == '__main__':
    unittest.main()
