"""Local-only browser app. Files are processed in memory and never overwrite originals."""
import argparse
import base64
import io
import json
from pathlib import Path, PurePosixPath
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from zipfile import ZipFile, ZIP_DEFLATED
from PIL import Image
from renderfix import inspect_dds, normalize

WEB = Path(__file__).parent / 'web'
MAX_BODY = 180 * 1024 * 1024


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, data, kind='application/json'):
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        name = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}.get(self.path)
        if not name:
            return self.reply(404, b'Not found', 'text/plain')
        kind = {'html': 'text/html; charset=utf-8', 'js': 'text/javascript', 'css': 'text/css'}[name.split('.')[-1]]
        self.reply(200, (WEB / name).read_bytes(), kind)

    def do_POST(self):
        try:
            # Reject cross-site browser requests to this local file processor.
            host = self.headers.get('Host', '')
            if host not in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'):
                return self.reply(403, b'Invalid host', 'text/plain')
            if self.headers.get('Origin') not in (None, f'http://{host}'):
                return self.reply(403, b'Invalid origin', 'text/plain')
            size = int(self.headers.get('Content-Length', 0))
            if size <= 0 or size > MAX_BODY:
                raise ValueError('Batch too large. Use batches under 120 MB.')
            body = json.loads(self.rfile.read(size))
            files = body['files']
            if not isinstance(files, list) or not 1 <= len(files) <= 200:
                raise ValueError('Select between 1 and 200 files')
            if self.path not in ('/api/inspect', '/api/convert'):
                return self.reply(404, b'Not found', 'text/plain')
            results, outputs, used = [], [], set()
            for item in files:
                name = item['name']
                p = PurePosixPath(name)
                if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name or any(ord(c) < 32 for c in name):
                    raise ValueError('Unsafe file path')
                try:
                    data = base64.b64decode(item['data'], validate=True)
                    suffix = p.suffix.lower()
                    if suffix not in ('.dds', '.png', '.tga', '.jpg', '.jpeg', '.webp'):
                        raise ValueError('Unsupported image type')
                    if self.path == '/api/inspect':
                        if suffix == '.dds':
                            detail = inspect_dds(data)
                        else:
                            with Image.open(io.BytesIO(data)) as im:
                                im.load()
                                detail = dict(width=im.width, height=im.height, format=im.format, mips=1, bytes=len(data), alpha='A' in im.getbands(), warnings=['Source image: convert to DDS using a confirmed target profile'])
                        with Image.open(io.BytesIO(data)) as im:
                            im.thumbnail((160, 160))
                            buf = io.BytesIO()
                            im.convert('RGBA').save(buf, format='PNG')
                        detail['preview'] = base64.b64encode(buf.getvalue()).decode()
                    else:
                        output_name = str(p.with_suffix('.dds'))
                        if output_name.casefold() in used or output_name.casefold() == 'conversion-report.json':
                            raise ValueError('Duplicate output path; rename conflicting inputs first')
                        used.add(output_name.casefold())
                        output, detail = normalize(data, int(body.get('size', 0)), bool(body.get('mipmaps', False)))
                        outputs.append((output_name, output))
                    results.append(dict(name=name, ok=True, **detail))
                except Exception as exc:
                    results.append(dict(name=name, ok=False, error=str(exc)))
            if self.path == '/api/inspect':
                self.reply(200, json.dumps(results).encode())
            else:
                buf = io.BytesIO()
                with ZipFile(buf, 'w', ZIP_DEFLATED) as archive:
                    for name, data in outputs:
                        archive.writestr(name, data)
                    archive.writestr('conversion-report.json', json.dumps(dict(note='Candidate textures, not verified in WWE 2K26. Original inputs unchanged.', files=results), indent=2))
                self.reply(200, buf.getvalue(), 'application/zip')
        except Exception as exc:
            self.reply(400, json.dumps(dict(error=str(exc))).encode())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'Render Workshop listening on port {args.port}', flush=True)
    server.serve_forever()
