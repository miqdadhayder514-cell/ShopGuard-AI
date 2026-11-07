# ShopGuard AI – Local Security Agent Webcam Integration Report

**Document Version:** 1.0.0  
**Status:** IMPLEMENTED & VERIFIED  
**Date:** 2026-11-05  
**Operating Environment:** Windows 10 / 11 (64-bit), Python 3.14  
**Full Test Suite Result:** 73/73 PASSED (100% Green, 0 Failures)

---

## 1. Executive Summary

This report documents the implementation of native **Laptop Webcam Testing Mode** within the **ShopGuard AI Phase 2 Local Security Agent**.

Previously, starting the agent without a physical CCTV camera or an active RTSP stream URL in `.env` resulted in:
`Video source for camera 'camera_01' is empty or undefined.`

With this integration, developers and shop owners can test the complete headless REST API service, security arm/disarm state machine, live YOLO person detection, ByteTrack tracking, restricted polygon zones, and incident clip generation directly on a Windows laptop using its built-in or USB webcam—**with zero RTSP cameras or `.env` configuration required**.

---

## 2. Requirements & Implementation Summary

| # | Requirement | Implementation Details | Status |
|---|---|---|:---:|
| 1 | Add `--webcam` command-line option to `tools/run_agent.py` | Added `--webcam [INDEX]` (defaults to index `0`) and explicit `--webcam-index [INT]`. | **DONE** |
| 2 | Initialize webcam capture using OpenCV device index 0 | Automatically probes hardware device using DirectShow/MSMF via `check_webcam_available()` before startup. | **DONE** |
| 3 | Reuse existing YOLO, ByteTrack, zone, controller, and recorder components | Reused `ShopGuardEngine` in headless mode (`show_gui=False`) without duplicating any detection or tracking logic. | **DONE** |
| 4 | Keep FastAPI endpoints operational during webcam capture | All 9 REST endpoints remain active, serving live data from the background webcam capture thread. | **DONE** |
| 5 | Ensure `/api/cameras` reports webcam status | Accurately returns `is_webcam: true`, `source_masked: "webcam:0"`, FPS, resolution, and connection status. | **DONE** |
| 6 | Ensure `/api/security/state` reports arm/disarm | Returns `state: "DISARMED"` on startup, validates 4 arming prerequisites (`can_arm: true`), and transitions to `ARMED` upon command. | **DONE** |
| 7 | Gated incident generation | Intrusions are strictly ignored while `DISARMED`. When `ARMED`, entering the zone triggers an incident clip and JSON metadata. | **DONE** |
| 8 | Display `WEBCAM TEST MODE — NOT CCTV` indicator | Prominently displayed in terminal banner, startup logs, `/api/status`, and `/api/health` response payloads. | **DONE** |
| 9 | Do not require RTSP URL or `CAMERA_01_URL` | `--webcam` isolates camera inputs to the webcam, bypassing `.env` stream lookups completely. | **DONE** |
| 10 | Preserve normal RTSP operation | Omitting `--webcam` maintains standard RTSP camera behavior from `config/config.yaml`. | **DONE** |
| 11 | Safe startup in DISARMED mode | The agent forces `DISARMED` state on initialization, requiring authorized arm command. | **DONE** |
| 12 | Automated test suite | Added `tests/test_agent_webcam.py` with 5 targeted integration tests. All 73 project tests pass. | **DONE** |

---

## 3. Architecture & Data Flow

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ tools/run_agent.py --webcam 0                                                          │
│                                                                                        │
│  ├── 1. Probes hardware webcam: check_webcam_available(0)                              │
│  ├── 2. Prints WEBCAM TEST MODE banner                                                 │
│  └── 3. Initializes FastAPI app via create_app(webcam_index=0)                         │
└────────────────────────────────────┬───────────────────────────────────────────────────┘
                                     │
                                     ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ FastAPI Local Security Agent (shopguard/agent/server.py)                                │
│                                                                                        │
│  ├── Endpoints:                                                                        │
│  │     GET  /api/status         ──► mode: "WEBCAM_TEST", notice: "WEBCAM TEST MODE"    │
│  │     GET  /api/cameras        ──► is_webcam: true, source_masked: "webcam:0"         │
│  │     GET  /api/security/state ──► can_arm: true, state: "DISARMED"                   │
│  │     POST /api/security/arm   ──► Authenticated arming (requires API Key / Bearer)   │
│  │     POST /api/security/disarm──► Authenticated disarming                            │
│  │     GET  /api/incidents      ──► Filtered incident list                             │
│  │     GET  /api/health         ──► Hardware & stream diagnostic metrics               │
│  │                                                                                     │
│  └── Headless ShopGuardEngine (webcam_override=0, show_gui=False)                      │
│        ├── Background StreamReader reading cv2.VideoCapture(0)                         │
│        ├── Headless YOLO11n + ByteTrack loop                                           │
│        ├── Restricted polygon zone containment filter                                  │
│        └── IncidentRecorder (saves .mp4 + .json with source_type: "webcam")            │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Commands for Running and Testing

### 4.1 Launch the Local Security Agent with Laptop Webcam
```powershell
.\venv\Scripts\python.exe tools/run_agent.py --webcam
```
If using a secondary USB webcam (device index 1):
```powershell
.\venv\Scripts\python.exe tools/run_agent.py --webcam 1
```

