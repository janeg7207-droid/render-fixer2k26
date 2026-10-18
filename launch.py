"""Start the browser app without requiring Tk; desktop mode is optional."""
import argparse
from http.server import ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
import threading
import webbrowser

ROOT = Path(__file__).resolve().parent


def create_browser_server():
    # Import only the browser backend. tkinter and ImageTk are not required.
    from server import Handler
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    return server, f'http://127.0.0.1:{server.server_port}'


def try_desktop():
    result = subprocess.run([sys.executable, str(ROOT / 'desktop.py')], cwd=ROOT,
                            capture_output=True, text=True, errors='replace')
    if result.returncode == 0:
        return True
    try:
        (ROOT / 'startup-error.log').write_text(result.stderr or result.stdout or 'Desktop startup failed.', encoding='utf-8')
    except OSError:
        pass
    print('The desktop window could not open. Switching to your browser.', flush=True)
    return False


def start_browser(open_browser=True):
    server, url = create_browser_server()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print('Render Workshop is ready: ' + url, flush=True)
    print('Keep this window open while using Render Workshop. Close it to stop.', flush=True)
    try:
        if open_browser:
            try:
                if not webbrowser.open(url):
                    print('Open the address above in your browser.', flush=True)
            except webbrowser.Error:
                print('Open the address above in your browser.', flush=True)
        while thread.is_alive():
            thread.join(.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--desktop', action='store_true', help='Try a native window first, with browser fallback')
    parser.add_argument('--no-open', action='store_true', help='Start the browser server without opening the browser')
    args = parser.parse_args()
    if args.desktop and try_desktop():
        return
    start_browser(not args.no_open)


if __name__ == '__main__':
    main()
