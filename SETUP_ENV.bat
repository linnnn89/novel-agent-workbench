@echo off
setlocal EnableExtensions

cd /d "%~dp0"

set "PYTHON_LAUNCHER=py -3.13"
set "VENV_PY=.venv\Scripts\python.exe"
set "NO_PAUSE="

if /I "%~1"=="--no-pause" set "NO_PAUSE=1"
if /I "%~1"=="/no-pause" set "NO_PAUSE=1"

echo.
echo [Novel Agent Workbench] Setting up local Python environment
echo Repo: %CD%
echo.

%PYTHON_LAUNCHER% --version >nul 2>nul
if errorlevel 1 (
    echo Python 3.13 was not found through the Windows py launcher.
    echo Install Python 3.13, or make sure "py -3.13" works in PowerShell/CMD.
    if not defined NO_PAUSE pause
    exit /b 1
)

if not exist "%VENV_PY%" (
    echo Creating .venv ...
    %PYTHON_LAUNCHER% -m venv .venv
    if errorlevel 1 (
        echo Failed to create .venv.
        if not defined NO_PAUSE pause
        exit /b 1
    )
) else (
    echo Reusing existing .venv.
)

echo.
echo Upgrading packaging tools ...
"%VENV_PY%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo Failed to upgrade pip/setuptools/wheel.
    if not defined NO_PAUSE pause
    exit /b 1
)

echo.
echo Installing project in editable mode ...
"%VENV_PY%" -m pip install -e .
if errorlevel 1 (
    echo Failed to install the project.
    if not defined NO_PAUSE pause
    exit /b 1
)

echo.
echo Installing Windows desktop build tools ...
"%VENV_PY%" -m pip install pyinstaller pillow
if errorlevel 1 (
    echo Failed to install desktop build tools.
    if not defined NO_PAUSE pause
    exit /b 1
)

echo.
echo Environment setup completed.
echo.
echo Run CLI:
echo   .venv\Scripts\novel-agent-workbench.exe --help
echo.
echo Run desktop app from source:
echo   .venv\Scripts\novel-agent-workbench-desktop.exe
echo.
echo Build Windows EXE:
echo   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_windows_exe.ps1 -SkipInstall
echo.
if not defined NO_PAUSE pause
