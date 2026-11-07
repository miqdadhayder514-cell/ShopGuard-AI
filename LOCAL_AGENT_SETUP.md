# ShopGuard AI – Local Security Agent Setup Guide (Windows)

This document provides step-by-step instructions for deploying and running the **ShopGuard AI Phase 2 Local Security Agent** on Windows 10/11 computers.

---

## 1. Prerequisites

1. **Operating System:** Windows 10 or 11 (64-bit).
2. **Python:** Version 3.10 to 3.14 (64-bit).
3. **Hardware Requirements:**
   - 4-core CPU or higher (Intel Core i3/i5/i7 or AMD Ryzen).
   - 8 GB RAM (minimum), 16 GB recommended.
   - At least 10 GB of free disk storage for incident videos.
   - No dedicated GPU required (CPU-optimized YOLO11n inference).

---

## 2. Installation & Environment Setup

Open PowerShell in the `ShopGuard AI` project root:

```powershell
# 1. Create a Python virtual environment (if not already created)
python -m venv venv

# 2. Activate the virtual environment
.\venv\Scripts\Activate.ps1

# 3. Upgrade pip and install all dependencies (including FastAPI & Uvicorn)
pip install -r requirements.txt
```

---

## 3. Configuration

Edit `config/config.yaml` to customize the Local Security Agent settings:

```yaml
agent:
  host: "127.0.0.1"             # Local loopback only (never bind 0.0.0.0 without tunnel)
  port: 8000                    # REST API port
  require_auth_for_read: false  # When true, GET endpoints also require API key
  state_file: "data/security_state.json"
  arm_readiness_timeout_seconds: 15
```

The API runner and app factory reject non-loopback hosts. Do not expose this agent
directly to a LAN or the public internet; remote access requires a separately secured
relay architecture. For a physical Android phone, the Windows installer configures
private Tailscale Serve to proxy to `127.0.0.1:8000`; the Android emulator can use
`10.0.2.2:8000` directly.

### Authentication

Control requests accept either the API key or an allowlisted Tailscale identity
forwarded by Tailscale Serve. The one-time Windows installer asks which Tailscale
login(s) may ARM/DISARM and stores them in the ignored local file
`config/tailscale_allowed_users.txt`. Tailscale access control should also limit
access to the ShopGuard device to trusted users. The Android app can leave the API
key blank when connected through the installed private Tailscale Serve endpoint.

API-key authentication remains available for local tools and deployments not using
Tailscale Serve:

#### Option A: Set via `.env` file
Copy `.env.example` to `.env` and define:
```ini
SHOPGUARD_API_KEY=YourSuperSecretKey123!
```

#### Option B: Automatic Secret Key Generation
If no key is configured in `.env`, the agent will automatically generate a secure 32-byte cryptographic hex token upon first start and save it to:
```
config/agent_api_key.secret
```
Open that file to read your API key for client testing.

---

## 4. Running the Local Security Agent

### Method 1: Foreground Interactive Console

#### Option A: Running with Laptop Webcam (No CCTV or RTSP cameras needed)
```powershell
.\venv\Scripts\python.exe tools/run_agent.py --webcam
```
If using a secondary USB webcam:
```powershell
.\venv\Scripts\python.exe tools/run_agent.py --webcam 1
```

#### Option B: Running with Physical CCTV RTSP Cameras
```powershell
.\venv\Scripts\python.exe tools/run_agent.py
```

Or pass custom host and port parameters:
```powershell
.\venv\Scripts\python.exe tools/run_agent.py --host 127.0.0.1 --port 8000
```

Console output will display:
```
[INFO] [ShopGuard.agent.server]: Starting ShopGuard AI Local Security Agent on 127.0.0.1:8000...
[INFO] [ShopGuard.agent.server]: Initializing headless ShopGuardEngine for Local Security Agent...
[INFO] [ShopGuard.security.controller]: Initializing in DISARMED state (Safe default).
[INFO] [ShopGuard.agent.server]: API documentation available at http://127.0.0.1:8000/docs
```

Press `Ctrl+C` in the PowerShell terminal to initiate a graceful shutdown.

---

## 5. Running Automatically on Windows Startup

Install a per-user Windows Task Scheduler task from the project root. Before running
the installer, install Tailscale on Windows, sign in, enable MagicDNS and HTTPS
certificates for the tailnet, and ensure the Android device is signed in to the same
tailnet:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\install_windows_task.ps1
```

The installer verifies Tailscale connectivity and the existing Serve configuration,
asks which Tailscale login(s) may control ShopGuard, installs and starts the local
agent, waits for its health endpoint, then configures a private HTTPS Serve endpoint
to `http://127.0.0.1:8000`. It will not overwrite an existing Tailscale Serve
configuration. Use the displayed `https://<Windows-machine>.ts.net` address in the
Android Device Connection screen (HTTPS, port 443); the API key field can remain
blank. Add the shop's camera credentials in the Android camera-management screen.

