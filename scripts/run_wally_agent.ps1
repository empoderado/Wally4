param(
    [string]$AppPath = ""
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($AppPath)) {
    $AppPath = Resolve-Path (Join-Path $scriptRoot "..")
}
$AppPath = ([string]$AppPath).Trim('"').TrimEnd('\')
$script:WallyAgentAppPath = $AppPath
. (Join-Path $AppPath "scripts\service_helpers.ps1")
Set-Location $AppPath

function Get-EnvValue {
    param(
        [string]$Key,
        [string]$Default = ""
    )
    $envPath = Join-Path $AppPath ".env"
    if (-not (Test-Path $envPath)) {
        return $Default
    }
    $line = Get-Content $envPath | Where-Object { $_ -match "^\s*$Key\s*=" } | Select-Object -First 1
    if (-not $line) {
        return $Default
    }
    return (($line -split "=", 2)[1]).Trim()
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

Ensure-WallyAgentVenv -AppPath $AppPath

$env:PYTHONPATH = $AppPath
$appHost = Get-EnvValue -Key "APP_HOST" -Default "127.0.0.1"
$appPort = Get-EnvValue -Key "APP_PORT" -Default "8503"
& ".\.venv\Scripts\streamlit.exe" run "app.py" --server.address $appHost --server.port $appPort
