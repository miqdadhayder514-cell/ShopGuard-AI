# ShopGuard AI – Phase 2: Local Security Agent Implementation Report

**Document Version:** 1.0.0  
**Status:** IMPLEMENTED & TESTED  
**Date:** 2026-11-05  
**Operating Environment:** Windows 10 / 11, Python 3.14 (x64)  
**Test Suite Status:** 68/68 PASSED (100% Green, 0 Regressions)

---

## 1. Executive Summary

Phase 2 transitions **ShopGuard AI** from a local OpenCV-based desktop application into a robust, headless **Local Security Agent** running as a Windows background service. It embeds an asynchronous Python **FastAPI** REST API layer that interfaces directly with the Phase 1 AI vision engine, camera manager, security controller, and incident storage.

### Key Achievements
1. **Full REST API Suite**: 9 structured JSON endpoints delivering live system status, camera telemetry, security state, incident history, health diagnostics, and host resources.
2. **Strict Security & Authentication**:
   - Bound to `127.0.0.1` (localhost loopback) by default; public internet exposure is prohibited.
   - All state-altering control actions (`POST /api/security/arm`, `POST /api/security/disarm`) require cryptographic authentication via `X-API-Key` or `Authorization: Bearer <token>`.
   - Constant-time secret comparison (`hmac.compare_digest`) protects against timing attacks.
   - Credentials inside RTSP URLs (e.g. `rtsp://admin:pass@host/`) are strictly masked across all API responses.
3. **Guaranteed Safe Startup & Crash Recovery**:
   - The security engine **always initializes in `DISARMED` mode** upon startup or reboot to eliminate false alarms following power disruptions.
   - Persistent disk-backed state store (`data/security_state.json`) tracks state transitions and audits whether prior process terminations were clean shutdowns or unexpected crashes.
   - Duplicate arm or disarm commands are validated and rejected with HTTP `409 Conflict`.
4. **Camera Failure Decoupling**:
   - Camera drops and network timeouts immediately trigger security state degradation (`ARMED` -> `PARTIAL` or `OFFLINE`) and report `DEGRADED`/`CRITICAL` health.
   - Camera loss is **never misclassified as an intrusion event**.
5. **Headless Execution**:
   - Full AI processing, tracking, and incident recording run in the background without requiring an OpenCV display window (`show_gui: false`).

---

## 2. System Architecture

```
                               ┌───────────────────────────────────────────────┐
                               │           Client / Mobile App                 │
                               │    (Future Android App via Secure Tunnel)     │
                               └──────────────────────┬────────────────────────┘
                                                      │ HTTP / JSON
                                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Windows Host (127.0.0.1:8000)                                                                   │
│                                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │ FastAPI Local Security Agent (shopguard/agent/server.py)                                   │  │
│  │                                                                                           │  │
│  │  ├── Auth Guard: Token Validator (HMAC-SHA256, constant-time compare)                     │  │
│  │  ├── Endpoints: /api/status, /api/cameras, /api/security/*, /api/incidents/*, /api/health   │  │
│  │  └── State Store: data/security_state.json (Persistent audit & crash tracking)            │  │
│  └──────────────────────────────────────────┬────────────────────────────────────────────────┘  │
│                                             │ In-Process Lifespan                                │
│                                             ▼                                                   │
│  ┌───────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │ ShopGuard AI Headless Core Engine                                                          │  │
│  │                                                                                           │  │
│  │  ├── SecurityController: State Machine (DISARMED ◄► ARMED / PARTIAL / OFFLINE)            │  │
│  │  ├── CameraManager: Multi-Stream RTSP & Laptop Webcam readers                             │  │
│  │  ├── YOLO11n + ByteTrack: People detection & multi-resolution inference                   │  │
│  │  ├── IntrusionEngine: Polygon zone containment & foot-contact coordinate gate             │  │
│  │  ├── IncidentRecorder: Pre/Post buffer rolling writer (.mp4 + .json metadata)             │  │
│  │  └── HealthMonitor: Diagnostics, camera liveness, and disk storage metrics                │  │
│  └───────────────────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Implemented API Endpoints

| Endpoint | Method | Auth Required | Purpose | Response Code |
| :--- | :---: | :---: | :--- | :---: |
| `/api/status` | `GET` | Optional* | Overall agent service status, security state, camera counts, incident counters. | `200 OK` |
| `/api/cameras` | `GET` | Optional* | Registered camera list, connection statuses, FPS, resolutions, masked sources. | `200 OK` |
| `/api/security/state` | `GET` | Optional* | Current security state, arm readiness check, active zone count, rejection reasons. | `200 OK` |
| `/api/security/arm` | `POST` | **Mandatory** | Arm the security system with audit reason logging. | `200 OK` / `400` / `409` |
| `/api/security/disarm` | `POST` | **Mandatory** | Disarm the security system with audit reason logging. | `200 OK` / `409` |
| `/api/incidents` | `GET` | Optional* | Paginated, filtered list of recorded intrusion incidents. | `200 OK` |
| `/api/incidents/{incident_id}` | `GET` | Optional* | Full metadata JSON for a single recorded incident. Traversal protected. | `200 OK` / `400` / `404` |
| `/api/health` | `GET` | Optional* | System health, camera drop status, AI model status, free disk space. | `200 OK` |
| `/api/system/info` | `GET` | Optional* | Host hardware diagnostic: OS version, Python version, memory, CPU cores. | `200 OK` |

*\* Note: Read endpoints can be configured to require authentication by setting `agent.require_auth_for_read: true` in `config/config.yaml`.*

---

## 4. Security & Safety Implementation Details

### 4.1 Localhost Binding and Network Isolation
The agent binds to `127.0.0.1` by default. Under no circumstances should the raw HTTP port be forwarded to the public internet. Remote mobile integration (Phase 3) will require an encrypted tunnel (e.g., WireGuard, Cloudflare Tunnel, or mutual TLS proxy).

### 4.2 Credential Protection & RTSP URL Masking
In accordance with zero-trust logging practices:
- RTSP URLs containing embedded credentials (e.g. `rtsp://admin:P@ssw0rd!@192.168.1.50/live`) are filtered using regex masking: `rtsp://admin:***@192.168.1.50/live`.
- Unmasked URLs never appear in API responses, logs, or error exceptions.

