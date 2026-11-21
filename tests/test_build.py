"""Verify that the router deployment artifact is reproducible and complete."""
import hashlib
import tempfile
from pathlib import Path
from zipfile import ZipFile
import unittest
from scripts.build_hotspot import FILES, build

class BuildTests(unittest.TestCase):
    def test_runtime_zip_is_complete_and_reproducible(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            first, sums = build(Path(a))
            second, _ = build(Path(b))
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with ZipFile(first) as archive:
                self.assertEqual(set(archive.namelist()), set(FILES))
                self.assertNotIn('tests/test_portal.py', archive.namelist())
                for entry in archive.infolist():
                    self.assertGreater(entry.file_size, 0, entry.filename)
                self.assertIn(b'$(chap-id)', archive.read('login.html'))
                self.assertIn(b'$(if var == "")', archive.read('login.html'))
            self.assertEqual(sums.read_text('ascii').split()[0], hashlib.sha256(first.read_bytes()).hexdigest())

if __name__=='__main__': unittest.main()