### 4.2 Terminal Output Sample
```
============================================================================
      SHOPGUARD AI — PHASE 2: LOCAL SECURITY AGENT (WINDOWS)
============================================================================
  ******************************************************************
  ***                 WEBCAM TEST MODE — NOT CCTV                ***
  ***  Active Webcam Device Index : 0                             ***
  ***  Webcam Sensor Resolution   : 1280x720                      ***
  ***  RTSP / Physical CCTV       : NOT REQUIRED (Simulation Mode)***
  ******************************************************************
  * Local REST API for CCTV monitoring, health checks, and security arm/disarm
  * Binding Address     : http://127.0.0.1:8000
  * Interactive Docs    : http://127.0.0.1:8000/docs
  * Configuration File  : config/config.yaml
  * Authentication      : Header 'X-API-Key' or 'Authorization: Bearer <key>'
  * Active Secret Key   : [STORED IN config\agent_api_key.secret]
  * Execution Mode      : HEADLESS (Zero OpenCV display windows)
  * Safe Startup State  : DISARMED
============================================================================
```

### 4.3 Verifying via REST API (PowerShell Examples)

#### 1. Query Status (Confirms Webcam Mode Notice)
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/status" -Method GET | ConvertTo-Json
```
**Response:**
```json
{
  "service_status": "RUNNING",
  "security_state": "DISARMED",
  "is_armed": false,
  "cameras_total": 1,
  "cameras_connected": 1,
  "active_incidents_today": 0,
  "uptime_seconds": 15.4,
  "mode": "WEBCAM_TEST",
  "notice": "WEBCAM TEST MODE — NOT CCTV"
}
```

#### 2. Query Camera Telemetry
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/cameras" -Method GET | ConvertTo-Json
```
**Response:**
```json
{
  "total": 1,
  "connected": 1,
  "cameras": [
    {
      "id": "camera_01",
      "name": "Laptop Webcam 0",
      "source_masked": "webcam:0",
      "is_connected": true,
      "status": "CONNECTED",
      "fps": 15.0,
      "resolution": [1280, 720],
      "consecutive_failures": 0,
      "is_webcam": true
    }
  ]
}
```

#### 3. Arm the System
```powershell
$headers = @{ "X-API-Key" = (Get-Content "config\agent_api_key.secret") }
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/security/arm" -Method POST -Headers $headers -Body '{"reason":"Webcam intrusion testing"}' -ContentType "application/json"
```

#### 4. Disarm the System
```powershell
$headers = @{ "X-API-Key" = (Get-Content "config\agent_api_key.secret") }
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/security/disarm" -Method POST -Headers $headers -ContentType "application/json"
```

---

## 5. Automated Test Suite Results

A dedicated automated test module was created in [`tests/test_agent_webcam.py`](file:///c:/Users/Miqdad%20Haider/Desktop/ShopGuard%20AI/tests/test_agent_webcam.py):

| Test Case | Scope | Result |
| :--- | :--- | :---: |
| `test_webcam_mode_status_endpoint_reports_indicator` | Verifies `/api/status` returns `mode: "WEBCAM_TEST"` and `notice: "WEBCAM TEST MODE — NOT CCTV"`. | **PASSED** |
| `test_webcam_mode_cameras_endpoint_identifies_webcam` | Verifies `/api/cameras` identifies `is_webcam: true` and `source_masked: "webcam:0"`. | **PASSED** |
| `test_webcam_mode_security_state_and_arming_lifecycle` | Validates arm readiness, authorized arming, and disarming lifecycle in webcam mode. | **PASSED** |
| `test_webcam_mode_incident_gated_by_arm_state` | Verifies intrusions are ignored when DISARMED and trigger incidents tagged with `source_type: "webcam"` and `simulation_mode: true` when ARMED. | **PASSED** |
| `test_webcam_mode_health_endpoint_reports_notice` | Verifies `/api/health` includes webcam diagnostic health and mode notice. | **PASSED** |

### Complete Project Regression Suite
```powershell
.\venv\Scripts\pytest -q
73 passed, 1 warning in 49.41s
```
- **Total Tests:** 73 passed (0 failed, 0 skipped, 100% green).
- **Zero regressions** across Phase 1 AI detection, ByteTrack tracking, multi-camera RTSP, webcam GUI mode, recorded video testing, and Phase 2 Local Security Agent REST API.

---

## 6. Known Limitations & Safety Considerations

1. **Simulation vs Production CCTV**:
   - Webcam testing validates the software logic, API orchestration, and AI inference pipeline.
   - It **does not prove RTSP stream stability, network switch bandwidth, or NVR latency**. Prior to live shop deployment, verify physical cameras with `tools/rtsp_diagnostic.py`.
2. **Camera Hardware Exclusivity**:
   - On Windows, webcams can typically only be opened by one process at a time. Close applications like Zoom, Microsoft Teams, Skype, or browser video calls before launching webcam mode.
3. **Field of View & Angles**:
   - Laptop webcams are typically placed at chest or eye level with wide-angle lenses, whereas CCTV cameras are mounted near ceilings angled downwards. Polygon zones should be calibrated accordingly.
