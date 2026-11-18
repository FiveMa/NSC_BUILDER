import sys
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from studio.update import Title, expected_titles, inspect_titles, replace_update, validate_result


BASE = '0100000000000000'
UPD = '0100000000000800'
DLC = '0100000000001001'
B = Title(BASE, 'BASE', 0, frozenset({'base.nca', 'base.cnmt.nca'}))
D = Title(DLC, 'DLC', 0, frozenset({'dlc.nca', 'dlc.cnmt.nca'}))
OLD = Title(UPD, 'UPDATE', 65536, frozenset({'old.nca', 'old.cnmt.nca'}))
NEW = Title(UPD, 'UPDATE', 131072, frozenset({'new.nca', 'new.cnmt.nca'}))


class UpdateTests(unittest.TestCase):
    def test_keeps_base_and_dlc_but_replaces_old_patch(self):
        expected = expected_titles([B, OLD, D], [NEW])
        self.assertEqual(set(expected.values()), {B, NEW, D})
        validate_result(expected, [B, NEW, D])
        for bad in ([NEW], [B, OLD, D], [B, NEW], [B, OLD, NEW, D]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_result(expected, bad)

    def test_rejects_wrong_game_and_older_or_non_patch_inputs(self):
        unrelated = Title('0100000000002800', 'UPDATE', NEW.version, NEW.files)
        for source, patch in (([B, OLD], [unrelated]), ([B, NEW], [OLD]),
                              ([B, OLD], [B]), ([OLD], [NEW]), ([B, NEW], [NEW])):
            with self.subTest(source=source, patch=patch), self.assertRaises(ValueError):
                expected_titles(source, patch)

    def test_incomplete_engine_output_is_never_published(self):
        self.exercise_builder([NEW], success=False)

    def test_only_verified_result_reaches_destination(self):
        self.exercise_builder([D, B, NEW], success=True)

    def test_existing_destination_is_not_overwritten(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            base, update, out = root / 'source.xci', root / 'update.nsp', root / 'already there.xci'
            for path in (base, update, out):
                path.write_bytes(b'existing')
            with self.assertRaisesRegex(ValueError, 'aucun fichier existant'):
                replace_update(base, update, out, Path('engine.py'), 'python', {}, threading.Event(), lambda _: None)
            self.assertEqual(out.read_bytes(), b'existing')

    def test_xci_probe_uses_the_read_only_engine_interface_in_a_child(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'Keys.py').write_text('keys = {"fixture": True}\n', encoding='utf-8')
            (root / 'sq_settings.py').write_text('def set_prod_environment(): pass\n', encoding='utf-8')
            (root / 'Fs.py').write_text('''
from types import SimpleNamespace
class Partition(list):
    _path = 'secure'
class Xci:
    def __init__(self, file=None):
        self.hfs0 = [Partition([SimpleNamespace(_path='base.nca', size=2),
                                SimpleNamespace(_path='base.cnmt.nca', size=3)])]
    def get_content(self, ofolder, vkeypatch, delta):
        assert (ofolder, vkeypatch, delta) == (False, False, True)
        return [('', '0100000000000000', '', 0, [('base.nca', 2), ('base.cnmt.nca', 3)], 'BASE', '0')]
    def close(self): pass
''', encoding='utf-8')
            self.assertEqual(inspect_titles(root / 'sample.xci', root / 'engine.py', sys.executable,
                                            None, threading.Event(), root), [B])

    def exercise_builder(self, built_titles, *, success):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            base, update = root / 'source game.xci', root / 'input update.nsp'
            out = root / 'destination.xci'
            base.write_bytes(b'original')
            update.write_bytes(b'update')
            commands = []

            def execute(prefix, jobs, cwd, env, stop, emit):
                args, = jobs
                commands.append(args)
                staging = Path(args[args.index('-o') + 1])
                manifest = Path(args[args.index('-tfile') + 1])
                self.assertEqual(manifest.read_text(encoding='utf-8').splitlines(), [str(base), str(update)])
                (staging / 'from engine.xci').write_bytes(b'built')
                return 0

            with patch('studio.update.inspect_titles', side_effect=[[B, OLD, D], [NEW], built_titles]), patch('studio.update.execute', execute):
                if success:
                    self.assertTrue(replace_update(base, update, out, Path('engine.py'), 'python', {}, threading.Event(), lambda _: None))
                    self.assertEqual(out.read_bytes(), b'built')
                else:
                    with self.assertRaises(ValueError):
                        replace_update(base, update, out, Path('engine.py'), 'python', {}, threading.Event(), lambda _: None)
                    self.assertFalse(out.exists())
            self.assertIn('-dmul', commands[0])
            self.assertEqual(base.read_bytes(), b'original')
            self.assertEqual(update.read_bytes(), b'update')
            self.assertEqual(sorted(p.name for p in root.iterdir()), sorted([base.name, update.name] + ([out.name] if success else [])))
