<#
.SYNOPSIS
    Runs the ShopGuard local API agent and appends stdout/stderr to its log.
#>

$ErrorActionPreference = "Stop"
$ProjectDir = (Get-Item -Path $PSScriptRoot).Parent.FullName
$PythonExe = Join-Path $ProjectDir "venv\Scripts\python.exe"
$Runner = Join-Path $ProjectDir "tools\run_agent.py"
$Config = Join-Path $ProjectDir "config\config.yaml"
$LogDir = Join-Path $ProjectDir "data\logs"
$LogPath = Join-Path $LogDir "agent-startup.log"
$OutputLogPath = Join-Path $LogDir "agent-output.log"
$ErrorLogPath = Join-Path $LogDir "agent-errors.log"

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
if (-not (Test-Path $PythonExe -PathType Leaf)) {
    throw "Python environment is missing: $PythonExe"
}

Set-Location $ProjectDir
Add-Content -Path $LogPath -Value "`r`n[$(Get-Date -Format o)] Starting ShopGuard agent; safe startup state is DISARMED."
try {
    $ArgumentList = '-u "{0}" --config "{1}"' -f $Runner, $Config
    $AgentProcess = Start-Process `
        -FilePath $PythonExe `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $ProjectDir `
        -NoNewWindow `
        -Wait `
        -PassThru `
        -RedirectStandardOutput $OutputLogPath `
        -RedirectStandardError $ErrorLogPath
    $AgentExitCode = $AgentProcess.ExitCode
    Add-Content -Path $LogPath -Value "[$(Get-Date -Format o)] Agent exited with code $AgentExitCode."
    exit $AgentExitCode
} catch {
    Add-Content -Path $LogPath -Value "[$(Get-Date -Format o)] Agent launcher failed: $($_.Exception.Message)"
    throw
}
