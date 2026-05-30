@echo off
setlocal
set "APP_DIR=%~dp0dist\NovelAgentWorkbench"
set "APP_EXE=%APP_DIR%\NovelAgentWorkbench.exe"

if not exist "%APP_EXE%" (
    echo NovelAgentWorkbench.exe not found.
    echo Expected: %APP_EXE%
    echo Run BUILD_NovelAgentWorkbench.bat first.
    pause
    exit /b 1
)

start "" "%APP_EXE%"
