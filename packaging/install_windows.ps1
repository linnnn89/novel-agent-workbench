param(
    [switch]$Quiet,
    [string]$InstallPath = (Join-Path $env:LOCALAPPDATA 'Programs\NovelAgentWorkbench'),
    [switch]$NoShortcuts,
    [switch]$NoLaunch
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.Windows.Forms.Application]::EnableVisualStyles()

if (-not $Quiet) {
    $form = New-Object Windows.Forms.Form
    $form.Text = '安装小说创作工作台'
    $form.ClientSize = New-Object Drawing.Size(580, 260)
    $form.StartPosition = 'CenterScreen'
    $form.FormBorderStyle = 'FixedDialog'
    $form.MaximizeBox = $false
    $intro = New-Object Windows.Forms.Label
    $intro.Text = '安装小说创作工作台' + [Environment]::NewLine + '安装包包含程序与运行依赖。更新已有程序时会保留“用户数据”。'
    $intro.SetBounds(20, 18, 540, 52)
    $pathBox = New-Object Windows.Forms.TextBox
    $pathBox.Text = $InstallPath
    $pathBox.SetBounds(20, 90, 445, 25)
    $browse = New-Object Windows.Forms.Button
    $browse.Text = '浏览…'
    $browse.SetBounds(475, 88, 80, 28)
    $browse.Add_Click({
        $picker = New-Object Windows.Forms.FolderBrowserDialog
        $picker.Description = '请选择程序安装目录'
        if ($picker.ShowDialog() -eq 'OK') { $pathBox.Text = $picker.SelectedPath }
        $picker.Dispose()
    })
    $shortcut = New-Object Windows.Forms.CheckBox
    $shortcut.Text = '创建桌面和开始菜单快捷方式'
    $shortcut.Checked = $true
    $shortcut.SetBounds(20, 135, 360, 25)
    $launch = New-Object Windows.Forms.CheckBox
    $launch.Text = '安装完成后启动'
    $launch.Checked = $true
    $launch.SetBounds(20, 166, 360, 25)
    $install = New-Object Windows.Forms.Button
    $install.Text = '安装'
    $install.DialogResult = 'OK'
    $install.SetBounds(365, 215, 90, 30)
    $cancel = New-Object Windows.Forms.Button
    $cancel.Text = '取消'
    $cancel.DialogResult = 'Cancel'
    $cancel.SetBounds(465, 215, 90, 30)
    $form.Controls.AddRange(@($intro, $pathBox, $browse, $shortcut, $launch, $install, $cancel))
    $form.AcceptButton = $install
    $form.CancelButton = $cancel
    if ($form.ShowDialog() -ne 'OK') { $form.Dispose(); exit 0 }
    $InstallPath = $pathBox.Text
    $NoShortcuts = -not $shortcut.Checked
    $NoLaunch = -not $launch.Checked
    $form.Dispose()
}

