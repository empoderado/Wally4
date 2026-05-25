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
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

Ensure-WallyAgentVenv -AppPath $AppPath
& (Join-Path $AppPath ".venv\Scripts\python.exe") (Join-Path $AppPath "scripts\apply_wallybd_sql.py") --app-path $AppPath
