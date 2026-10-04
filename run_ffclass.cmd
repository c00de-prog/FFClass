@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title FFClass - Windows launcher

:MENU
echo.
echo FFClass
echo 1. Run from source
echo 2. Build Windows installer EXE
echo 3. Build portable ZIP
echo 4. Exit
choice /C 1234 /N /M "Select 1, 2, 3, or 4: "
if errorlevel 4 exit /b 0
if errorlevel 3 goto BUILD
if errorlevel 2 goto INSTALLER
goto RUN

:PREPARE
if exist ".venv\Scripts\python.exe" goto PYTHON_READY
where py >nul 2>nul
if not errorlevel 1 py -3 -m venv ".venv"
if not exist ".venv\Scripts\python.exe" (
    where python >nul 2>nul
    if not errorlevel 1 python -m venv ".venv"
)
if not exist ".venv\Scripts\python.exe" (
    echo Python 3 was not found. Install Python, then run this file again.
    exit /b 1
)
:PYTHON_READY
set "FFCLASS_PY=%CD%\.venv\Scripts\python.exe"
"%FFCLASS_PY%" -c "import PySide6" >nul 2>nul
if errorlevel 1 (
    echo Installing FFClass dependencies...
    "%FFCLASS_PY%" -m pip install --disable-pip-version-check -r requirements.txt
    if errorlevel 1 exit /b 1
)
exit /b 0

:MEDIA
if exist "bin\ffmpeg.exe" if exist "bin\ffprobe.exe" exit /b 0
echo Looking for an installed FFmpeg pair to stage locally...
"%FFCLASS_PY%" stage_ffmpeg.py
if exist "bin\ffmpeg.exe" if exist "bin\ffprobe.exe" exit /b 0
exit /b 1

:RUN
call :PREPARE
if errorlevel 1 goto FAILED
call :MEDIA
if errorlevel 1 echo FFmpeg is missing. The UI can open, but media processing requires bin\ffmpeg.exe and bin\ffprobe.exe.
"%FFCLASS_PY%" gui.py
if errorlevel 1 goto FAILED
goto MENU

:BUILD
call :PREPARE
if errorlevel 1 goto FAILED
call :MEDIA
if errorlevel 1 (
    echo Building needs a local FFmpeg pair in bin. See README.md.
    goto FAILED
)
if not exist "bin\ffclass_ffmpeg.json" (
    echo Building needs bin\ffclass_ffmpeg.json from stage_ffmpeg.py. See README.md.
    goto FAILED
)
"%FFCLASS_PY%" -c "import PyInstaller" >nul 2>nul
if errorlevel 1 (
    echo Installing build dependency...
    "%FFCLASS_PY%" -m pip install --disable-pip-version-check -r requirements-build.txt
    if errorlevel 1 goto FAILED
)
"%FFCLASS_PY%" build_windows.py
if errorlevel 1 goto FAILED
echo.
echo Ready to upload: dist\FFClass-Windows.zip
goto MENU

:INSTALLER
call :PREPARE
if errorlevel 1 goto FAILED
call :MEDIA
if errorlevel 1 (
    echo Building needs a local FFmpeg pair in bin. See README.md.
    goto FAILED
)
if not exist "bin\ffclass_ffmpeg.json" (
    echo Building needs bin\ffclass_ffmpeg.json from stage_ffmpeg.py. See README.md.
    goto FAILED
)
"%FFCLASS_PY%" -c "import PyInstaller" >nul 2>nul
if errorlevel 1 (
    echo Installing build dependency...
    "%FFCLASS_PY%" -m pip install --disable-pip-version-check -r requirements-build.txt
    if errorlevel 1 goto FAILED
)
"%FFCLASS_PY%" build_installer.py
if errorlevel 1 goto FAILED
echo.
echo Ready to test: dist\FFClass-Setup-0.1.0-Windows.exe
goto MENU

:FAILED
echo.
echo FFClass could not complete this action. The error is shown above.
pause
goto MENU
