param([string]$Installer = '', [switch]$KeepTestDirectory)
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if (-not $Installer) { $Installer = Join-Path $repo 'dist\release\NovelAgentWorkbench-Setup-x64.exe' }
$root = Join-Path $repo ('build\installer-test-' + [guid]::NewGuid().ToString('N'))
$extracted = Join-Path $root 'extracted'
$installed = Join-Path $root 'installed'
New-Item -ItemType Directory -Path $extracted -Force | Out-Null
try {
    $extract = Start-Process -FilePath $Installer -ArgumentList @('/Q', ('/T:"' + $extracted + '"'), '/C') -WindowStyle Hidden -Wait -PassThru
    if ($extract.ExitCode -ne 0 -or -not (Test-Path -LiteralPath (Join-Path $extracted 'setup.ps1'))) { throw 'Self-extraction failed.' }
    $actualEntries = @(Get-ChildItem -LiteralPath $extracted -File | Select-Object -ExpandProperty Name | Sort-Object)
    if (($actualEntries -join '|') -ne 'NovelAgentWorkbench.zip|payload.sha256|setup.ps1') { throw 'Unexpected files in installer.' }
    $script = Join-Path $extracted 'setup.ps1'
    & powershell -NoProfile -ExecutionPolicy Bypass -STA -File $script -Quiet -InstallPath $installed -NoShortcuts -NoLaunch
    if ($LASTEXITCODE -ne 0) { throw 'Fresh installation failed.' }
    $exe = Join-Path $installed 'NovelAgentWorkbench.exe'
    $expected = (Get-FileHash -LiteralPath (Join-Path $repo 'dist\NovelAgentWorkbench\NovelAgentWorkbench.exe') -Algorithm SHA256).Hash
    if ((Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash -ne $expected) { throw 'Installed EXE differs from built EXE.' }
    $data = Join-Path $installed '用户数据\test-project'
    New-Item -ItemType Directory -Path $data -Force | Out-Null
    $sentinel = Join-Path $data 'preserve.txt'
    [IO.File]::WriteAllText($sentinel, 'Isolated test data; preserve during upgrade.')
    $before = (Get-FileHash -LiteralPath $sentinel -Algorithm SHA256).Hash
    & powershell -NoProfile -ExecutionPolicy Bypass -STA -File $script -Quiet -InstallPath $installed -NoShortcuts -NoLaunch
    if ($LASTEXITCODE -ne 0 -or (Get-FileHash -LiteralPath $sentinel -Algorithm SHA256).Hash -ne $before) { throw 'Upgrade failed to preserve data.' }
    $unknown = Join-Path $root 'unrelated'
    New-Item -ItemType Directory -Path $unknown -Force | Out-Null
    $untouched = Join-Path $unknown 'keep.txt'
    [IO.File]::WriteAllText($untouched, 'Unrelated directory must not be overwritten.')
    $unknownHash = (Get-FileHash -LiteralPath $untouched -Algorithm SHA256).Hash
    $rejected = Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-STA', '-File', ('"' + $script + '"'), '-Quiet', '-InstallPath', ('"' + $unknown + '"'), '-NoShortcuts', '-NoLaunch') -WindowStyle Hidden -Wait -PassThru -RedirectStandardError (Join-Path $root 'expected-rejection.txt')
    if ($rejected.ExitCode -eq 0 -or (Get-FileHash -LiteralPath $untouched -Algorithm SHA256).Hash -ne $unknownHash) { throw 'Unknown destination was not protected.' }
    $locked = [IO.File]::Open($exe, 'Open', 'Read', 'None')
    try {
        $rejected = Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-STA', '-File', ('"' + $script + '"'), '-Quiet', '-InstallPath', ('"' + $installed + '"'), '-NoShortcuts', '-NoLaunch') -WindowStyle Hidden -Wait -PassThru -RedirectStandardError (Join-Path $root 'expected-lock-rejection.txt')
        if ($rejected.ExitCode -eq 0) { throw 'Locked EXE should stop installation.' }
    } finally { $locked.Dispose() }
    if ((Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash -ne $expected -or
        (Get-FileHash -LiteralPath $sentinel -Algorithm SHA256).Hash -ne $before) { throw 'Failed installation changed existing files.' }
    & (Join-Path $repo '.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'verify_release_payload.py') $installed
    if ($LASTEXITCODE -ne 0) { throw 'Installed payload privacy check failed.' }
    Write-Host 'PASS: self-extraction, fresh install, data-preserving upgrade, unrelated-folder rejection, and locked-EXE protection'
    Write-Host "Isolated install: $installed"
}
finally {
    if (-not $KeepTestDirectory) {
        $full = [IO.Path]::GetFullPath($root)
        if ([IO.Path]::GetDirectoryName($full) -ne (Join-Path $repo 'build') -or
            [IO.Path]::GetFileName($full) -notmatch '^installer-test-[a-f0-9]{32}$') { throw 'Unsafe test cleanup path.' }
        Remove-Item -LiteralPath $full -Recurse -Force
    }
}
