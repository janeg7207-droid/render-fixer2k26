import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import bootstrap


class BootstrapTests(unittest.TestCase):
    def test_rejects_315_and_prerelease_but_accepts_310(self):
        for version, release, accepted in (([3, 15], 'alpha', False), ([3, 15], 'final', False), ([3, 13], 'beta', False), ([3, 10], 'final', True), ([3, 13], 'final', True)):
            output = json.dumps(dict(version=version, release=release, executable='python.exe'))
            with patch.object(bootstrap.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, output)):
                self.assertEqual(bootstrap.probe(['python']) is not None, accepted)

    def test_unsupported_runtime_cannot_install_pillow(self):
        with patch.object(bootstrap.subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'unsupported'):
                bootstrap.ensure_environment(dict(version=[3, 15], release='final', executable='python.exe'))
            run.assert_not_called()

    def test_clean_environment_checks_image_extension_not_just_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = dict(version=[3, 12], release='final', executable='stable-python')
            responses = [subprocess.CompletedProcess([], 0), subprocess.CompletedProcess([], 1, '', 'SystemError: unknown slot ID 85'), subprocess.CompletedProcess([], 0), subprocess.CompletedProcess([], 0)]
            with patch.object(bootstrap, 'ROOT', Path(tmp)), patch.object(bootstrap, 'probe', return_value=runtime), patch.object(bootstrap.subprocess, 'run', side_effect=responses) as run:
                python = bootstrap.ensure_environment(runtime)
                self.assertIn('.venv-py312', str(python))
                commands = [call.args[0] for call in run.call_args_list]
                self.assertEqual(commands[0][:3], ['stable-python', '-m', 'venv'])
                self.assertIn(bootstrap.IMAGE_CHECK, commands[1])
                self.assertIn('--force-reinstall', commands[2])
                self.assertIn(bootstrap.IMAGE_CHECK, commands[3])

    def test_reuses_verified_image_environment_without_reinstall(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = dict(version=[3, 12], release='final', executable='stable-python')
            folder = Path(tmp) / '.venv-py312'
            python = folder / ('Scripts/python.exe' if bootstrap.os.name == 'nt' else 'bin/python')
            python.parent.mkdir(parents=True)
            python.touch()
            with patch.object(bootstrap, 'ROOT', Path(tmp)), patch.object(bootstrap, 'probe', return_value=runtime), patch.object(bootstrap.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
                self.assertEqual(bootstrap.ensure_environment(runtime), python)
                run.assert_called_once()
                self.assertIn(bootstrap.IMAGE_CHECK, run.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
