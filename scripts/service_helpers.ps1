param()

function Get-WallyAgentAppPath {
    if ($script:WallyAgentAppPath) {
        return ([string]$script:WallyAgentAppPath).Trim('"').TrimEnd('\')
    }
    return "C:\Apps\WallyAgent"
}

function Get-WallyAgentServiceName {
    $appPath = Get-WallyAgentAppPath
    $name = Split-Path -Leaf $appPath
    if ([string]::IsNullOrWhiteSpace($name)) {
        return "WallyAgent"
    }
    return $name
}

function Get-WallyAgentProcess {
    param([string]$Kind = "all")

    $appPath = Get-WallyAgentAppPath
    $all = Get-CimInstance Win32_Process |
        Where-Object {
            $_.CommandLine -and $_.CommandLine -like "*$appPath*"
        }

    if ($Kind -eq "web") {
        return $all | Where-Object { $_.CommandLine -like "*streamlit*run*app.py*" }
    }
    if ($Kind -eq "telegram") {
        return $all | Where-Object { $_.CommandLine -like "*run_maria_telegram.py*" }
    }
    return $all | Where-Object {
        $_.CommandLine -like "*streamlit*run*app.py*" -or
        $_.CommandLine -like "*run_maria_telegram.py*"
    }
}

function Get-WallyAgentPython {
    $candidates = @()

    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        try {
            $version = & py -3.12 --version 2>$null
            if ($LASTEXITCODE -eq 0 -and $version -like "Python 3.12*") {
                return @{ Command = "py"; Arguments = @("-3.12") }
            }
        } catch {
        }
    }

    $shortcutRoots = @(
        "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Python 3.12",
        "C:\Users\Administrator\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Python 3.12",
        "C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Python 3.12"
    )
    foreach ($root in $shortcutRoots) {
        if (Test-Path $root) {
            Get-ChildItem -LiteralPath $root -Filter "*.lnk" -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -like "Python 3.12*" } |
                ForEach-Object {
                    try {
                        $shell = New-Object -ComObject WScript.Shell
                        $link = $shell.CreateShortcut($_.FullName)
                        if ($link.TargetPath -and (Test-Path $link.TargetPath) -and $link.TargetPath -notlike "*WindowsApps*") {
                            $candidates += Get-Item -LiteralPath $link.TargetPath
                        }
                    } catch {
                    }
                }
        }
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand -and $pythonCommand.Source -notlike "*\WindowsApps\python.exe") {
        try {
            $version = & $pythonCommand.Source --version 2>$null
            if ($version -like "Python 3.12*") {
                return @{ Command = $pythonCommand.Source; Arguments = @() }
            }
            $candidates += Get-Item -LiteralPath $pythonCommand.Source -ErrorAction SilentlyContinue
        } catch {
        }
    }

    $candidateRoots = @(
        "$env:LOCALAPPDATA\Programs\Python",
        "C:\Users\Administrator\AppData\Local\Programs\Python",
        "$env:ProgramFiles\Python312",
        "$env:ProgramFiles\Python311",
        "C:\Python312",
        "C:\Python311"
    )

    foreach ($root in $candidateRoots) {
        if (Test-Path $root) {
            $candidates += Get-ChildItem -LiteralPath $root -Recurse -Filter python.exe -ErrorAction SilentlyContinue
        }
    }

    $pythonExe = $candidates |
        Where-Object { $_ -and $_.FullName -and $_.FullName -notlike "*\WindowsApps\*" -and $_.FullName -notlike "*\.venv\*" } |
        Sort-Object FullName -Descending |
        Select-Object -First 1

    if ($pythonExe) {
        return @{ Command = $pythonExe.FullName; Arguments = @() }
    }

    return $null
}

function Test-WallyAgentVenv {
    param([string]$AppPath)
    $venvPython = Join-Path $AppPath ".venv\Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        return $false
    }
    try {
        $version = & $venvPython --version 2>&1
        return ($LASTEXITCODE -eq 0 -and $version -like "Python 3.12*")
    } catch {
        return $false
    }
}

function Ensure-WallyAgentVenv {
    param([string]$AppPath)
    $AppPath = ([string]$AppPath).Trim('"').TrimEnd('\')
    $venvPath = Join-Path $AppPath ".venv"
    $venvPython = Join-Path $AppPath ".venv\Scripts\python.exe"

    if (-not (Test-WallyAgentVenv -AppPath $AppPath)) {
        if (Test-Path $venvPath) {
            $resolvedApp = (Resolve-Path -LiteralPath $AppPath).Path.TrimEnd('\')
            $resolvedVenv = (Resolve-Path -LiteralPath $venvPath).Path.TrimEnd('\')
            if ($resolvedVenv -ne (Join-Path $resolvedApp ".venv")) {
                throw "Ruta .venv insegura: $resolvedVenv"
            }
            Write-Host "Entorno virtual invalido o apunta a una ruta de Python anterior. Recreando .venv..."
            Remove-Item -LiteralPath $venvPath -Recurse -Force
        }

        $python = Get-WallyAgentPython
        if (-not $python) {
            throw "No se encontro Python 3.12 x64. En este servidor revise el acceso directo de Python 3.12 o reinstale Python marcando 'Add Python to environment variables'."
        }

        Write-Host "Creando entorno virtual con Python:" $python.Command
        & $python.Command @($python.Arguments) -m venv $venvPath
    }

    if (-not (Test-Path $venvPython)) {
        throw "No se pudo crear el entorno virtual en $venvPath"
    }

    & $venvPython -m pip install --upgrade pip
    & (Join-Path $AppPath ".venv\Scripts\pip.exe") install -r (Join-Path $AppPath "requirements.txt")
}

function Stop-WallyAgentProcess {
    param([string]$Kind = "all")
    $processes = @(Get-WallyAgentProcess -Kind $Kind)
    foreach ($process in $processes) {
        $live = Get-Process -Id $process.ProcessId -ErrorAction SilentlyContinue
        if ($live) {
            Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }
    return $processes.Count
}

function Show-WallyAgentStatus {
    $serviceName = Get-WallyAgentServiceName
    $web = @(Get-WallyAgentProcess -Kind "web")
    $telegram = @(Get-WallyAgentProcess -Kind "telegram")

    Write-Host ""
    Write-Host "Estado de servicios $serviceName"
    Write-Host "-----------------------------"
    Write-Host ("$serviceName Web:     " + $(if ($web.Count -gt 0) { "Activo ($($web.Count) proceso(s))" } else { "Detenido" }))
    Write-Host ("Mar-IA Telegram:    " + $(if ($telegram.Count -gt 0) { "Activo ($($telegram.Count) proceso(s))" } else { "Detenido" }))

    if ($web.Count -gt 0) {
        Write-Host ""
        Write-Host "Procesos Web:"
        $web | Select-Object ProcessId, CommandLine | Format-Table -AutoSize
    }
    if ($telegram.Count -gt 0) {
        Write-Host ""
        Write-Host "Procesos Telegram:"
        $telegram | Select-Object ProcessId, CommandLine | Format-Table -AutoSize
    }
}
