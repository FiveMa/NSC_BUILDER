import runpy
import unittest
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1] / 'py' / 'ztools'


class LegacyEnumTests(unittest.TestCase):
    def test_metadata_enum_keeps_legacy_spelling_and_integer_identity(self):
        for folder in ('Fs', 'nutFs'):
            with self.subTest(folder=folder):
                enums = runpy.run_path(str(ENGINE / folder / 'Type.py'))
                meta = enums['Content'].META
                self.assertEqual(str(meta), 'Content.META')
                self.assertEqual(int(meta), 1)
                self.assertEqual(enums['Content'](1), meta)
