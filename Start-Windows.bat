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
echo Opening the Render Workshop desktop application.
.venv\Scripts\python.exe -c "import tkinter; import PIL.ImageTk" >nul 2>nul
if errorlevel 1 goto failed
start "" .venv\Scripts\pythonw.exe desktop.py
exit /b 0
:failed
echo Could not start. Install Python 3.10 or newer from python.org with Python on PATH and Tcl/Tk enabled, then retry.
pause
exit /b 1
