import io
import json
from pathlib import Path
import queue
import tempfile
import unittest
from PIL import Image
from desktop import Workshop
from renderfix import inspect_dds


class ExportTests(unittest.TestCase):
    def make_image(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new('RGBA', (16, 16), (40, 80, 120, 160))
        image.save(path)

    def worker(self, files, base=None):
        # Exercise the desktop conversion worker without opening a GUI.
        app = Workshop.__new__(Workshop)
        app.files, app.base, app.events = files, base, queue.Queue()
        return app

    def result(self, app):
        messages = list(app.events.queue)
        saved = next(value for event, value in messages if event == 'saved')
        output = saved[0]
        return output, json.loads((output / 'conversion-report.json').read_text())['files']

    def test_nested_paths_originals_and_repeated_exports(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'source' / 'roster' / 'test.png'
            self.make_image(source)
            original = source.read_bytes()
            app = self.worker([source], root / 'source')
            app.convert(root, 512, False)
            first, report = self.result(app)
            self.assertTrue(report[0]['ok'])
            self.assertEqual(inspect_dds((first / 'roster/test.dds').read_bytes())['width'], 512)
            self.assertEqual(source.read_bytes(), original)
            app.events = queue.Queue()
            app.convert(root, 512, False)
            second, _ = self.result(app)
            self.assertNotEqual(first, second)
            self.assertTrue((first / 'roster/test.dds').exists())

    def test_duplicate_names_and_unreadable_files_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            one, two, bad = root / 'a/test.png', root / 'b/test.png', root / 'bad.dds'
            self.make_image(one)
            self.make_image(two)
            bad.write_bytes(b'not a DDS')
            app = self.worker([one, two, bad])
            app.convert(root, 512, False)
            output, report = self.result(app)
            self.assertEqual([r['ok'] for r in report], [True, False, False])
            self.assertEqual(len(list(output.glob('*.dds'))), 1)


if __name__ == '__main__':
    unittest.main()
