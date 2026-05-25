param(
    [string]$AppPath = ""
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($AppPath)) {
    $AppPath = Resolve-Path (Join-Path $scriptRoot "..")
}
$AppPath = ([string]$AppPath).Trim('"').TrimEnd('\')
$envPath = Join-Path $AppPath ".env"

if (-not (Test-Path $envPath)) {
    Copy-Item (Join-Path $AppPath ".env.server.example") $envPath
}

$settings = [ordered]@{
    "SQL_DRIVER" = "ODBC Driver 17 for SQL Server"
    "APP_ENV" = "production"
    "USE_MOCK_DATA" = "no"
    "APP_PORT" = "8503"
    "APP_HOST" = "127.0.0.1"
    "WALLY_AGENT_SQLITE_PATH" = "C:\ProgramData\WallyAgent\wally_agent.sqlite"
}

$lines = Get-Content -LiteralPath $envPath
foreach ($key in $settings.Keys) {
    $found = $false
    $lines = $lines | ForEach-Object {
        if ($_ -match "^\s*$([regex]::Escape($key))\s*=") {
            $found = $true
            "$key=$($settings[$key])"
        } else {
            $_
        }
    }
    if (-not $found) {
        $lines += "$key=$($settings[$key])"
    }
}

Set-Content -LiteralPath $envPath -Value $lines -Encoding ASCII
Write-Host "Archivo .env ajustado para servidor:" -ForegroundColor Green
Select-String -LiteralPath $envPath -Pattern "SQL_SERVER|SQL_DATABASE|SQL_DRIVER|APP_ENV|USE_MOCK_DATA|APP_PORT|APP_HOST"
