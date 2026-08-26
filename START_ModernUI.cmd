@echo off
setlocal
cd /d "%~dp0"

echo Starting modern UI from source...
echo This is a developer launcher, not the user EXE.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo .venv not found. Run SETUP_ENV.bat first.
    pause
    exit /b 1
)

set "PYTHONPATH=%CD%\src;%PYTHONPATH%"
".venv\Scripts\python.exe" -m novel_agent_workbench.modern_desktop
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" (
    echo.
    echo Modern UI exited with code %ERR%.
    pause
)
exit /b %ERR%
