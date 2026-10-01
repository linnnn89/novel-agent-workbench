param([switch]$SkipBuild)
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$python = Join-Path $repo '.venv\Scripts\python.exe'
$app = Join-Path $repo 'dist\NovelAgentWorkbench'
$release = Join-Path $repo 'dist\release'
$work = Join-Path $repo ('build\windows-release-' + [guid]::NewGuid().ToString('N'))
$iexpress = Join-Path $env:WINDIR 'System32\iexpress.exe'
if (-not (Test-Path -LiteralPath $iexpress)) { throw 'Windows IExpress is unavailable.' }
if (-not $SkipBuild) {
    & (Join-Path $PSScriptRoot 'build_windows_exe.ps1') -SkipInstall
    if ($LASTEXITCODE -ne 0) { throw 'EXE build failed.' }
}
& $python (Join-Path $PSScriptRoot 'verify_release_payload.py') $app
if ($LASTEXITCODE -ne 0) { throw 'Release privacy checks failed.' }
try {
    $payload = Join-Path $work 'payload\NovelAgentWorkbench'
    $package = Join-Path $work 'package'
    New-Item -ItemType Directory -Path $payload, $package, $release -Force | Out-Null
    foreach ($name in @('NovelAgentWorkbench.exe', '_internal')) {
        Copy-Item -LiteralPath (Join-Path $app $name) -Destination (Join-Path $payload $name) -Recurse
    }
    Copy-Item -LiteralPath (Join-Path $repo 'LICENSE') -Destination $payload
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = Join-Path $package 'NovelAgentWorkbench.zip'
    [IO.Compression.ZipFile]::CreateFromDirectory((Join-Path $work 'payload'), $zip, 'Optimal', $false)
    $hash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash
    [IO.File]::WriteAllText((Join-Path $package 'payload.sha256'), $hash, [Text.Encoding]::ASCII)
    $setup = Get-Content -LiteralPath (Join-Path $repo 'packaging\install_windows.ps1') -Raw -Encoding UTF8
    [IO.File]::WriteAllText((Join-Path $package 'setup.ps1'), $setup, (New-Object Text.UTF8Encoding($true)))
    $output = Join-Path $work 'NovelAgentWorkbench-Setup-x64.exe'
    $sed = @"
[Version]
Class=IEXPRESS
SEDVersion=3
[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=1
HideExtractAnimation=1
UseLongFileName=1
InsideCompressed=0
CAB_FixedSize=0
CAB_ResvCodeSigning=0
RebootMode=N
InstallPrompt=%InstallPrompt%
DisplayLicense=%DisplayLicense%
FinishMessage=%FinishMessage%
TargetName=%TargetName%
FriendlyName=%FriendlyName%
AppLaunched=%AppLaunched%
PostInstallCmd=%PostInstallCmd%
AdminQuietInstCmd=%AdminQuietInstCmd%
UserQuietInstCmd=%UserQuietInstCmd%
SourceFiles=SourceFiles
[Strings]
InstallPrompt=
DisplayLicense=
FinishMessage=
TargetName=$output
FriendlyName=Novel Agent Workbench Setup
AppLaunched=powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -STA -File setup.ps1
PostInstallCmd=<None>
AdminQuietInstCmd=powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -STA -File setup.ps1 -Quiet -NoLaunch
UserQuietInstCmd=powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -STA -File setup.ps1 -Quiet -NoLaunch
FILE0="setup.ps1"
FILE1="NovelAgentWorkbench.zip"
FILE2="payload.sha256"
[SourceFiles]
SourceFiles0=$package\
[SourceFiles0]
%FILE0%=
%FILE1%=
%FILE2%=
"@
    $sedPath = Join-Path $work 'setup.sed'
    [IO.File]::WriteAllText($sedPath, $sed, [Text.Encoding]::ASCII)
    $process = Start-Process -FilePath $iexpress -ArgumentList @('/N', '/Q', $sedPath) -WindowStyle Hidden -Wait -PassThru
    if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $output)) { throw 'IExpress installer build failed.' }
    Copy-Item -LiteralPath $output -Destination $release -Force
    Copy-Item -LiteralPath $zip -Destination $release -Force
    $checksums = foreach ($name in @('NovelAgentWorkbench.zip', 'NovelAgentWorkbench-Setup-x64.exe')) {
        (Get-FileHash -LiteralPath (Join-Path $release $name) -Algorithm SHA256).Hash.ToLowerInvariant() + '  ' + $name
    }
    [IO.File]::WriteAllLines((Join-Path $release 'SHA256SUMS.txt'), $checksums, [Text.Encoding]::ASCII)
    Write-Host "Release artifacts: $release"
}
finally {
    $full = [IO.Path]::GetFullPath($work)
    if ([IO.Path]::GetDirectoryName($full) -ne (Join-Path $repo 'build') -or
        [IO.Path]::GetFileName($full) -notmatch '^windows-release-[a-f0-9]{32}$') { throw 'Unsafe build cleanup path.' }
    if (Test-Path -LiteralPath $full) { Remove-Item -LiteralPath $full -Recurse -Force }
}