The task runs `venv\Scripts\pythonw.exe` directly under Task Scheduler, without a
console attached to the installation PowerShell window. The installer stops any
older foreground copy first and verifies that the task's own process is running,
so its health check cannot pass against a manually launched agent. The task is
configured not to stop when Windows changes idle state. Application logs are written to
`data\logs\shopguard.log`; Task Scheduler retries up to five times at one-minute
intervals if the process exits.
The task runs while the configured Windows user is signed in; after a computer
restart, sign in to Windows and make a deliberate ARM request from Android.

### Startup and monitoring safety

The agent **always starts DISARMED**, regardless of its prior persisted state. A
computer restart never automatically resumes monitoring: the shopkeeper must make
a fresh, authenticated ARM request from the Android app. Once the Windows agent
has started, closing the Android app does not stop the API or an armed monitoring
session; reopening the app reads the current server state.
Camera capture and person-inference workers remain stopped while DISARMED and are
started automatically by an authenticated ARM request.

ARM waits for every enabled camera to provide fresh frames that have actually
passed through person inference, along with a loaded model and an enabled
restricted zone for every camera. If any requirement is unavailable after the
configured timeout, the API rejects ARM with a reason. During an armed session,
camera loss degrades the state and a recovered feed is processed again; no camera
or processing worker is duplicated by repeated start/ARM requests.

DISARM immediately gates intrusion evaluation off but leaves the API, capture
workers, and health checks running.

Check task and log status:

```powershell
Get-ScheduledTask -TaskName "ShopGuardAI_Engine" | Get-ScheduledTaskInfo
Get-Content .\data\logs\shopguard.log -Tail 100
```

To remove the scheduled task:
```powershell
powershell -ExecutionPolicy Bypass -File .\tools\uninstall_windows_task.ps1
```
Uninstalling stops/removes the task but leaves logs, configuration, and incident
records untouched. Tailscale Serve configuration is also left untouched because it
may contain other services. After checking `tailscale serve status`, remove the
ShopGuard Serve configuration only if it is still the sole Serve service:
```powershell
tailscale serve --https=443 off
```
To stop the agent without uninstalling it, stop the scheduled task in Task
Scheduler; it will start again at the next user logon.

---

## 6. Verifying the API & Testing Commands

### Interactive Swagger UI
Open your browser to:
```
http://127.0.0.1:8000/docs
```
Here you can explore every endpoint, inspect schemas, and execute requests interactively.

### Testing via PowerShell (`Invoke-RestMethod`)

#### Check Status:
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/status" -Method GET | ConvertTo-Json
```

#### Arm the System:
```powershell
$headers = @{ "X-API-Key" = "YourSuperSecretKey123!" }
$body = @{ reason = "Shop closing for night" } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/security/arm" -Method POST -Headers $headers -Body $body -ContentType "application/json"
```

#### Disarm the System:
```powershell
$headers = @{ "X-API-Key" = "YourSuperSecretKey123!" }
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/security/disarm" -Method POST -Headers $headers -ContentType "application/json"
```

#### Check System Health:
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -Method GET | ConvertTo-Json
```

---

## 7. Troubleshooting

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| **HTTP 401 Unauthorized** | Missing or incorrect API key. | Verify the key in `.env` or check `config/agent_api_key.secret`. Include `X-API-Key` or `Authorization: Bearer <key>`. |
| **HTTP 409 Conflict** | Duplicate state change. | Check `/api/status`. The system is already in the requested state (`ARMED` or `DISARMED`). |
| **HTTP 400 Cannot Arm** | Prerequisites not met. | Check `/api/security/state` to view `rejection_reasons` (e.g., any enabled camera has no fresh frame, inference is inactive, or a camera has no enabled zone). |
| **Camera Disconnected** | Network cable unplugged or RTSP stream down. | The agent automatically degrades to `PARTIAL` or `OFFLINE` and marks health as `DEGRADED`. A disconnected camera does not generate detections. During the same armed session, a recovered stream resumes when fresh frames are available. |
| **Port 8000 in use** | Another application is bound to 8000. | Change `port: 8080` in `config/config.yaml` or run `tools/run_agent.py --port 8080`. |
