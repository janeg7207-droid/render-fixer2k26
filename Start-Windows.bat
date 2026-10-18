@echo off
setlocal
cd /d "%~dp0"
echo Starting Render Workshop. Please keep this window open.
echo Image processing uses stable Python 3.10 through 3.13, never Python 3.15.
where py >nul 2>nul
if errorlevel 1 goto use_python
py -3 bootstrap.py
if errorlevel 1 goto failed
exit /b 0
:use_python
python bootstrap.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo The startup error is shown above. Tcl/Tk is not required.
pause
exit /b 1
