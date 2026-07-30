# Wally Migration Restorer Script
# Este script se ejecuta en el NUEVO servidor para restaurar configuraciones, bases de datos SQLite locales, base de datos SQL Server y registrar tareas programadas.

$ErrorActionPreference = "Continue"

$backupFolder = "C:\Wally_Migration_Backup"
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "INICIANDO RESTAURACION DE MIGRACION DE WALLY" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

# 1. Validar origen
if (-not (Test-Path -Path $backupFolder)) {
    Write-Error "No se encontro la carpeta de backup en: $backupFolder. Por favor, copiela antes de continuar."
    exit 1
}

# 2. Asegurar existencia de las carpetas de destino de las aplicaciones
$appWally4 = "C:\Apps\Wally4"
$appWallyAgent = "C:\Apps\WallyAgent"

if (-not (Test-Path $appWally4)) {
    Write-Warning "No se encontro la carpeta $appWally4. Asegurese de haber clonado/copiado el codigo fuente ahi."
}
if (-not (Test-Path $appWallyAgent)) {
    Write-Warning "No se encontro la carpeta $appWallyAgent. Asegurese de haber clonado/copiado el codigo fuente ahi."
}

# 3. Restaurar archivos .env
Write-Host "`n1. Restaurando archivos de configuracion (.env)..." -ForegroundColor Yellow
$envBackupWally4 = Join-Path $backupFolder "Wally4.env"
$envBackupWallyAgent = Join-Path $backupFolder "WallyAgent.env"

if (Test-Path $envBackupWally4) {
    Copy-Item -Path $envBackupWally4 -Destination (Join-Path $appWally4 ".env") -Force
    Write-Host "[OK] Restaurado .env en Wally4" -ForegroundColor Green
}
if (Test-Path $envBackupWallyAgent) {
    Copy-Item -Path $envBackupWallyAgent -Destination (Join-Path $appWallyAgent ".env") -Force
    Write-Host "[OK] Restaurado .env en WallyAgent" -ForegroundColor Green
}

# 4. Restaurar SQLite locales
Write-Host "`n2. Restaurando bases de datos SQLite locales..." -ForegroundColor Yellow
$sqliteBackupWally4 = Join-Path $backupFolder "Wally4_wally_agent.sqlite"
$sqliteBackupWallyAgent = Join-Path $backupFolder "WallyAgent_wally_agent.sqlite"

$programDataWally4 = "C:\ProgramData\Wally4"
if (-not (Test-Path $programDataWally4)) {
    New-Item -ItemType Directory -Path $programDataWally4 -Force | Out-Null
}

if (Test-Path $sqliteBackupWally4) {
    Copy-Item -Path $sqliteBackupWally4 -Destination (Join-Path $programDataWally4 "wally_agent.sqlite") -Force
    Write-Host "[OK] Restaurada base SQLite principal en ProgramData\Wally4" -ForegroundColor Green
}

$dataWallyAgent = Join-Path $appWallyAgent "data"
if (-not (Test-Path $dataWallyAgent)) {
    New-Item -ItemType Directory -Path $dataWallyAgent -Force | Out-Null
}
if (Test-Path $sqliteBackupWallyAgent) {
    Copy-Item -Path $sqliteBackupWallyAgent -Destination (Join-Path $dataWallyAgent "wally_agent.sqlite") -Force
    Write-Host "[OK] Restaurada base SQLite en WallyAgent\data" -ForegroundColor Green
}

# 5. Restaurar base de datos SQL Server (WallyBD)
Write-Host "`n3. Restaurando base de datos SQL Server (WallyBD) desde Backup..." -ForegroundColor Yellow
$sqlBackupPath = Join-Path $backupFolder "WallyBD.bak"

if (Test-Path $sqlBackupPath) {
    $sqlServerInstance = "NAZGUL\SB22"
    $envWally4 = Join-Path $appWally4 ".env"
    if (Test-Path $envWally4) {
        $serverConfigured = Get-Content $envWally4 | Where-Object { $_ -match '^SQL_SERVER=' } | Select-Object -First 1
        if ($serverConfigured) {
            $sqlServerInstance = ($serverConfigured -replace '^SQL_SERVER=', '').Trim()
        }
    }

    # Consulta de restauración forzando sobreescritura (WITH REPLACE)
    # Se asume que las rutas de los archivos de base de datos se manejan por defecto del servidor SQL
    $restoreQuery = "RESTORE DATABASE [WallyBD] FROM DISK = N'$sqlBackupPath' WITH REPLACE, RECOVERY, STATS = 10"

    Write-Host "Conectando y restaurando en SQL Server: $sqlServerInstance..."
    & sqlcmd -S $sqlServerInstance -E -Q $restoreQuery
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Base de datos SQL Server (WallyBD) restaurada exitosamente." -ForegroundColor Green
    } else {
        Write-Error "No se pudo restaurar la base de datos SQL Server automaticamente. Por favor, hagalo manualmente desde SSMS usando el archivo en '$sqlBackupPath'."
    }
} else {
    Write-Warning "No se encontro el archivo de backup de SQL Server 'WallyBD.bak' en el directorio de migración."
}

# 6. Registrar tareas programadas de Windows
Write-Host "`n4. Creando Tareas Programadas de Windows para el arranque automatico..." -ForegroundColor Yellow
$taskScriptWally4 = Join-Path $appWally4 "scripts\ensure_services.ps1"
$taskScriptWallyAgent = Join-Path $appWallyAgent "scripts\ensure_services.ps1"

if (Test-Path $taskScriptWally4) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $taskScriptWally4 -AppPath $appWally4
    Write-Host "[OK] Tarea programada registrada para Wally4" -ForegroundColor Green
}
if (Test-Path $taskScriptWallyAgent) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $taskScriptWallyAgent -AppPath $appWallyAgent
    Write-Host "[OK] Tarea programada registrada para WallyAgent" -ForegroundColor Green
}

# 7. Iniciar Servicios
Write-Host "`n5. Iniciando servicios en segundo plano..." -ForegroundColor Yellow
if (Test-Path $appWally4) {
    Start-ScheduledTask -TaskPath "\ServiciosWally4\" -TaskName "Iniciar Servicios Wally4" -ErrorAction SilentlyContinue
}
if (Test-Path $appWallyAgent) {
    Start-ScheduledTask -TaskPath "\ServiciosWallyAgent\" -TaskName "Iniciar Servicios WallyAgent" -ErrorAction SilentlyContinue
}
Write-Host "[OK] Servicios iniciados." -ForegroundColor Green

Write-Host "`n=============================================" -ForegroundColor Cyan
Write-Host "PROCESO DE RESTAURACION DE MIGRACION FINALIZADO" -ForegroundColor Cyan
Write-Host "Verifique el acceso a http://127.0.0.1:8504" -ForegroundColor Cyan
Write-Host "y la conexion del bot de Telegram." -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
