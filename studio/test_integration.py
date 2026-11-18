"""Exercise the guided join workflow with Squirrel itself and no private data."""
import importlib.util
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from studio.runner import engine_environment
from studio.workflows import WORKFLOWS, build_jobs

ENGINE = Path(__file__).resolve().parents[1] / 'py' / 'ztools' / 'squirrel.py'


@unittest.skipUnless(sys.platform == 'win32', 'Squirrel integration fixture targets Windows')
@unittest.skipUnless(importlib.util.find_spec('Crypto'), 'Install studio/requirements.txt for engine integration')
class SquirrelIntegrationTests(unittest.TestCase):
    def test_join_produces_exact_bytes_from_fragments_in_a_path_with_spaces(self):
        with TemporaryDirectory(prefix='studio join ') as directory:
            base = Path(directory)
            first = base / 'grouped sample.ns0'
            second = base / 'grouped sample.ns1'
            first.write_bytes(b'first fragment\0')
            second.write_bytes(b'\x01second fragment')
            expected = first.read_bytes() + second.read_bytes()

            # The upstream import requires these fields even though joining is
            # byte concatenation. All zeroes, no encryption or private data.
            fields = ('aes_kek_generation_source', 'aes_key_generation_source',
                      'titlekek_source', 'key_area_key_application_source',
                      'key_area_key_ocean_source', 'key_area_key_system_source')
            fixture = base / 'synthetic.txt'
            fixture.write_text(''.join(f'{field} = {"00" * 16}\n' for field in fields)
                               + f'header_key = {"00" * 32}\n', encoding='utf-8')
            target = base / 'separate destination'
            workflow = next(item for item in WORKFLOWS if item.id == 'join')
            jobs = build_jobs(workflow, [first], target, '')
            self.assertEqual(len(jobs), 1)
            process = subprocess.run([sys.executable, '-u', str(ENGINE), *jobs[0]],
                                     cwd=ENGINE.parent, env=engine_environment(fixture),
                                     stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                                     errors='replace', timeout=20)
            self.assertEqual(process.returncode, 0, process.stdout)
            output = target / 'grouped sample.nsp'
            self.assertTrue(output.is_file(), process.stdout)
            self.assertEqual(output.read_bytes(), expected)
            self.assertTrue(first.is_file() and second.is_file())
