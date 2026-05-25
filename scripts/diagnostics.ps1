param(
    [string]$AppPath = "C:\Apps\WallyAgent"
)

$ErrorActionPreference = "Stop"
$AppPath = ([string]$AppPath).Trim('"').TrimEnd('\')
Set-Location $AppPath

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "No existe .venv. Ejecute primero el comando de inicio de servicios de esta carpeta."
}

$env:PYTHONPATH = $AppPath
& ".\.venv\Scripts\python.exe" "scripts\diagnostics.py"
