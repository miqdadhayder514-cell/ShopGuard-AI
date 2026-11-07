<#
.SYNOPSIS
    Installs ShopGuard AI as a per-user Windows logon task.
.DESCRIPTION
    Starts the local API and camera processing engine at user logon. The agent
    always initializes DISARMED; cameras are monitored only after an authorized
    ARM request. The API runner refuses non-loopback bindings. Configures private
    Tailscale Serve access for an explicitly allowlisted Tailscale user.
#>

param(
    [string]$TaskName = "ShopGuardAI_Engine"
)

$ErrorActionPreference = "Stop"

$ProjectDir = (Get-Item -Path $PSScriptRoot).Parent.FullName
$PythonExe = Join-Path $ProjectDir "venv\Scripts\python.exe"
$Launcher = Join-Path $ProjectDir "tools\start_agent.ps1"
$AllowedUsersFile = Join-Path $ProjectDir "config\tailscale_allowed_users.txt"
$TailscaleCommand = Get-Command "tailscale.exe" -ErrorAction SilentlyContinue
if (-not $TailscaleCommand) {
    $TailscalePath = Join-Path $env:ProgramFiles "Tailscale\tailscale.exe"
    if (Test-Path $TailscalePath -PathType Leaf) {
        $TailscaleExe = $TailscalePath
    } else {
        throw "Tailscale CLI was not found. Install and sign in to Tailscale, then rerun this installer."
    }
} else {
    $TailscaleExe = $TailscaleCommand.Source
}

if (-not (Test-Path $PythonExe -PathType Leaf)) {
    throw "Virtual environment python.exe not found at '$PythonExe'. Create the venv and install requirements first."
}
if (-not (Test-Path $Launcher -PathType Leaf)) {
    throw "Agent launcher not found at '$Launcher'."
}

try {
    $StatusJson = & $TailscaleExe status --json 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw ($StatusJson -join "`n")
    }
    $TailscaleStatus = ($StatusJson -join "`n") | ConvertFrom-Json
} catch {
    throw "Tailscale is not ready. Install it, sign in, and verify 'tailscale status'; details: $_"
}

$TailnetHost = ([string]$TailscaleStatus.Self.DNSName).TrimEnd(".")
if ([string]::IsNullOrWhiteSpace($TailnetHost)) {
    throw "Tailscale is signed in, but this device has no MagicDNS hostname. Enable MagicDNS and HTTPS in the tailnet, then rerun."
}

$SuggestedLogin = [string]$TailscaleStatus.Self.UserProfile.LoginName
$Prompt = "Allowed Tailscale user login(s), comma-separated [$SuggestedLogin]"
$AllowedLogins = Read-Host $Prompt
if ([string]::IsNullOrWhiteSpace($AllowedLogins)) {
    $AllowedLogins = $SuggestedLogin
}
$AllowedUsers = @(
    $AllowedLogins -split "," |
        ForEach-Object { $_.Trim().ToLowerInvariant() } |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
        Select-Object -Unique
)
if ($AllowedUsers.Count -eq 0 -or ($AllowedUsers | Where-Object { $_ -match "\s" })) {
    throw "Enter one or more valid Tailscale login names separated by commas."
}

$ServeStatus = & $TailscaleExe serve status 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Could not inspect current Tailscale Serve configuration: $($ServeStatus -join ' ')"
}
$ServeStatusText = $ServeStatus -join "`n"
$ServeAlreadyConfigured = $ServeStatusText -match "http://127\.0\.0\.1:8000"
if (-not [string]::IsNullOrWhiteSpace($ServeStatusText) -and
    $ServeStatusText -notmatch "(?i)no serve config" -and
    -not $ServeAlreadyConfigured) {
    throw "Tailscale Serve already has a configuration. To avoid replacing existing routes, ShopGuard was not added. Configure a dedicated HTTPS route to http://127.0.0.1:8000, or remove the existing Serve configuration and rerun."
}

New-Item -ItemType Directory -Path (Split-Path $AllowedUsersFile -Parent) -Force | Out-Null
Set-Content -Path $AllowedUsersFile -Value $AllowedUsers -Encoding UTF8

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
    $Deadline = (Get-Date).AddSeconds(60)
    do {
        Start-Sleep -Seconds 2
        try {
            $Health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 3
            if ($Health) { break }
        } catch {
            if ((Get-Date) -ge $Deadline) {
                throw "The agent did not become healthy within 60 seconds. Check $ProjectDir\data\logs\agent-startup.log."
            }
        }
    } while ((Get-Date) -lt $Deadline)

    if (-not $ServeAlreadyConfigured) {
        $ServeOutput = & $TailscaleExe serve --bg --yes 8000 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "Tailscale Serve setup failed: $($ServeOutput -join ' '). Ensure HTTPS certificates are enabled for the tailnet, then rerun the installer."
        }
    }

    Write-Host "[SUCCESS] Task '$TaskName' installed and started." -ForegroundColor Green
    Write-Host "[SUCCESS] Private Tailscale Serve forwards https://$TailnetHost/ to the local agent." -ForegroundColor Green
    Write-Host "Allowed Tailscale identities: $($AllowedUsers -join ', ')" -ForegroundColor Gray
    Write-Host "The agent starts DISARMED. Runtime output: $ProjectDir\data\logs\agent-startup.log" -ForegroundColor Yellow
    Write-Host "Automatic recovery: up to five restarts, one minute apart." -ForegroundColor Gray
} catch {
    Write-Error "Failed to finish ShopGuard setup: $_"
    exit 1
}
