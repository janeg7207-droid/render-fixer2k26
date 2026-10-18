# Render Workshop for WWE 2K26

A native desktop DDS inspector and converter, with an optional browser interface.
It never overwrites source files. The desktop app has native folder pickers, large
image previews, and a guided three-step workflow.

## Start

Install Python 3.10 or newer from python.org. On Windows, double-click
**Start-Windows.bat**. The fixed launcher opens the app in your browser and does
not require Tcl/Tk. Keep the launcher window open while using the app.
Python is required; this download is not a standalone EXE.
The first launch downloads the pinned Pillow dependency from PyPI. Subsequent
launches reuse the local virtual environment. Images stay on your computer.

The optional desktop app saves to a new `Converted-renders-...` folder inside the destination
you choose. Click **Open output folder** when done. Original names and subfolders
are retained. The per-file report lists any conversion failures. Each export uses
a unique folder, so earlier exports and source files are never replaced.

For the optional browser version on Linux/macOS, run `bash start.sh`. For the
native version with Tk installed, run `.venv/bin/python launch.py --desktop` after dependency
installation. This tries the desktop window first and falls back to the browser
if it fails. Linux desktop mode may require its distribution's `python3-tk` package.

In the optional browser version, choose a folder or individual files, inspect the
results, and download the ZIP. Extract it separately and read `conversion-report.json`
before testing files in game. Browser batches support up to 200 images / 120 MB. Folder selection is best supported by
current desktop Chrome and Edge. Folder selection includes subfolders; drag/drop
supports individual files only. Original filenames and relative folders are retained.

## What the default does

The default profile matches the supplied working `odb.dds`: 1024×1024, legacy
DXT5 / BC3, straight alpha, one mip level, and the same DDS header layout. Images
are resized to fit on a transparent square without stretching or cropping.
Compatible BC3 image blocks are preserved when no resize or mip generation is
necessary. Other images are decoded and re-encoded with lossy DXT5 compression.
Custom mode supports keeping dimensions or selecting 512/1024/2048 and generating
a full mip chain. Advanced texture types and ambiguous sRGB conversion are rejected.

The second working sample, `LENA KROSS.dds`, uses 1536×1536 DXT1 with 11 mip levels.
Consequently, neither non-power-of-two dimensions nor a missing full mip chain
alone proves a texture is invalid. Warnings are inspection notes, not a game validator.
The custom encoder currently outputs DXT5 only; it does not clone the LENA profile.

Both supplied unreadable Randy textures decode normally. One uses DX10 BC3,
and the other already uses 1024×1024 DXT5 but has a different depth/caps header.
Matching ODB produces candidate replacements, not a demonstrated in-game fix.

This tool does **not** bake, install, package, or assign game asset IDs. A correct
DDS cannot fix an incorrect filename, asset mapping, installation, or game package.
In-game loading has not been tested. Use your established installation process,
keep backups, and test one candidate before replacing an entire installed folder.

## Development

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python server.py
```

The server listens only on loopback port 8765; `--port` selects another port.
No node build, database, account, or game credentials are required.
