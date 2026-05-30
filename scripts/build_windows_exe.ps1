param(
    [string]$Python = "",
    [switch]$SkipInstall,
    [switch]$RegenerateIcon
)

$ErrorActionPreference = "Stop"

function Invoke-PythonCommand {
    param(
        [string[]]$Command,
        [string[]]$Arguments
    )
    $exe = $Command[0]
    $baseArgs = @()
    if ($Command.Count -gt 1) {
        $baseArgs = $Command[1..($Command.Count - 1)]
    }
    & $exe @baseArgs @Arguments
}

function Test-PythonCommand {
    param([string[]]$Command)
    try {
        Invoke-PythonCommand -Command $Command -Arguments @(
            "-c",
            "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
        ) *> $null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

function Resolve-PythonCommand {
    if ($Python.Trim()) {
        $custom = $Python.Trim() -split "\s+"
        if (Test-PythonCommand -Command $custom) {
            return $custom
        }
        throw "Requested Python command is unavailable or older than 3.10: $Python"
    }

    $candidates = @(
        @("py", "-3.13"),
        @("py", "-3.12"),
        @("py", "-3.11"),
        @("py", "-3.10"),
        @("python")
    )
    foreach ($candidate in $candidates) {
        if (Test-PythonCommand -Command $candidate) {
            return $candidate
        }
    }
    throw "No compatible Python was found. Install Python 3.10 or newer."
}

function Assert-VenvPythonSupported {
    param([string]$VenvPython)
    & $VenvPython -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
    if ($LASTEXITCODE -ne 0) {
        throw "Existing .venv uses Python older than 3.10. Remove .venv and rerun the build."
    }
}

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$IconPath = Join-Path $RepoRoot "src\novel_agent_workbench\assets\novel_agent_workbench.ico"
$LauncherPath = Join-Path $RepoRoot "packaging\desktop_launcher.py"
$AssetsPath = Join-Path $RepoRoot "src\novel_agent_workbench\assets"
$DistRoot = Join-Path $RepoRoot "dist"
$FinalAppDir = Join-Path $DistRoot "NovelAgentWorkbench"
$SpecWorkDir = Join-Path $RepoRoot "build\pyinstaller_spec"
$StagingDist = Join-Path $RepoRoot "build\pyinstaller_dist"
$StagingAppDir = Join-Path $StagingDist "NovelAgentWorkbench"

Push-Location $RepoRoot
try {
    Write-Host "[1/6] Repository root: $RepoRoot"

    if (-not (Test-Path $VenvPython)) {
        $PythonCommand = Resolve-PythonCommand
        Write-Host "[2/6] Creating .venv with: $($PythonCommand -join ' ')"
        Invoke-PythonCommand -Command $PythonCommand -Arguments @("-m", "venv", ".venv")
    }
    else {
        Write-Host "[2/6] Reusing existing .venv"
        Assert-VenvPythonSupported -VenvPython $VenvPython
    }

    if (-not $SkipInstall) {
        Write-Host "[3/6] Installing build dependencies"
        & $VenvPython -m pip install --upgrade pip
        & $VenvPython -m pip install pyinstaller pillow
    }
    else {
        Write-Host "[3/6] Skipping dependency install"
    }

    if ($RegenerateIcon -or -not (Test-Path $IconPath)) {
        Write-Host "[4/6] Regenerating Windows icon"
        & $VenvPython scripts\generate_windows_icon.py
        if ($LASTEXITCODE -ne 0) {
            throw "Icon generation failed."
        }
    }
    else {
        Write-Host "[4/6] Reusing committed Windows icon"
    }

    if (Test-Path $StagingDist) {
        Remove-Item -LiteralPath $StagingDist -Recurse -Force
    }
    if (Test-Path $SpecWorkDir) {
        Remove-Item -LiteralPath $SpecWorkDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $SpecWorkDir | Out-Null

    Write-Host "[5/6] Building PyInstaller application"
    & $VenvPython -m PyInstaller `
        --noconfirm `
        --clean `
        --windowed `
        --name "NovelAgentWorkbench" `
        --distpath $StagingDist `
        --specpath $SpecWorkDir `
        --icon $IconPath `
        --paths "src" `
        --add-data "$AssetsPath;novel_agent_workbench\assets" `
        $LauncherPath
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed."
    }

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

    Write-Host "[6/6] Publishing final EXE while preserving user data"
    if (Test-Path $FinalExe) {
        Remove-Item -LiteralPath $FinalExe -Force
    }
    if (Test-Path $FinalInternal) {
        Remove-Item -LiteralPath $FinalInternal -Recurse -Force
    }
    Copy-Item -LiteralPath $StagingExe -Destination $FinalExe
    Copy-Item -LiteralPath $StagingInternal -Destination $FinalInternal -Recurse

    $BuildDir = Join-Path $RepoRoot "build"
    if (Test-Path $BuildDir) {
        Remove-Item -LiteralPath $BuildDir -Recurse -Force
    }

    Write-Host ""
    Write-Host "Built: $FinalExe"
    Write-Host "Cleaned PyInstaller intermediate build files."
    Write-Host "Preserved dist\NovelAgentWorkbench user-data directory if present."
}
finally {
    Pop-Location
}
