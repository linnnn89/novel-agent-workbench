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
$DistRoot = Join-Path $RepoRoot "dist"
$FinalAppDir = Join-Path $DistRoot "NovelAgentWorkbench"
$StagingDist = Join-Path $RepoRoot "build\pyinstaller_dist"
$StagingAppDir = Join-Path $StagingDist "NovelAgentWorkbench"

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

    if (Test-Path $StagingDist) {
        Remove-Item -LiteralPath $StagingDist -Recurse -Force
    }

    & $VenvPython -m PyInstaller `
        --noconfirm `
        --clean `
        --windowed `
        --name "NovelAgentWorkbench" `
        --distpath $StagingDist `
        --icon $IconPath `
        --paths "src" `
        --add-data "$AssetsPath;novel_agent_workbench\assets" `
        $LauncherPath

    if (-not (Test-Path $StagingAppDir)) {
        throw "PyInstaller did not create expected staging output: $StagingAppDir"
    }
    if (-not (Test-Path $FinalAppDir)) {
        New-Item -ItemType Directory -Path $FinalAppDir | Out-Null
    }

    $FinalExe = Join-Path $FinalAppDir "NovelAgentWorkbench.exe"
    $FinalInternal = Join-Path $FinalAppDir "_internal"
    $StagingExe = Join-Path $StagingAppDir "NovelAgentWorkbench.exe"
    $StagingInternal = Join-Path $StagingAppDir "_internal"

    if (Test-Path $FinalExe) {
        Remove-Item -LiteralPath $FinalExe -Force
    }
    if (Test-Path $FinalInternal) {
        Remove-Item -LiteralPath $FinalInternal -Recurse -Force
    }
    Copy-Item -LiteralPath $StagingExe -Destination $FinalExe
    Copy-Item -LiteralPath $StagingInternal -Destination $FinalInternal -Recurse

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
    Write-Host "Preserved dist\NovelAgentWorkbench user-data directory"
}
finally {
    Pop-Location
}
