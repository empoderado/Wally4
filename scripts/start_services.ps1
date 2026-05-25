param(
    [string]$AppPath = "C:\Apps\WallyAgent"
)

$ErrorActionPreference = "Stop"
$AppPath = ([string]$AppPath).Trim('"').TrimEnd('\')
$script:WallyAgentAppPath = $AppPath
$helpers = Join-Path $AppPath "scripts\service_helpers.ps1"
. $helpers

Set-Location $AppPath
$serviceName = Get-WallyAgentServiceName

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

$web = @(Get-WallyAgentProcess -Kind "web")
if ($web.Count -eq 0) {
    Start-Process -FilePath "powershell.exe" -ArgumentList @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$AppPath\scripts\run_wally_agent.ps1`"",
        "-AppPath", "`"$AppPath`""
    ) -WindowStyle Hidden -WorkingDirectory $AppPath
    Write-Host "$serviceName Web iniciado en segundo plano."
} else {
    Write-Host "$serviceName Web ya estaba activo. No se crea duplicado."
}

$telegram = @(Get-WallyAgentProcess -Kind "telegram")
if ($telegram.Count -eq 0) {
    Start-Process -FilePath "powershell.exe" -ArgumentList @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$AppPath\scripts\run_maria_telegram.ps1`"",
        "-AppPath", "`"$AppPath`""
    ) -WindowStyle Hidden -WorkingDirectory $AppPath
    Write-Host "Mar-IA Telegram iniciado en segundo plano."
} else {
    Write-Host "Mar-IA Telegram ya estaba activo. No se crea duplicado."
}

Start-Sleep -Seconds 3
Show-WallyAgentStatus
