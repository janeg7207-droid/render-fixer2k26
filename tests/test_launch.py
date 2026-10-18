import base64
from http.client import HTTPConnection
import io
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
from PIL import Image
import launch


class LaunchTests(unittest.TestCase):
    def test_missing_tk_records_error_and_allows_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.CompletedProcess([], 1, '', "ModuleNotFoundError: No module named 'tkinter'")
            with patch.object(launch, 'ROOT', Path(tmp)), patch.object(launch.subprocess, 'run', return_value=result):
                self.assertFalse(launch.try_desktop())
                self.assertIn('tkinter', (Path(tmp) / 'startup-error.log').read_text())

    def test_default_avoids_desktop_and_missing_tk_falls_back(self):
        with patch('sys.argv', ['launch.py']), patch.object(launch, 'try_desktop') as desktop, patch.object(launch, 'start_browser') as browser:
            launch.main()
            desktop.assert_not_called()
            browser.assert_called_once_with(True)
        with patch('sys.argv', ['launch.py', '--desktop']), patch.object(launch, 'try_desktop', return_value=False), patch.object(launch, 'start_browser') as browser:
            launch.main()
            browser.assert_called_once_with(True)

    def test_dynamic_port_serves_real_conversion(self):
        server, url = launch.create_browser_server()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            self.assertTrue(url.endswith(str(server.server_port)))
            connection = HTTPConnection('127.0.0.1', server.server_port)
            connection.request('GET', '/')
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertIn(b'Choose folder', response.read())
            buf = io.BytesIO()
            Image.new('RGBA', (8, 8), (255, 0, 0, 180)).save(buf, format='PNG')
            body = json.dumps({'files':[{'name':'test.png', 'data':base64.b64encode(buf.getvalue()).decode()}], 'size':512})
            connection.request('POST', '/api/convert', body, {'Content-Type':'application/json'})
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            from zipfile import ZipFile
            from renderfix import inspect_dds
            with ZipFile(io.BytesIO(response.read())) as archive:
                self.assertEqual(inspect_dds(archive.read('test.dds'))['width'], 512)
            connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
