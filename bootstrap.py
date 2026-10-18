"""Select a stable Python before importing binary image dependencies."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
SUPPORTED = {(3, 10), (3, 11), (3, 12), (3, 13)}
PROBE = "import json,sys;print(json.dumps({'version':list(sys.version_info[:2]),'release':sys.version_info.releaselevel,'executable':sys.executable}))"
IMAGE_CHECK = "import io,PIL;from PIL import Image;assert PIL.__version__=='12.3.0';b=io.BytesIO();Image.new('RGBA',(8,8)).save(b,format='DDS',pixel_format='DXT5');b.seek(0);Image.open(b).load()"


def probe(command):
    try:
        result = subprocess.run([*command, '-c', PROBE], capture_output=True, text=True, timeout=20)
        if result.returncode:
            return None
        info = json.loads(result.stdout)
        if tuple(info['version']) in SUPPORTED and info['release'] == 'final':
            return info
    except (OSError, subprocess.SubprocessError, ValueError, KeyError):
        pass
    return None


def find_runtime():
    candidates = [[sys.executable]]
    if os.name == 'nt':
        candidates += [['py', '-3.13'], ['py', '-3.12'], ['py', '-3.11'], ['py', '-3.10']]
        local = os.environ.get('LOCALAPPDATA')
        if local:
            candidates += [[str(Path(local) / 'Programs' / 'Python' / f'Python{version}' / 'python.exe')] for version in ('313', '312', '311', '310')]
    for name in ('python3.13', 'python3.12', 'python3.11', 'python3.10', 'python', 'python3'):
        executable = shutil.which(name)
        if executable:
            candidates.append([executable])
    for command in candidates:
        info = probe(command)
        if info:
            return info
    return None


def install_runtime():
    winget = shutil.which('winget') if os.name == 'nt' else None
    if not winget:
        raise RuntimeError('Install Python 3.13 from https://www.python.org/downloads/windows/ and run Start-Windows.bat again. Python 3.15 is not supported for image processing.')
    print('A stable Python is needed. Installing Python 3.13 for your Windows user…', flush=True)
    print('Your existing Python installation will stay installed.', flush=True)
    subprocess.run([winget, 'install', '--id', 'Python.Python.3.13', '--exact', '--source', 'winget', '--scope', 'user', '--silent', '--accept-source-agreements', '--accept-package-agreements', '--disable-interactivity'], check=True)
    runtime = find_runtime()
    if runtime is None:
        raise RuntimeError('Python 3.13 was installed but could not be located. Close this window and run Start-Windows.bat again.')
    return runtime


def ensure_environment(runtime):
    version = tuple(runtime['version'])
    if version not in SUPPORTED or runtime['release'] != 'final':
        raise RuntimeError('Refusing to install image dependencies in an unsupported Python runtime.')
    folder = ROOT / ('.venv-py' + ''.join(str(part) for part in version))
    relative_python = Path('Scripts/python.exe') if os.name == 'nt' else Path('bin/python')
    python = folder / relative_python
    existing = probe([str(python)]) if python.exists() else None
    if folder.exists() and (existing is None or tuple(existing['version']) != version):
        folder = Path(tempfile.mkdtemp(prefix=folder.name + '-repair-', dir=ROOT))
        python = folder / relative_python
        existing = None
    if existing is None:
        subprocess.run([runtime['executable'], '-m', 'venv', str(folder)], check=True)
    verified = probe([str(python)])
    if verified is None or tuple(verified['version']) != version:
        raise RuntimeError('The new environment did not use the selected stable Python.')
    print(f'Using Python {version[0]}.{version[1]} for Render Workshop.', flush=True)
    check = subprocess.run([str(python), '-c', IMAGE_CHECK], capture_output=True, text=True)
    if check.returncode:
        subprocess.run([str(python), '-m', 'pip', '--disable-pip-version-check', 'install', '--no-input', '--force-reinstall', '-r', str(ROOT / 'requirements.txt')], check=True)
        subprocess.run([str(python), '-c', IMAGE_CHECK], check=True)
    return python


def main():
    print('Preparing Render Workshop with a compatible Python runtime…', flush=True)
    runtime = find_runtime()
    if runtime is None:
        runtime = install_runtime()
    python = ensure_environment(runtime)
    return subprocess.call([str(python), str(ROOT / 'launch.py')], cwd=ROOT)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f'\nRender Workshop could not start: {exc}', file=sys.stderr, flush=True)
        sys.exit(1)
