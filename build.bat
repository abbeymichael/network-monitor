@echo off
REM ============================================================================
REM  Build the PingSentry Windows executable + installer.
REM
REM  Usage (from a Developer / normal Command Prompt):
REM      build.bat
REM
REM  Steps:
REM    1. Installs dependencies (requirements.txt + PyInstaller).
REM    2. Builds a single windowed EXE that bundles on.wav / off.wav.
REM       -> dist\PingSentry.exe
REM    3. If Inno Setup (iscc) is installed, compiles a full installer.
REM       -> dist\PingSentry-Setup.exe
REM ============================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

if "%PYTHON%"=="" set PYTHON=python

echo ==^> Using interpreter:
%PYTHON% --version

echo ==^> Installing dependencies (requirements.txt + pyinstaller)
%PYTHON% -m pip install --upgrade pip
%PYTHON% -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo ==^> Cleaning previous build artifacts
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo ==^> Building executable with PyInstaller
%PYTHON% -m PyInstaller --clean --noconfirm PingSentry.spec
if errorlevel 1 goto :error

echo.
echo ==^> Executable built: dist\PingSentry.exe

REM ---- Optional: build the Windows installer with Inno Setup --------------
where iscc >nul 2>nul
if %errorlevel%==0 (
    echo ==^> Inno Setup found - compiling installer
    iscc installer.iss
    if errorlevel 1 goto :error
    echo.
    echo ==^> Installer built: dist\PingSentry-Setup.exe
) else (
    echo.
    echo ==^> Inno Setup ^(iscc^) not found on PATH.
    echo     Install it from https://jrsoftware.org/isdl.php to build the installer,
    echo     then re-run build.bat, or run:  iscc installer.iss
)

echo.
echo ==^> Done.
goto :eof

:error
echo.
echo *** BUILD FAILED ***
exit /b 1
