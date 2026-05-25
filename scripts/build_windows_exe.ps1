param(
    [string]$Python = "py -3.13",
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$IconPath = Join-Path $RepoRoot "src\novel_agent_workbench\assets\novel_agent_workbench.ico"
$LauncherPath = Join-Path $RepoRoot "packaging\desktop_launcher.py"
$AssetsPath = Join-Path $RepoRoot "src\novel_agent_workbench\assets"

Push-Location $RepoRoot
try {
    if (-not (Test-Path $VenvPython)) {
        Invoke-Expression "$Python -m venv .venv"
    }

    if (-not $SkipInstall) {
        & $VenvPython -m pip install --upgrade pip
        & $VenvPython -m pip install pyinstaller pillow
    }

    & $VenvPython scripts\generate_windows_icon.py

    & $VenvPython -m PyInstaller `
        --noconfirm `
        --clean `
        --windowed `
        --name "NovelAgentWorkbench" `
        --icon $IconPath `
        --paths "src" `
        --add-data "$AssetsPath;novel_agent_workbench\assets" `
        $LauncherPath

    $BuildDir = Join-Path $RepoRoot "build"
    $SpecPath = Join-Path $RepoRoot "NovelAgentWorkbench.spec"
    if (Test-Path $BuildDir) {
        Remove-Item -LiteralPath $BuildDir -Recurse -Force
    }
    if (Test-Path $SpecPath) {
        Remove-Item -LiteralPath $SpecPath -Force
    }

    Write-Host "Built dist\NovelAgentWorkbench\NovelAgentWorkbench.exe"
    Write-Host "Cleaned PyInstaller intermediate build files"
}
finally {
    Pop-Location
}
