import argparse
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


class CatalogTests(unittest.TestCase):
    def test_static_catalog_keeps_declaration_order_and_groups_aliases(self):
        from studio.core import Option, load_catalog

        source = '''
import argparse
raise RuntimeError("catalog loading must not execute Squirrel")
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('file', nargs='*')
    # parser.add_argument('--commented-out')
    parser.add_argument('-v', '--verify', '--check', nargs='+', help='Verify files')
    parser.add_argument('--internal', help=argparse.SUPPRESS)
    parser.add_argument('--force', action='store_true')
    other_object.add_argument('--unrelated')
    args = parser.parse_args()
    parser.add_argument('--too-late')
'''
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'squirrel.py'
            path.write_text(source, encoding='utf-8')
            catalog = load_catalog(path)

        self.assertEqual(catalog, [
            Option('file', (), '', '*', 'store'),
            Option('--verify', ('-v', '--check'), 'Verify files', '+', 'store'),
            Option('--internal', (), '', None, 'store'),
            Option('--force', (), '', None, 'store_true'),
        ])


class ArgumentTests(unittest.TestCase):
    def test_argv_round_trips_paths_and_keeps_positionals_out_of_variadic_option(self):
        from studio.core import Option, build_arguments

        argv = build_arguments(iter([
            (Option('file', (), '', '*', 'store'), ['C:/Input Files/a & b.nsp']),
            (Option('--verify', ('-v',), '', '+', 'store'), ['One File.nsp', 'Two File.nsp']),
            (Option('--force', (), '', None, 'store_true'), []),
        ]))
        self.assertEqual(argv, [
            '--verify', 'One File.nsp', 'Two File.nsp', '--force', '--', 'C:/Input Files/a & b.nsp',
        ])
        parser = argparse.ArgumentParser()
        parser.add_argument('file', nargs='*')
        parser.add_argument('-v', '--verify', nargs='+')
        parser.add_argument('--force', action='store_true')
        args = parser.parse_args(argv)
        self.assertEqual(args.file, ['C:/Input Files/a & b.nsp'])
        self.assertEqual(args.verify, ['One File.nsp', 'Two File.nsp'])
        self.assertTrue(args.force)

    def test_arity_rejects_missing_or_extra_values(self):
        from studio.core import Option, build_arguments

        cases = [
            (None, 'store', []), (None, 'store', ['a', 'b']),
            ('+', 'store', []), ('?', 'store', ['a', 'b']),
            (2, 'store', ['a']), (2, 'store', ['a', 'b', 'c']),
            (None, 'store_true', ['true']),
        ]
        for nargs, action, values in cases:
            with self.subTest(nargs=nargs, action=action, values=values):
                with self.assertRaisesRegex(ValueError, '--sample'):
                    build_arguments([(Option('--sample', (), '', nargs, action), values)])

    def test_valid_arity_can_emit_bare_flags_and_exact_counts(self):
        from studio.core import Option, build_arguments

        self.assertEqual(build_arguments([
            (Option('--maybe', (), '', '?', 'store'), []),
            (Option('--items', (), '', '*', 'store'), []),
            (Option('--pair', (), '', 2, 'store'), ['a', 'b']),
            (Option('--quiet', (), '', None, 'store_false'), []),
        ]), ['--maybe', '--items', '--pair', 'a', 'b', '--quiet'])

    def test_duplicate_selections_are_rejected(self):
        from studio.core import Option, build_arguments

        verify = Option('--verify', ('-v',), '', '+', 'store')
        alias = Option('-v', (), '', '+', 'store')
        for duplicate in (verify, alias):
            with self.subTest(duplicate=duplicate.flag):
                with self.assertRaisesRegex(ValueError, 'duplicate'):
                    build_arguments([(verify, ['a']), (duplicate, ['b'])])

    def test_unattached_option_like_values_are_rejected(self):
        from studio.core import Option, build_arguments

        verify = Option('--verify', ('-v',), '', '+', 'store')
        for value in ('--', '--force', '-v', '-name with spaces.nsp'):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, 'option-like'):
                    build_arguments([(verify, ['a', value])])

    def test_positionals_after_the_separator_can_start_with_a_hyphen(self):
        from studio.core import Option, build_arguments

        argv = build_arguments([(Option('file', (), '', '*', 'store'), ['-file.nsp'])])
        parser = argparse.ArgumentParser()
        parser.add_argument('file', nargs='*')
        self.assertEqual(parser.parse_args(argv).file, ['-file.nsp'])


if __name__ == '__main__':
    unittest.main()
