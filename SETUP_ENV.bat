@echo off
setlocal EnableExtensions

cd /d "%~dp0"

set "PYTHON_LAUNCHER="
set "VENV_PY=.venv\Scripts\python.exe"
set "NO_PAUSE="

if /I "%~1"=="--no-pause" set "NO_PAUSE=1"
if /I "%~1"=="/no-pause" set "NO_PAUSE=1"
if /I "%~2"=="--no-pause" set "NO_PAUSE=1"
if /I "%~2"=="/no-pause" set "NO_PAUSE=1"

echo.
echo [Novel Agent Workbench] Setting up local Python environment
echo Repo: %CD%
echo.

if not defined PYTHON_LAUNCHER py -3.13 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set "PYTHON_LAUNCHER=py -3.13"
if not defined PYTHON_LAUNCHER py -3.12 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set "PYTHON_LAUNCHER=py -3.12"
if not defined PYTHON_LAUNCHER py -3.11 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set "PYTHON_LAUNCHER=py -3.11"
if not defined PYTHON_LAUNCHER py -3.10 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set "PYTHON_LAUNCHER=py -3.10"
if not defined PYTHON_LAUNCHER python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set "PYTHON_LAUNCHER=python"

if not defined PYTHON_LAUNCHER (
    echo No compatible Python was found.
    echo Install Python 3.10 or newer, then rerun this file.
    if not defined NO_PAUSE pause
    exit /b 1
)

echo Using Python:
%PYTHON_LAUNCHER% --version
echo.

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

"%VENV_PY%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 (
    echo Existing .venv is older than Python 3.10.
    echo Remove .venv and rerun this setup file with Python 3.10 or newer installed.
    if not defined NO_PAUSE pause
    exit /b 1
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
if exist "src\novel_agent_workbench.egg-info" (
    echo Removing stale editable-install metadata ...
    rmdir /s /q "src\novel_agent_workbench.egg-info"
)
"%VENV_PY%" -m pip install -e .
if errorlevel 1 (
    echo Editable install failed in this checkout.
    echo Continuing because the app can still run from source with PYTHONPATH=src.
    echo On a fresh clone, rerun this file after confirming the source directory is writable.
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
echo   BUILD_NovelAgentWorkbench.bat
echo.
if not defined NO_PAUSE pause
exit /b 0
