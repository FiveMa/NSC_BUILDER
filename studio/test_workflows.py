import unittest
from pathlib import Path

from studio import workflows


class WorkflowTests(unittest.TestCase):
    def test_merge_both_uses_one_ordered_manifest_for_two_batch_invocations(self):
        workflow = next(item for item in workflows.WORKFLOWS if item.id == 'merge')
        self.assertEqual(workflow.mode, 'group')
        files = [Path('Base Game.xci'), Path('Update.nsz'), Path('Additional Content.nsp')]
        output = Path('Output Folder')
        jobs = workflows.build_jobs(workflow, files, output, 'both')
        common = ['-b', '65536', '-pv', 'false', '-kp', 'false', '--RSVcap', '268435656',
                  '-fat', 'exfat', '-fx', 'files', '-ND', 'true']
        self.assertEqual(len(jobs), 2)
        for job, target in zip(jobs, ('nsp', 'xci')):
            self.assert_job(job, common + ['-t', target, '-o', str(output.absolute()), '-tfile',
                                           '$list', '-roma', 'TRUE', '-dmul', 'calculate'], files)
        self.assertEqual(jobs[0][jobs[0].index('-tfile') + 1], jobs[1][jobs[1].index('-tfile') + 1])

    def test_rejects_invalid_inputs_before_building_a_job(self):
        workflow = next(item for item in workflows.WORKFLOWS if item.id == 'compress')
        output = Path('Output')
        for files, destination, choice, error in (
            ([], output, '', 'Select at least one'),
            ([Path('game.nsp')], None, '', 'Select an output'),
            ([Path('game.nsp')], output, '23', 'Invalid choice'),
            ([Path('game.nsp'), Path('game.nca')], output, '', 'Unsupported input'),
            ([Path('game\npart.nsp')], output, '', 'line break'),
        ):
            with self.subTest(files=files, destination=destination, choice=choice):
                with self.assertRaisesRegex(ValueError, error):
                    workflows.build_jobs(workflow, files, destination, choice)

    def test_file_workflows_follow_batch_argument_order(self):
        catalog = {item.id: item for item in workflows.WORKFLOWS}
        output = Path('Output Folder').absolute()
        buffer = ['-b', '65536']
        dest = ['-o', str(output)]
        repack = buffer + ['-pv', 'false', '-kp', 'false', '--RSVcap', '268435656',
                           '-fat', 'exfat', '-fx', 'files', '-ND', 'true']
        cases = (
            ('convert', 'Game.nsp', 'both', repack + dest + ['-t', 'both', '-dc', '$input']),
            ('split', 'Game.nsp', 'xci', buffer + dest + ['-fat', 'exfat', '-fx', 'files',
                                                        '-t', 'xci', '-dspl', '$input', '-tfile', '$list']),
            ('extract', 'Game.xcz', 'raw', buffer + dest + ['-tfile', '$list', '-raw_x', '']),
            ('trim', 'Game.xci', '-xci_st', buffer + dest + ['-tfile', '$list', '-xci_st', '$input']),
            ('compress', 'Game.xci', '22', buffer + dest + ['-tfile', '$list', '--compress', '22',
                                                           '--threads', '0', '--nodelta', 'true', '--fexport', 'xcz']),
            ('decompress', 'Game.nsz', '', dest + ['-tfile', '$list', '--decompress', 'auto']),
            ('join', '00', '', buffer + dest + ['-tfile', '$list', '--joinfile', '']),
            ('rename', 'Game.nsx', 'force', ['-renf', 'single', '-tfile', '$list', '-t', 'nsp', 'xci',
                                            'nsx', 'nsz', 'xcz', '-renm', 'force', '-nover', 'false',
                                            '-oaid', 'false', '-addl', 'false', '-roma', 'TRUE',
                                            '-dlcrn', 'false', '-threads', '1']),
            ('restore', 'Game.nsp', '', buffer + dest + ['-tfile', '$list', '--restore', '']),
        )
        for workflow_id, name, choice, expected in cases:
            with self.subTest(workflow=workflow_id):
                workflow = catalog[workflow_id]
                files = [Path('A Folder') / name, Path('Another Folder') / name]
                jobs = workflows.build_jobs(workflow, files, output if workflow.output else None, choice)
                self.assertEqual(len(jobs), 2)
                for job, path in zip(jobs, files):
                    self.assert_job(job, expected, [path])

    def assert_job(self, job, expected, files):
        actual = list(job)
        if '$list' in expected:
            index = expected.index('$list')
            self.assertEqual(Path(actual[index]).read_text(encoding='utf-8').splitlines(),
                             [str(path.absolute()) for path in files])
            actual[index] = '$list'
        self.assertEqual(actual, [str(files[0].absolute()) if token == '$input' else token for token in expected])

    def test_inspection_builds_one_job_per_file_in_order(self):
        catalog = {item.id: item for item in workflows.WORKFLOWS}
        files = [Path('Folder With Spaces/Game.nsp'), Path('Update.xci')]
        for workflow_id, prefix, flag in (
            ('contents', [], '--ADVcontentlist'),
            ('firmware', ['--translate', 'FALSE'], '--fw_req'),
            ('verify', ['-b', '65536', '-vt', 'lv1'], '-v'),
        ):
            with self.subTest(workflow=workflow_id):
                jobs = workflows.build_jobs(catalog[workflow_id], files, None, '')
                self.assertEqual(len(jobs), len(files))
                for job, path in zip(jobs, files):
                    self.assertEqual(job[:-4], prefix)
                    self.assertEqual(job[-4], '-tfile')
                    self.assertEqual(job[-2:], [flag, str(path.absolute())])
                    self.assertEqual(Path(job[-3]).read_text(encoding='utf-8').splitlines(),
                                     [str(path.absolute())])


if __name__ == '__main__':
    unittest.main()
