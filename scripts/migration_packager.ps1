# Wally Migration Packager Script
# Este script detiene los servicios, empaqueta las configuraciones, bases de datos locales y genera el backup (.bak) de SQL Server.

$ErrorActionPreference = "Continue"

$backupFolder = "C:\Wally_Migration_Backup"
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "INICIANDO EMPAQUETADO DE MIGRACION DE WALLY" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

# 1. Crear directorio de backup
if (-not (Test-Path -Path $backupFolder)) {
    New-Item -ItemType Directory -Path $backupFolder -Force | Out-Null
    Write-Host "[OK] Directorio de backup creado: $backupFolder" -ForegroundColor Green
}

# 2. Detener servicios activos para evitar escrituras en bases de datos
Write-Host "`n1. Deteniendo procesos de Wally4 y WallyAgent..." -ForegroundColor Yellow
$wally4Helpers = "C:\Apps\Wally4\scripts\service_helpers.ps1"
if (Test-Path $wally4Helpers) {
    . $wally4Helpers
    Stop-WallyProcess -Force
}
$wallyAgentHelpers = "C:\Apps\WallyAgent\scripts\service_helpers.ps1"
if (Test-Path $wallyAgentHelpers) {
    . $wallyAgentHelpers
    Stop-WallyAgentProcess -Force
}
Get-CimInstance Win32_Process | Where-Object { ($_.CommandLine -like "*Wally4*" -or $_.CommandLine -like "*WallyAgent*") -and $_.Name -in "python.exe","streamlit.exe" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Write-Host "[OK] Procesos detenidos." -ForegroundColor Green

# 3. Copiar archivos .env de configuraciones
Write-Host "`n2. Copiando archivos de configuracion (.env)..." -ForegroundColor Yellow
$envWally4 = "C:\Apps\Wally4\.env"
$envWallyAgent = "C:\Apps\WallyAgent\.env"

if (Test-Path $envWally4) {
    Copy-Item -Path $envWally4 -Destination (Join-Path $backupFolder "Wally4.env") -Force
    Write-Host "[OK] Copiado .env de Wally4" -ForegroundColor Green
} else {
    Write-Warning "No se encontro el archivo .env de Wally4."
}

if (Test-Path $envWallyAgent) {
    Copy-Item -Path $envWallyAgent -Destination (Join-Path $backupFolder "WallyAgent.env") -Force
    Write-Host "[OK] Copiado .env de WallyAgent" -ForegroundColor Green
} else {
    Write-Warning "No se encontro el archivo .env de WallyAgent."
}

# 4. Copiar bases de datos SQLite locales
Write-Host "`n3. Copiando bases de datos SQLite locales..." -ForegroundColor Yellow
$sqliteWally4 = "C:\ProgramData\Wally4\wally_agent.sqlite"
$sqliteWallyAgent = "C:\Apps\WallyAgent\data\wally_agent.sqlite"

if (Test-Path $sqliteWally4) {
    Copy-Item -Path $sqliteWally4 -Destination (Join-Path $backupFolder "Wally4_wally_agent.sqlite") -Force
    Write-Host "[OK] Copiada base SQLite principal de Wally4" -ForegroundColor Green
} else {
    Write-Warning "No se encontro la base SQLite de Wally4 en ProgramData."
}

if (Test-Path $sqliteWallyAgent) {
    Copy-Item -Path $sqliteWallyAgent -Destination (Join-Path $backupFolder "WallyAgent_wally_agent.sqlite") -Force
    Write-Host "[OK] Copiada base SQLite de WallyAgent" -ForegroundColor Green
} else {
    Write-Warning "No se encontro la base SQLite de WallyAgent en su carpeta de datos."
}

# 5. Generar backup de la base de datos SQL Server (WallyBD)
Write-Host "`n4. Generando Backup (.bak) de SQL Server (WallyBD)..." -ForegroundColor Yellow
$sqlBackupPath = Join-Path $backupFolder "WallyBD.bak"
$backupQuery = "BACKUP DATABASE [WallyBD] TO DISK = N'$sqlBackupPath' WITH NOFORMAT, INIT, NAME = N'WallyBD-Full Database Backup', SKIP, NOREWIND, NOUNLOAD, STATS = 10"

# Intentar usar sqlcmd con la instancia por defecto o la configurada
$sqlServerInstance = "NAZGUL\SB22"
if (Test-Path $envWally4) {
    $serverConfigured = Get-Content $envWally4 | Where-Object { $_ -match '^SQL_SERVER=' } | Select-Object -First 1
    if ($serverConfigured) {
        $sqlServerInstance = ($serverConfigured -replace '^SQL_SERVER=', '').Trim()
    }
}

Write-Host "Conectando a la instancia SQL Server: $sqlServerInstance..."
& sqlcmd -S $sqlServerInstance -E -Q $backupQuery
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Backup de SQL Server (WallyBD) generado exitosamente en: $sqlBackupPath" -ForegroundColor Green
} else {
    Write-Error "No se pudo realizar el backup de SQL Server mediante sqlcmd. Por favor, hagalo manualmente desde SQL Server Management Studio (SSMS) guardando en '$sqlBackupPath'."
}

Write-Host "`n=============================================" -ForegroundColor Cyan
Write-Host "PROCESO DE EMPAQUETADO FINALIZADO" -ForegroundColor Cyan
Write-Host "Por favor, copie la carpeta completa '$backupFolder'" -ForegroundColor Cyan
Write-Host "al nuevo servidor y ejecute el proceso de restauracion." -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
