@echo off
setlocal EnableExtensions
title Remove FFClass
set "FFCLASS_APP_DIR=%~dp0"

if not exist "%FFCLASS_APP_DIR%FFClass.exe" goto INVALID
if not exist "%FFCLASS_APP_DIR%_internal\bin\ffmpeg.exe" goto INVALID
if not exist "%FFCLASS_APP_DIR%_internal\bin\ffprobe.exe" goto INVALID
if not exist "%FFCLASS_APP_DIR%remove_ffclass.ps1" goto INVALID

echo This will remove the FFClass application folder and its settings.
echo Videos outside the FFClass folder will remain on disk.
echo Move any personal files out of the FFClass folder before continuing.
echo Close FFClass before continuing.
echo.
choice /C YN /N /M "Remove FFClass and its settings? [Y/N] "
if errorlevel 2 exit /b 0

tasklist /FI "IMAGENAME eq FFClass.exe" 2>nul | find /I "FFClass.exe" >nul
if not errorlevel 1 (
    echo FFClass is still open. Close it and run this file again.
    pause
    exit /b 1
)

set "FFCLASS_TEMP_SCRIPT=%TEMP%\FFClass-remove-%RANDOM%-%RANDOM%.ps1"
copy /Y "%FFCLASS_APP_DIR%remove_ffclass.ps1" "%FFCLASS_TEMP_SCRIPT%" >nul
if errorlevel 1 (
    echo Could not prepare the removal script.
    pause
    exit /b 1
)
start "FFClass removal" /D "%TEMP%" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%FFCLASS_TEMP_SCRIPT%"
exit /b 0

:INVALID
echo Run this file from the extracted FFClass folder containing FFClass.exe and _internal.
pause
exit /b 1