$stage = $null
$backup = $null
$cleanBackup = $false
$oldMoved = @()
$newMoved = @()
try {
    if ([string]::IsNullOrWhiteSpace($InstallPath) -or -not [IO.Path]::IsPathRooted($InstallPath)) {
        throw '请选择有效的绝对安装路径。'
    }
    $target = [IO.Path]::GetFullPath($InstallPath).TrimEnd('\')
    foreach ($protected in @([IO.Path]::GetPathRoot($target), $env:WINDIR, $env:USERPROFILE, $env:ProgramFiles, ${env:ProgramFiles(x86)})) {
        if ($protected -and $target -eq $protected.TrimEnd('\')) { throw '请选择独立的程序子目录。' }
    }
    if ($target.StartsWith($env:WINDIR.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw '不能安装到 Windows 系统目录。'
    }
    $cursor = $target
    while ($cursor) {
        if ((Test-Path -LiteralPath $cursor) -and ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw '安装路径不能经过链接或联接目录。'
        }
        $cursor = [IO.Path]::GetDirectoryName($cursor)
    }
    if (Test-Path -LiteralPath $target) {
        $entries = @(Get-ChildItem -LiteralPath $target -Force)
        if ($entries.Count -and -not ((Test-Path -LiteralPath (Join-Path $target 'NovelAgentWorkbench.exe')) -and
                                     (Test-Path -LiteralPath (Join-Path $target '_internal')))) {
            throw '目标目录非空且不是本程序的安装目录，请选择空目录。'
        }
    }
    foreach ($process in Get-Process -Name NovelAgentWorkbench -ErrorAction SilentlyContinue) {
        if ($process.Path -eq (Join-Path $target 'NovelAgentWorkbench.exe')) { throw '请先关闭目标目录中的程序再安装。' }
    }
    $archive = Join-Path $PSScriptRoot 'NovelAgentWorkbench.zip'
    $expectedHash = (Get-Content -LiteralPath (Join-Path $PSScriptRoot 'payload.sha256') -Raw).Trim()
    if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $expectedHash) { throw '安装包校验失败，请重新下载。' }
    $parent = Split-Path -Parent $target
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    $suffix = [guid]::NewGuid().ToString('N')
    $stage = Join-Path $parent ('.novel-setup-stage-' + $suffix)
    $backup = Join-Path $parent ('.novel-setup-backup-' + $suffix)
    New-Item -ItemType Directory -Path $stage, $backup -Force | Out-Null
    $zip = [IO.Compression.ZipFile]::OpenRead($archive)
    try {
        foreach ($entry in $zip.Entries) {
            $resolved = [IO.Path]::GetFullPath((Join-Path $stage $entry.FullName))
            if (-not $resolved.StartsWith($stage + '\', [StringComparison]::OrdinalIgnoreCase)) { throw '安装包路径无效。' }
            if ($entry.FullName -notmatch '^NovelAgentWorkbench/(?:$|NovelAgentWorkbench\.exe$|LICENSE$|_internal(?:/.*)?$)') {
                throw '安装包包含非程序文件。'
            }
        }
    } finally { $zip.Dispose() }
    [IO.Compression.ZipFile]::ExtractToDirectory($archive, $stage)
    $source = Join-Path $stage 'NovelAgentWorkbench'
    if (-not ((Test-Path -LiteralPath (Join-Path $source 'NovelAgentWorkbench.exe')) -and
              (Test-Path -LiteralPath (Join-Path $source '_internal\build_info.json')))) { throw '安装包缺少完整程序。' }
    New-Item -ItemType Directory -Path $target -Force | Out-Null
    foreach ($name in @('NovelAgentWorkbench.exe', '_internal', 'LICENSE')) {
        $old = Join-Path $target $name
        if (Test-Path -LiteralPath $old) {
            if ((Get-Item -LiteralPath $old -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw '已有程序文件不能是链接。' }
            Move-Item -LiteralPath $old -Destination (Join-Path $backup $name)
            $oldMoved += $name
        }
        Move-Item -LiteralPath (Join-Path $source $name) -Destination (Join-Path $target $name)
        $newMoved += $name
    }
    $cleanBackup = $true
}
catch {
    try {
        foreach ($name in $newMoved) { Move-Item -LiteralPath (Join-Path $target $name) -Destination (Join-Path $source $name) }
        foreach ($name in $oldMoved) { Move-Item -LiteralPath (Join-Path $backup $name) -Destination (Join-Path $target $name) }
        $cleanBackup = $true
    } catch { throw "还原失败，旧程序保留在 $backup，请保留该目录。" }
    if (-not $Quiet) { [Windows.Forms.MessageBox]::Show("安装失败：$($_.Exception.Message)", '小说创作工作台') | Out-Null }
    Write-Error $_
    exit 1
}
finally {
    $cleanup = @($stage)
    if ($cleanBackup) { $cleanup += $backup }
    foreach ($temporary in $cleanup) {
        if ($temporary -and (Test-Path -LiteralPath $temporary)) {
            $full = [IO.Path]::GetFullPath($temporary)
            if ([IO.Path]::GetDirectoryName($full) -ne $parent -or
                [IO.Path]::GetFileName($full) -notmatch '^\.novel-setup-(stage|backup)-[a-f0-9]{32}$') {
                throw '拒绝清理非安装临时目录。'
            }
            Remove-Item -LiteralPath $full -Recurse -Force
        }
    }
}

try {
    if (-not $NoShortcuts) {
        $shell = New-Object -ComObject WScript.Shell
        foreach ($folder in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {
            $link = $shell.CreateShortcut((Join-Path $folder '小说创作工作台.lnk'))
            $link.TargetPath = Join-Path $target 'NovelAgentWorkbench.exe'
            $link.WorkingDirectory = $target
            $link.Save()
        }
    }
    if (-not $Quiet) { [Windows.Forms.MessageBox]::Show('安装完成。作品、设置和密钥保存在程序旁的“用户数据”目录。', '小说创作工作台') | Out-Null }
    if (-not $NoLaunch) { Start-Process -FilePath (Join-Path $target 'NovelAgentWorkbench.exe') }
} catch {
    if (-not $Quiet) { [Windows.Forms.MessageBox]::Show("程序已安装，但快捷方式或启动失败：$($_.Exception.Message)", '小说创作工作台') | Out-Null }
    Write-Warning $_
}
