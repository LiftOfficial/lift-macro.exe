@echo off
setlocal
cd /d "%~dp0"
title Build LIFT MACRO 12.0
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
 echo Python 3.11+ was not found.
 echo Install from https://www.python.org/downloads/windows/
 echo IMPORTANT: enable "Add python.exe to PATH" during setup.
 pause
 exit /b 1
)
%PY% --version || goto failed
%PY% -m pip install --upgrade pip || goto failed
%PY% -m pip install -r requirements.txt || goto failed
%PY% -m PyInstaller --noconfirm --clean --windowed --onedir --name LIFT-MACRO --icon "assets\lift-icon.ico" --add-data "assets;assets" --collect-all PySide6 --collect-all shiboken6 --collect-all PySide6.QtWebEngineCore --collect-all PySide6.QtWebEngineWidgets --collect-all PySide6.QtWebEngine lift_macro.py || goto failed
if not exist "dist\LIFT-MACRO\LIFT-MACRO.exe" goto failed
echo.
echo BUILD SUCCESSFUL: dist\LIFT-MACRO\LIFT-MACRO.exe
echo Keep the complete LIFT-MACRO folder together.
pause
exit /b 0
:failed
echo.
echo BUILD FAILED. Take a screenshot of this window and share it for troubleshooting.
pause
exit /b 1
