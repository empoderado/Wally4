param(
    [string]$AppPath = "C:\Apps\WallyAgent",
    [string]$DestinationDir = ""
)

$ErrorActionPreference = "Stop"
$AppPath = ([string]$AppPath).Trim('"').TrimEnd('\')

if (-not (Test-Path -LiteralPath $AppPath)) {
    throw "No existe la carpeta de WallyAgent: $AppPath"
}

$envFile = Join-Path $AppPath ".env"
$sqlitePath = Join-Path $AppPath "data\wally_agent.sqlite"

if (Test-Path -LiteralPath $envFile) {
    $configured = Get-Content -LiteralPath $envFile |
        Where-Object { $_ -match '^WALLY_AGENT_SQLITE_PATH=' } |
        Select-Object -First 1
    if ($configured) {
        $value = ($configured -replace '^WALLY_AGENT_SQLITE_PATH=', '').Trim()
        if ($value) {
            $sqlitePath = $value
        }
    }
}

if (-not (Test-Path -LiteralPath $sqlitePath)) {
    throw "No existe la base local SQLite: $sqlitePath"
}

if ([string]::IsNullOrWhiteSpace($DestinationDir)) {
    $DestinationDir = Join-Path $AppPath "data\backups"
}

New-Item -ItemType Directory -Force -Path $DestinationDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$destination = Join-Path $DestinationDir "wally_agent_local_data_$stamp.sqlite"

Copy-Item -LiteralPath $sqlitePath -Destination $destination -Force

Write-Host "Backup de datos locales creado:"
Write-Host $destination
Write-Host ""
Write-Host "Copie este archivo al servidor y restaure con:"
Write-Host "powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\restore_local_data.ps1 -SourceSqlite `"$destination`""
