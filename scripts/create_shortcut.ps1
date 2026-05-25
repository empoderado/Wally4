param(
    [string]$AppPath = "C:\Apps\WallyAgent",
    [string]$ShortcutName = "WallyAgent.lnk",
    [string]$Url = "http://127.0.0.1:8503/"
)

$ErrorActionPreference = "Stop"

$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop $ShortcutName
$iconPath = Join-Path $AppPath "assets\WallyAgent_icon.ico"

$browserCandidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
) | Where-Object { $_ -and (Test-Path $_) }

if ($browserCandidates.Count -gt 0) {
    $targetPath = $browserCandidates[0]
    $arguments = $Url
} else {
    $targetPath = "$env:WINDIR\System32\cmd.exe"
    $arguments = "/c start `"`" `"$Url`""
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $targetPath
$shortcut.Arguments = $arguments
$shortcut.WorkingDirectory = $AppPath
if (Test-Path $iconPath) {
    $shortcut.IconLocation = $iconPath
}
$shortcut.Description = "Abrir WallyAgent en el navegador"
$shortcut.Save()

Write-Host "Acceso directo creado o actualizado: $shortcutPath" -ForegroundColor Green
if (Test-Path $iconPath) {
    Write-Host "Icono aplicado: $iconPath" -ForegroundColor Green
} else {
    Write-Host "Aviso: no se encontro el icono $iconPath" -ForegroundColor Yellow
}
