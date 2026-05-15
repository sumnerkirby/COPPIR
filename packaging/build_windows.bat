@echo off
REM Build COPPIR for Windows.
REM Produces: dist\COPPIR-windows.zip
REM
REM Requirements:
REM   - Python 3.10+ with pip  (python.org installer, add to PATH)
REM   - All Python dependencies installed in the active environment
REM   - Microsoft Visual C++ Redistributable (usually already present)
REM   - Microsoft Edge / WebView2 Runtime (ships with Windows 10 1803+ and 11)
REM
REM Run from the packaging\ directory:
REM   cd packaging && build_windows.bat

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set ROOT=%SCRIPT_DIR%..
set DIST=%SCRIPT_DIR%dist

echo =^> Installing build dependencies
pip install --quiet pyinstaller pillow
if errorlevel 1 ( echo ERROR: pip install failed & exit /b 1 )

echo =^> Generating icons
python "%SCRIPT_DIR%make_icons.py"
if errorlevel 1 ( echo ERROR: make_icons.py failed & exit /b 1 )

echo =^> Running PyInstaller
cd /d "%ROOT%"
pyinstaller ^
    --distpath "%DIST%" ^
    --workpath "%SCRIPT_DIR%build_tmp" ^
    --noconfirm ^
    "%SCRIPT_DIR%coppir.spec"
if errorlevel 1 ( echo ERROR: PyInstaller failed & exit /b 1 )

set APP_DIR=%DIST%\COPPIR
if not exist "%APP_DIR%\COPPIR.exe" (
    echo ERROR: %APP_DIR%\COPPIR.exe not found -- PyInstaller may have failed.
    exit /b 1
)

echo =^> Creating zip archive
set ZIP=%DIST%\COPPIR-windows.zip
REM Use PowerShell's Compress-Archive (available on Windows 10+)
powershell -NoProfile -Command ^
    "Compress-Archive -Path '%APP_DIR%' -DestinationPath '%ZIP%' -Force"
if errorlevel 1 ( echo ERROR: Compress-Archive failed & exit /b 1 )

echo.
echo Build complete: %ZIP%
echo.
echo Distribute COPPIR-windows.zip. Users extract the folder and run COPPIR.exe.
echo The entire COPPIR\ folder must stay together -- do not move the .exe alone.
echo.
echo Note: Windows SmartScreen may warn on first run because the binary is
echo unsigned. Users click "More info" then "Run anyway".
