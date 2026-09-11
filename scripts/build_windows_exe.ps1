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
            "import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] < (3, 15) else 1)"
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
        throw "Requested Python command is unavailable or outside the supported EXE build range (Python 3.11-3.14): $Python"
    }

    $candidates = @(
        @("py", "-3.14"),
        @("py", "-3.13"),
        @("py", "-3.12"),
        @("py", "-3.11"),
        @("python")
    )
    foreach ($candidate in $candidates) {
        if (Test-PythonCommand -Command $candidate) {
            return $candidate
        }
    }
    throw "No compatible Python was found. Install Python 3.11-3.14 for the Windows EXE build."
}

function Assert-VenvPythonSupported {
    param([string]$VenvPython)
    & $VenvPython -c "import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] < (3, 15) else 1)"
    if ($LASTEXITCODE -ne 0) {
        throw "Existing .venv uses Python outside the supported EXE build range. Recreate .venv with Python 3.11-3.14 and rerun the build."
    }
}

function Assert-BuildPath {
    param([string]$Path)
    $full = [IO.Path]::GetFullPath($Path)
    $root = [IO.Path]::GetFullPath([string]$RepoRoot).TrimEnd('\')
    if (-not $full.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Build path is outside the repository: $full"
    }
    $cursor = $full
    while ($cursor.Length -gt $root.Length) {
        if (Test-Path -LiteralPath $cursor) {
            if ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Build paths must not traverse a junction or symbolic link: $cursor"
            }
        }
        $cursor = [IO.Path]::GetDirectoryName($cursor)
    }
}

function Assert-BuildTree {
    param([string]$Path)
    Assert-BuildPath $Path
    if (-not (Test-Path -LiteralPath $Path)) { return }
    $pending = New-Object 'System.Collections.Generic.Stack[string]'
    $pending.Push($Path)
    while ($pending.Count) {
        $current = Get-Item -LiteralPath $pending.Pop() -Force
        if ($current.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Build payload contains a junction or symbolic link: $($current.FullName)"
        }
        if ($current.PSIsContainer) {
            foreach ($child in Get-ChildItem -LiteralPath $current.FullName -Force) { $pending.Push($child.FullName) }
        }
    }
}