### 4.3 Control Action Authentication
- **Headers Supported**:
  - `X-API-Key: <token>`
  - `Authorization: Bearer <token>`
- **Token Resolution Priority**:
  1. Environment variable `SHOPGUARD_API_KEY`.
  2. Local secret file `config/agent_api_key.secret` (auto-generated 32-byte cryptographically secure token on first run if unset).
- **Constant-Time Verification**: Uses Python's `hmac.compare_digest` to prevent side-channel timing attacks.

### 4.4 Safe Startup Guarantee & State Persistence
- When the Local Security Agent starts up, it **always forces `DISARMED` mode**.
- The persistent store (`data/security_state.json`) logs every transition with timestamps, originating caller reasons, and audit trails.
- On shutdown, a `clean_shutdown: true` marker is written to disk. On reboot, if `clean_shutdown` is `false` and the prior recorded state was `ARMED`, the agent logs an audit warning:
  > *"Prior session terminated abnormally while system was ARMED. Safe recovery enforced: system initialized in DISARMED mode."*

### 4.5 Camera Disconnection Handling
If a camera connection drops:
- The `CameraManager` worker thread attempts exponential backoff reconnection.
- `SecurityController` transitions system state from `ARMED` to `PARTIAL` (if other cameras are alive) or `OFFLINE` (if all cameras are dead).
- `HealthMonitor` flags `overall_health` as `DEGRADED` or `CRITICAL`.
- **Zero intrusion alerts are emitted**. The event recorder remains idle.

---

## 5. Verification & Test Suite Summary

A dedicated automated test suite (`tests/test_agent_api.py`) was developed to validate all Phase 2 functionality. All 10 tests passed without errors:

| Test Case | Scope Covered | Result |
| :--- | :--- | :---: |
| `test_status_endpoint_initial_state` | Verifies `/api/status` returns `RUNNING` service and safe `DISARMED` state. | **PASSED** |
| `test_cameras_endpoint_masks_credentials` | Verifies `/api/cameras` completely hides RTSP passwords. | **PASSED** |
| `test_security_state_endpoint` | Validates `/api/security/state`, prerequisite checks, and zone counts. | **PASSED** |
| `test_control_endpoints_require_authentication` | Validates rejection (HTTP 401) for missing or invalid tokens on `/arm` and `/disarm`. | **PASSED** |
| `test_arm_and_disarm_lifecycle_with_x_api_key` | Validates full arm/disarm lifecycle with `X-API-Key` and duplicate arm rejection (409). | **PASSED** |
| `test_arm_with_bearer_authorization_header` | Validates `Authorization: Bearer <token>` authentication format. | **PASSED** |
| `test_camera_disconnection_updates_health_without_intrusion` | Verifies camera drop transitions to `PARTIAL`/`OFFLINE` and causes zero intrusion alerts. | **PASSED** |
| `test_incidents_list_and_detail_endpoints` | Validates incident pagination, filtering, metadata retrieval, and path traversal protection. | **PASSED** |
| `test_system_info_endpoint` | Validates host hardware diagnostics (CPU, RAM, OS version). | **PASSED** |
| `test_persistent_state_store_and_crash_recovery` | Validates disk state persistence, clean shutdown, and crash recovery auditing. | **PASSED** |

### Complete Project Regression Suite
- Total automated tests: **68 passed** (0 failed, 0 skipped).
- Covers Phase 1 AI vision, ByteTrack, webcam mode, recorded video player, multi-camera RTSP, night detection, and Phase 2 Local Security Agent.

---

## 6. Pre-Deployment Limitations & Next Steps

1. **Local Access Boundary**: The local API is restricted to `127.0.0.1`. Do not expose port 8000 to external networks or router port forwarding.
2. **Android App Preparation**: Android application development should proceed based on the OpenAPI contracts defined in `API_DOCUMENTATION.md`. Remote mobile connectivity must utilize an authenticated reverse tunnel.
3. **Storage Maintenance**: Incident videos are stored locally under `data/incidents/`. Ensure adequate disk capacity or configure a retention pruning policy.
