@echo off
setlocal EnableExtensions
chcp 65001 >nul

cd /d "%~dp0"

set "NO_PAUSE="
if /I "%~1"=="--no-pause" set "NO_PAUSE=1"
if /I "%~1"=="/no-pause" set "NO_PAUSE=1"

echo.
echo ============================================================
echo  Novel Agent Workbench - Windows EXE Build
echo ============================================================
echo Repo: %CD%
echo.
echo This window will show each build step.
echo.

echo [Build] Running environment and PyInstaller package steps ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build_windows_exe.ps1"
if errorlevel 1 (
    echo.
    echo Build failed. Review the messages above.
    if not defined NO_PAUSE pause
    exit /b 1
)

set "APP_EXE=%~dp0dist\NovelAgentWorkbench\NovelAgentWorkbench.exe"

echo.
echo ============================================================
echo  Build completed
echo ============================================================
echo 您的运行 EXE 在:
echo   %APP_EXE%
echo.
echo 可双击运行；也可以按 Y 立即启动。
echo.
if defined NO_PAUSE goto done
choice /C YN /N /M "现在运行 NovelAgentWorkbench.exe 吗？[Y/N] "
if errorlevel 2 goto done
start "" "%APP_EXE%"

:done
echo.
echo Done.
if not defined NO_PAUSE pause
