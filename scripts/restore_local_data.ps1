param(
    [Parameter(Mandatory = $true)]
    [string]$SourceSqlite,
    [string]$AppPath = "C:\Apps\WallyAgent"
)

$ErrorActionPreference = "Stop"
$AppPath = ([string]$AppPath).Trim('"').TrimEnd('\')
$SourceSqlite = ([string]$SourceSqlite).Trim('"')

if (-not (Test-Path -LiteralPath $SourceSqlite)) {
    throw "No existe el archivo origen: $SourceSqlite"
}
if (-not (Test-Path -LiteralPath $AppPath)) {
    throw "No existe la carpeta de WallyAgent: $AppPath"
}

$python = Join-Path $AppPath ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "No existe Python del entorno virtual: $python"
}

$validation = @"
import sqlite3, sys
path = sys.argv[1]
required = ["pto_sucursal", "pto_vendedor", "pto_linea_sucursal", "app_parametros"]
conn = sqlite3.connect(path)
try:
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    missing = [name for name in required if name not in tables]
    if missing:
        raise SystemExit("SQLite no parece ser de WallyAgent. Faltan tablas: " + ", ".join(missing))
finally:
    conn.close()
"@

$tempValidation = Join-Path $env:TEMP "wallyagent_validate_sqlite.py"
Set-Content -LiteralPath $tempValidation -Value $validation -Encoding UTF8
& $python $tempValidation $SourceSqlite
if ($LASTEXITCODE -ne 0) {
    throw "Validacion fallida del SQLite origen."
}

$envFile = Join-Path $AppPath ".env"
$targetSqlite = Join-Path $AppPath "data\wally_agent.sqlite"

if (Test-Path -LiteralPath $envFile) {
    $configured = Get-Content -LiteralPath $envFile |
        Where-Object { $_ -match '^WALLY_AGENT_SQLITE_PATH=' } |
        Select-Object -First 1
    if ($configured) {
        $value = ($configured -replace '^WALLY_AGENT_SQLITE_PATH=', '').Trim()
        if ($value) {
            $targetSqlite = $value
        }
    }
}

$targetDir = Split-Path -Parent $targetSqlite
New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

if (Test-Path -LiteralPath $targetSqlite) {
    $backupDir = Join-Path $AppPath "data\backups"
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backup = Join-Path $backupDir "wally_agent_before_restore_$stamp.sqlite"
    Copy-Item -LiteralPath $targetSqlite -Destination $backup -Force
    Write-Host "Backup previo creado:"
    Write-Host $backup
}

Copy-Item -LiteralPath $SourceSqlite -Destination $targetSqlite -Force

Write-Host "Base local restaurada en:"
Write-Host $targetSqlite
Write-Host ""
Write-Host "Reinicie WallyAgent para tomar los datos restaurados."
