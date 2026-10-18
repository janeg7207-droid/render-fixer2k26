#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [ ! -x .venv/bin/python ]; then python3 -m venv .venv; fi
if ! .venv/bin/python -c "import PIL; assert PIL.__version__ == '12.3.0'" 2>/dev/null; then
  .venv/bin/python -m pip install -r requirements.txt
fi
echo 'Open http://127.0.0.1:8765 in your browser. Keep this terminal open.'
exec .venv/bin/python server.py
