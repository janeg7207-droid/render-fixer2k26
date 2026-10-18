@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  where py >nul 2>nul
  if errorlevel 1 (
    python -m venv .venv
  ) else (
    py -3 -m venv .venv
  )
  if errorlevel 1 goto failed
)
.venv\Scripts\python.exe -c "import PIL; assert PIL.__version__ == '12.3.0'" >nul 2>nul
if errorlevel 1 (
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 goto failed
)
echo Opening Render Workshop in your browser. No Tcl/Tk installation is needed.
.venv\Scripts\python.exe launch.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo Render Workshop could not start. The actual error is shown above.
echo Python 3.10 or newer with pip is required. Tcl/Tk is NOT required.
pause
exit /b 1
