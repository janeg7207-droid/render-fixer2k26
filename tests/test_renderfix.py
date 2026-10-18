import base64
import io
import json
import struct
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from zipfile import ZipFile
from PIL import Image
from renderfix import inspect_dds, normalize
from server import Handler


def fixture(size=(16, 16)):
    im = Image.new('RGBA', size, (180, 50, 25, 255))
    im.putpixel((0, 0), (0, 0, 0, 0))
    buf = io.BytesIO()
    im.save(buf, format='DDS', pixel_format='DXT5')
    return buf.getvalue()


class TextureTests(unittest.TestCase):
    def test_legacy_preserves_image_data_and_alpha(self):
        original = fixture()
        result, report = normalize(original)
        self.assertEqual(result[128:], original[128:])
        self.assertTrue(inspect_dds(result)['alpha'])
        self.assertEqual(struct.unpack_from('<I', result, 20)[0], 256)
        self.assertIn('preserved', report['operation'])

    def test_dx10_bc3_header_rewrap_preserves_blocks(self):
        legacy = bytearray(fixture())
        legacy[84:88] = b'DX10'
        original = bytes(legacy[:128]) + struct.pack('<5I', 77, 3, 0, 1, 0) + legacy[128:]
        result, _ = normalize(original)
        self.assertEqual(result[84:88], b'DXT5')
        self.assertEqual(result[128:], original[148:])

    def test_resize_and_complete_mip_payload(self):
        result, _ = normalize(fixture((32, 16)), 512, True)
        info = inspect_dds(result)
        self.assertEqual((info['width'], info['height'], info['mips']), (512, 512, 10))
        expected = sum(((max(1, 512 >> n) + 3)//4)**2 * 16 for n in range(10))
        self.assertEqual(len(result), 128 + expected)
        with Image.open(io.BytesIO(result)) as im:
            self.assertEqual(im.getpixel((250, 0))[3], 0)
            self.assertGreater(im.getpixel((250, 250))[3], 200)

    def test_truncated_and_array_textures_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Truncated'):
            inspect_dds(fixture()[:-1])
        data = bytearray(fixture())
        struct.pack_into('<I', data, 112, 0x200)
        with self.assertRaises(ValueError):
            normalize(data)


class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, path, body, origin=None):
        connection = HTTPConnection('127.0.0.1', self.server.server_port)
        headers = {'Content-Type': 'application/json'}
        if origin:
            headers['Origin'] = origin
        connection.request('POST', path, json.dumps(body), headers)
        response = connection.getresponse()
        status, data = response.status, response.read()
        connection.close()
        return status, data

    def test_batch_reports_bad_file_and_keeps_folder(self):
        data = base64.b64encode(fixture()).decode()
        files = [{'name':'roster/good.dds','data':data}, {'name':'broken.dds','data':base64.b64encode(b'bad').decode()}]
        status, body = self.request('/api/inspect', {'files':files})
        self.assertEqual(status, 200)
        self.assertEqual([r['ok'] for r in json.loads(body)], [True, False])
        status, body = self.request('/api/convert', {'files':files, 'size':0})
        self.assertEqual(status, 200)
        with ZipFile(io.BytesIO(body)) as z:
            self.assertEqual(set(z.namelist()), {'roster/good.dds','conversion-report.json'})
            inspect_dds(z.read('roster/good.dds'))
            report = json.loads(z.read('conversion-report.json'))
            self.assertFalse(report['files'][1]['ok'])

    def test_cross_origin_and_path_traversal_rejected(self):
        files = [{'name':'../bad.dds','data':base64.b64encode(fixture()).decode()}]
        self.assertEqual(self.request('/api/convert', {'files':files})[0], 400)
        self.assertEqual(self.request('/api/convert', {'files':files}, 'https://example.com')[0], 403)


if __name__ == '__main__':
    unittest.main()
