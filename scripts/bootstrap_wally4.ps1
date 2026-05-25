param(
    [string]$SourcePath = "C:\Apps\WallyAgent",
    [string]$TargetPath = "C:\Apps\Wally4",
    [switch]$ResetEnv
)

$ErrorActionPreference = "Stop"

$SourcePath = ([string]$SourcePath).Trim('"').TrimEnd('\')
$TargetPath = ([string]$TargetPath).Trim('"').TrimEnd('\')

if (-not (Test-Path -LiteralPath $SourcePath)) {
    throw "No existe SourcePath: $SourcePath"
}

$resolvedSource = (Resolve-Path -LiteralPath $SourcePath).Path.TrimEnd('\')
if ($resolvedSource -eq $TargetPath) {
    throw "SourcePath y TargetPath no pueden ser iguales."
}

if (-not (Test-Path -LiteralPath $TargetPath)) {
    New-Item -ItemType Directory -Path $TargetPath | Out-Null
}

$resolvedTarget = (Resolve-Path -LiteralPath $TargetPath).Path.TrimEnd('\')
if ($resolvedTarget -notlike "C:\Apps\*") {
    throw "Por seguridad TargetPath debe estar dentro de C:\Apps. Valor: $resolvedTarget"
}

$excludeDirs = @(".git", ".venv", "__pycache__", ".pytest_cache", "logs")
$excludeFiles = @(".env")
$robocopyArgs = @(
    $resolvedSource,
    $resolvedTarget,
    "/MIR",
    "/XD"
) + ($excludeDirs | ForEach-Object { Join-Path $resolvedSource $_ }) + @(
    "/XF"
) + $excludeFiles + @(
    "/R:2",
    "/W:2",
    "/NFL",
    "/NDL",
    "/NP"
)

Write-Host "Copiando WallyAgent hacia Wally4..."
& robocopy @robocopyArgs
$exitCode = $LASTEXITCODE
if ($exitCode -ge 8) {
    throw "Robocopy fallo con codigo $exitCode"
}

$envExample = Join-Path $resolvedTarget ".env.v4.example"
$envPath = Join-Path $resolvedTarget ".env"
if (-not (Test-Path -LiteralPath $envExample)) {
    throw "No se encontro .env.v4.example en $resolvedTarget"
}
if ($ResetEnv -or -not (Test-Path -LiteralPath $envPath)) {
    Copy-Item -LiteralPath $envExample -Destination $envPath -Force
    Write-Host "Archivo .env creado desde .env.v4.example"
} else {
    Write-Host "Archivo .env existente preservado. Use -ResetEnv si necesita regenerarlo."
}

$programData = "C:\ProgramData\Wally4"
if (-not (Test-Path -LiteralPath $programData)) {
    New-Item -ItemType Directory -Path $programData | Out-Null
}

Write-Host "Wally4 preparado en $resolvedTarget" -ForegroundColor Green
Write-Host "Configuracion esperada: APP_NAME=Wally4, SQL_DATABASE=WallyBD y APP_PORT=8504"
Write-Host "Siguiente paso: crear objetos SQL con database\wallybd\00..03 y luego iniciar servicios desde C:\Apps\Wally4"
