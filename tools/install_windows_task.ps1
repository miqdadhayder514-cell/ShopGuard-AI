<#
.SYNOPSIS
    Installs ShopGuard AI as a per-user Windows logon task.
.DESCRIPTION
    Starts the local API and camera processing engine at user logon. The agent
    always initializes DISARMED; cameras are monitored only after an authorized
    ARM request. The API runner refuses non-loopback bindings.
#>

param(
    [string]$TaskName = "ShopGuardAI_Engine"
)

$ErrorActionPreference = "Stop"

$ProjectDir = (Get-Item -Path $PSScriptRoot).Parent.FullName
$PythonExe = Join-Path $ProjectDir "venv\Scripts\python.exe"
$Launcher = Join-Path $ProjectDir "tools\start_agent.ps1"

if (-not (Test-Path $PythonExe -PathType Leaf)) {
    throw "Virtual environment python.exe not found at '$PythonExe'. Create the venv and install requirements first."
}
if (-not (Test-Path $Launcher -PathType Leaf)) {
    throw "Agent launcher not found at '$Launcher'."
}

$PowerShellExe = Join-Path $PSHOME "powershell.exe"
$Arguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Launcher`""
$Action = New-ScheduledTaskAction `
    -Execute $PowerShellExe `
    -Argument $Arguments `
    -WorkingDirectory $ProjectDir
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 5 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit 0 `
    -MultipleInstances IgnoreNew
$Principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited

try {
    $ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($ExistingTask) {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Principal $Principal `
        -Description "ShopGuard local API and camera processing (always starts DISARMED; logs to data\logs\agent-startup.log)." |
        Out-Null

    # Start now as well as at future user logons; this starts the API DISARMED.
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "[SUCCESS] Task '$TaskName' installed and started." -ForegroundColor Green
    Write-Host "The agent starts DISARMED. Runtime output: $ProjectDir\data\logs\agent-startup.log" -ForegroundColor Yellow
    Write-Host "Automatic recovery: up to five restarts, one minute apart." -ForegroundColor Gray
} catch {
    Write-Error "Failed to install or start the ShopGuard task '$TaskName': $_"
    exit 1
}
