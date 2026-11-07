<#
.SYNOPSIS
    Removes ShopGuard AI from Windows Task Scheduler.
#>

param(
    [string]$TaskName = "ShopGuardAI_Engine"
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "     ShopGuard AI - Windows Startup Task Uninstaller      " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($ExistingTask) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "[SUCCESS] Task '$TaskName' has been removed from Windows Task Scheduler." -ForegroundColor Green
    Write-Host "Existing logs and configuration were left untouched." -ForegroundColor Gray
} else {
    Write-Host "[NOTICE] Task '$TaskName' was not found in Windows Task Scheduler." -ForegroundColor Yellow
}
