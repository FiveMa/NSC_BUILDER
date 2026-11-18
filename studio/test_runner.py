import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

from studio.runner import execute, engine_environment


class RunnerTests(unittest.TestCase):
    def test_process_receives_paths_verbatim_and_failure_stops_batch(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / 'fake engine.py'
            source.write_text('import sys\nprint(sys.argv[1])\nsys.exit(int(sys.argv[2]))\n')
            messages = []
            result = execute([sys.executable, '-u', str(source)],
                             [['a & b.nsp', '2'], ['unexpected', '0']], Path(directory),
                             engine_environment(None), Event(), messages.append)
            self.assertEqual(result, 2)
            self.assertIn('a & b.nsp\n', messages)
            self.assertNotIn('unexpected\n', messages)

    def test_cancelled_batch_does_not_spawn(self):
        stop = Event()
        stop.set()
        self.assertIsNone(execute(['not-a-real-python'], [[]], Path.cwd(), {}, stop, lambda _: None))

    def test_keys_passed_as_path_only(self):
        path = Path.cwd() / 'private keys.txt'
        self.assertEqual(engine_environment(path)['NSCB_STUDIO_KEYS_FILE'], str(path))
        self.assertNotIn('NSCB_STUDIO_KEYS_FILE', engine_environment(None))
