param(
    [string]$AppPath = "C:\Apps\WallyAgent"
)

$ErrorActionPreference = "Stop"
$AppPath = ([string]$AppPath).Trim('"').TrimEnd('\')
$script:WallyAgentAppPath = $AppPath
. (Join-Path $AppPath "scripts\service_helpers.ps1")

$telegramStopped = Stop-WallyAgentProcess -Kind "telegram"
$webStopped = Stop-WallyAgentProcess -Kind "web"

Write-Host "Procesos Mar-IA Telegram detenidos: $telegramStopped"
Write-Host "Procesos WallyAgent Web detenidos: $webStopped"
Show-WallyAgentStatus
