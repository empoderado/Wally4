param(
    [string]$AppPath = "C:\Apps\WallyAgent"
)

$ErrorActionPreference = "Stop"
$AppPath = ([string]$AppPath).Trim('"').TrimEnd('\')
$script:WallyAgentAppPath = $AppPath
. (Join-Path $AppPath "scripts\service_helpers.ps1")

$serviceName = Get-WallyAgentServiceName
$taskFolder = "\Servicios$serviceName\"
$taskName = "Iniciar Servicios $serviceName"
$startScript = Join-Path $AppPath "scripts\start_services.ps1"

function Ensure-TaskFolder {
    $service = New-Object -ComObject "Schedule.Service"
    $service.Connect()
    $root = $service.GetFolder("\")
    try {
        $null = $root.GetFolder($taskFolder.Trim("\"))
    } catch {
        $null = $root.CreateFolder($taskFolder.Trim("\"))
    }
}

function Remove-ObsoleteTasks {
    $obsoleteNames = @(
        "Crear Tareas Servicios WallyAgent",
        "Iniciar WallyAgent",
        "Iniciar MarIA Telegram",
        "Reiniciar Servicios WallyAgent",
        "Detener Servicios WallyAgent",
        "Diagnostico WallyAgent",
        "Iniciar Servicios WallyAgent",
        "Iniciar Servicios Wally4"
    )

    foreach ($name in $obsoleteNames) {
        try {
            Unregister-ScheduledTask -TaskPath $taskFolder -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
        } catch {
        }
        try {
            Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
        } catch {
        }
    }
}

function Register-StartTask {
    Ensure-TaskFolder
    Remove-ObsoleteTasks

    $currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $taskAction = New-ScheduledTaskAction `
        -Execute "powershell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$startScript`" -AppPath `"$AppPath`""
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $currentUser
    $principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType Interactive -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit (New-TimeSpan -Hours 0)

    Register-ScheduledTask `
        -TaskName $taskName `
        -TaskPath $taskFolder `
        -Action $taskAction `
        -Trigger $trigger `
        -Principal $principal `
        -Settings $settings `
        -Force | Out-Null

    Write-Host "Tarea programada creada o actualizada: $taskFolder$taskName"
}

Set-Location $AppPath

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

Write-Host "Preparando entorno $serviceName..."
Ensure-WallyAgentVenv -AppPath $AppPath

Write-Host "Actualizando tarea programada..."
Register-StartTask

Write-Host "Deteniendo procesos existentes para reinicio limpio..."
$telegramStopped = Stop-WallyAgentProcess -Kind "telegram"
$webStopped = Stop-WallyAgentProcess -Kind "web"
Write-Host "Procesos Mar-IA Telegram detenidos: $telegramStopped"
Write-Host "Procesos WallyAgent Web detenidos: $webStopped"

Start-Sleep -Seconds 2
Write-Host "Iniciando servicios $serviceName..."
& (Join-Path $AppPath "scripts\start_services.ps1") -AppPath $AppPath