function Get-ProgramFingerprint {
    param([string]$Directory)
    $records = foreach ($name in @('NovelAgentWorkbench.exe', '_internal')) {
        $path = Join-Path $Directory $name
        Assert-BuildTree $path
        if (Test-Path -LiteralPath $path) {
            foreach ($file in Get-ChildItem -LiteralPath $path -File -Recurse -Force | Sort-Object FullName) {
                $relative = $file.FullName.Substring($Directory.Length).TrimStart('\')
                $relative + ':' + (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
            }
        }
    }
    return $records -join "`n"
}

function Publish-WindowsApp {
    param([string]$Candidate, [string]$Destination, [string]$WorkDirectory)
    foreach ($path in @($Candidate, $Destination, $WorkDirectory)) { Assert-BuildPath $path }
    if (-not (Test-Path -LiteralPath (Join-Path $Candidate 'NovelAgentWorkbench.exe') -PathType Leaf) -or
        -not (Test-Path -LiteralPath (Join-Path $Candidate '_internal') -PathType Container)) {
        throw 'The candidate is missing its executable or runtime directory.'
    }
    $dist = Split-Path -Parent $Destination
    New-Item -ItemType Directory -Path $dist -Force | Out-Null
    $publishLock = [IO.File]::Open((Join-Path $dist '.NovelAgentWorkbench.publish.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    try {
        $installedExe = Join-Path $Destination 'NovelAgentWorkbench.exe'
        foreach ($process in Get-Process -Name NovelAgentWorkbench -ErrorAction SilentlyContinue) {
            if ($process.Path -eq $installedExe) { throw 'Please close NovelAgentWorkbench before publishing. The current program is unchanged.' }
        }
        $expected = Get-ProgramFingerprint $Candidate
        $prepared = Join-Path $WorkDirectory 'prepared'
        $backup = Join-Path $RepoRoot ('old/program-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 6))
        foreach ($path in @($prepared, $backup)) { Assert-BuildPath $path }
        New-Item -ItemType Directory -Path $prepared, $backup, $Destination -Force | Out-Null
        foreach ($name in @('NovelAgentWorkbench.exe', '_internal')) {
            Copy-Item -LiteralPath (Join-Path $Candidate $name) -Destination (Join-Path $prepared $name) -Recurse
        }
        if ((Get-ProgramFingerprint $prepared) -cne $expected) { throw 'Prepared program verification failed; the installed program is unchanged.' }
        $original = Get-ProgramFingerprint $Destination
        $oldMoved = @()
        $newMoved = @()
        try {
            foreach ($name in @('NovelAgentWorkbench.exe', '_internal')) {
                $old = Join-Path $Destination $name
                if (Test-Path -LiteralPath $old) {
                    Move-Item -LiteralPath $old -Destination (Join-Path $backup $name)
                    $oldMoved += $name
                }
            }
            foreach ($name in @('NovelAgentWorkbench.exe', '_internal')) {
                Move-Item -LiteralPath (Join-Path $prepared $name) -Destination (Join-Path $Destination $name)
                $newMoved += $name
            }
            if ((Get-ProgramFingerprint $Destination) -cne $expected) { throw 'Published program verification failed.' }
        }
        catch {
            $publishFailure = $_
            foreach ($name in $newMoved) { Move-Item -LiteralPath (Join-Path $Destination $name) -Destination (Join-Path $prepared $name) }
            foreach ($name in $oldMoved) { Move-Item -LiteralPath (Join-Path $backup $name) -Destination (Join-Path $Destination $name) }
            if ((Get-ProgramFingerprint $Destination) -cne $original) { throw "Rollback verification failed. Retained files: $backup and $prepared" }
            throw "Publishing failed; the original program was restored. $publishFailure"
        }
        Write-Host "Old program retained: $backup"
    }
    finally { $publishLock.Dispose() }
}

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$IconPath = Join-Path $RepoRoot "src\novel_agent_workbench\assets\novel_agent_workbench.ico"
$LauncherPath = Join-Path $RepoRoot "packaging\desktop_launcher.py"
$AssetsPath = Join-Path $RepoRoot "src\novel_agent_workbench\assets"
$ModernUiPath = Join-Path $RepoRoot "src\novel_agent_workbench\modern_ui"
$DistRoot = Join-Path $RepoRoot "dist"
$FinalAppDir = Join-Path $DistRoot "NovelAgentWorkbench"
$RunBuildRoot = Join-Path $RepoRoot ('build\windows-exe-' + [guid]::NewGuid().ToString('N'))
$SpecWorkDir = Join-Path $RunBuildRoot 'spec'
$StagingDist = Join-Path $RunBuildRoot 'dist'
$StagingAppDir = Join-Path $StagingDist "NovelAgentWorkbench"

Push-Location $RepoRoot
try {
    Write-Host "[1/6] Repository root: $RepoRoot"

    if (-not (Test-Path $VenvPython)) {
        $PythonCommand = Resolve-PythonCommand
        Write-Host "[2/6] Creating .venv with: $($PythonCommand -join ' ')"
        Invoke-PythonCommand -Command $PythonCommand -Arguments @("-m", "venv", ".venv")
        if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
    }
    else {
        Write-Host "[2/6] Reusing existing .venv"
        Assert-VenvPythonSupported -VenvPython $VenvPython
    }

    if (-not $SkipInstall) {
        Write-Host "[3/6] Installing build dependencies"
        & $VenvPython -m pip install --no-deps -r (Join-Path $RepoRoot 'requirements-windows-build.txt')
        if ($LASTEXITCODE -ne 0) { throw 'Build dependency installation failed.' }
    }
    else {
        Write-Host "[3/6] Skipping dependency install"
    }

    # SkipInstall must use the same validated versions, not silently build a different environment.
    # A script file also avoids Windows PowerShell 5.1 native-argument quote rewriting.
    & $VenvPython (Join-Path $RepoRoot 'scripts/check_build_dependencies.py') (Join-Path $RepoRoot 'requirements-windows-build.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Build dependency versions do not match the lock file.' }
    & $VenvPython -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Build dependencies are inconsistent.' }

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

    Assert-BuildPath $RunBuildRoot
    New-Item -ItemType Directory -Path $SpecWorkDir | Out-Null
    $commit = & git rev-parse HEAD
    if ($LASTEXITCODE -ne 0) { $commit = 'unknown' }
    $dirty = [bool](& git status --porcelain)
    $appVersion = & $VenvPython (Join-Path $RepoRoot 'src/novel_agent_workbench/version.py')
    if ($LASTEXITCODE -ne 0 -or $appVersion -notmatch '^\d+\.\d+\.\d+$') { throw 'Invalid application version.' }
    $BuildInfoPath = Join-Path $RunBuildRoot 'build_info.json'
    $buildInfo = @{ version = $appVersion; built_at = (Get-Date -Format 'o'); commit = $commit; local_changes = $dirty } | ConvertTo-Json
    [IO.File]::WriteAllText($BuildInfoPath, $buildInfo, (New-Object Text.UTF8Encoding($false)))

    Write-Host "[5/6] Building PyInstaller application"
    & $VenvPython -m PyInstaller `
        --noconfirm `
        --clean `
        --windowed `
        --name "NovelAgentWorkbench" `
        --distpath $StagingDist `
        --specpath $SpecWorkDir `
        --workpath (Join-Path $RunBuildRoot 'work') `
        --icon $IconPath `
        --paths "src" `
        --add-data "$AssetsPath;novel_agent_workbench\assets" `
        --add-data "$ModernUiPath;novel_agent_workbench\modern_ui" `
        --add-data "$BuildInfoPath;." `
        --collect-all webview `
        --collect-all deepseek_tokenizer `
        --collect-all clr_loader `
        --hidden-import novel_agent_workbench.modern_desktop `
        --hidden-import novel_agent_workbench.desktop_app `
        $LauncherPath
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed."
    }

    if (-not (Test-Path $StagingAppDir)) {
        throw "PyInstaller did not create expected staging output: $StagingAppDir"
    }
    $FinalExe = Join-Path $FinalAppDir "NovelAgentWorkbench.exe"
    Write-Host "[6/6] Verifying and publishing, with automatic rollback on failure"
    Publish-WindowsApp -Candidate $StagingAppDir -Destination $FinalAppDir -WorkDirectory $RunBuildRoot

    Assert-BuildTree $RunBuildRoot
    Remove-Item -LiteralPath $RunBuildRoot -Recurse -Force

    Write-Host ""
    Write-Host "Built: $FinalExe"
    Write-Host "Cleaned only this run's PyInstaller intermediate files."
    Write-Host "Preserved dist\NovelAgentWorkbench user-data directory if present."
}
finally {
    Pop-Location
}
