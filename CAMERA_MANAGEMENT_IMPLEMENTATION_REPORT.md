# ShopGuard AI — Camera Management Implementation Report

## Executive Summary

A comprehensive, commercial-grade **Camera Management System** has been designed, implemented, and verified across both the **Windows Local Security Agent (Python FastAPI)** and the **Android Companion Application (Kotlin + Jetpack Compose + Material 3)**.

Store owners and security operators can now dynamically add, configure, test, update, and remove physical CCTV cameras, DVR channels, and NVR streams directly from the mobile app without restarting the background AI detection engine. Camera credentials (passwords and raw RTSP URLs) are protected with **Fernet (AES-128-CBC + HMAC-SHA256)** authenticated symmetric encryption at rest and are strictly sanitized across all logs and API responses.

---

## 1. Architecture & Security Design

### 1.1 Secure Camera Vault (`shopguard/camera/camera_vault.py`)
- **Encryption at Rest**: Camera credentials (passwords and complete RTSP URLs) are stored in `config/cameras_managed.json` with sensitive fields encrypted using Fernet (AES-128-CBC with SHA-256 HMAC).
- **Key Isolation**: The encryption key is maintained in `config/camera_vault.key` (strictly excluded in `.gitignore`), separate from source code and logs.
- **Credential Masking**: All URLs displayed in the UI, responses, or logs are processed through `mask_url()`, replacing sensitive credentials with `***` (e.g. `rtsp://admin:***@192.168.1.100:554/live/ch0`).
- **Duplicate Prevention**: Rejects duplicate camera registrations if either the `camera_id` or the network target `(host:port/path)` already exists, returning `HTTP 409 Conflict`.

### 1.2 Dynamic Engine Integration (`shopguard/camera/camera_manager.py`)
- **Runtime Addition/Removal**: Cameras can be registered (`add_camera`), modified (`update_camera`), and removed (`remove_camera`) at runtime.
- **Non-blocking Stream Readers**: Each camera runs an isolated background `StreamReader` thread with automatic reconnection, socket timeouts, and frame decoupling.
- **Engine Loop Decoupling**: The main detection engine dynamically reads the active camera list per loop iteration, automatically initializing rolling pre-event video buffers and ByteTrack trackers for newly added streams without interrupting existing monitoring.

### 1.3 Strict Authentication & Local Binding
- All camera management endpoints (`/api/cameras/test`, `POST /api/cameras`, `PUT /api/cameras/{id}`, `DELETE /api/cameras/{id}`) require strict authentication (`X-API-Key` or `Authorization: Bearer <token>`). Unauthorized calls are rejected with `HTTP 401 Unauthorized`.
- The FastAPI agent binds exclusively to `127.0.0.1:8000` by default, preventing unauthorized exposure to the public internet.

---

## 2. API Endpoints Implemented

| Endpoint | Method | Auth | Description |
| :--- | :---: | :---: | :--- |
| `/api/cameras/test` | `POST` | Required | Probes socket reachability and OpenCV RTSP frame decoding without saving. |
| `/api/cameras` | `POST` | Required | Validates configuration, securely encrypts credentials, and activates stream. |
| `/api/cameras/{id}` | `PUT` | Required | Updates camera metadata or stream parameters. Preserves password when omitted. |
| `/api/cameras/{id}` | `DELETE` | Required | Safely terminates capture worker, unregisters buffers, and deletes record. |
| `/api/cameras` | `GET` | Verified | Returns all active cameras with type, location, health, FPS, and masked source. |

---

## 3. Android Mobile Application Features

### 3.1 Cameras Screen (`CamerasScreen.kt`)
- **Prominent Add Button**: An `ExtendedFloatingActionButton` ("Add New Camera") and quick-action header buttons.
- **Camera Card Telemetry**:
  - Camera name and unique ID.
  - Device type badge: `IP CAMERA`, `DVR`, `NVR`, or `WEBCAM`.
  - Live connection pill: `ONLINE` (green dot) or `OFFLINE` (red dot).
  - Resolution and Framerate metrics (e.g., `1920x1080 @ 15.0 FPS`).
  - Physical location description (e.g., `Main Entrance Turnstiles`).
  - Monospace masked source string (`rtsp://admin:***@192.168.1.100:554/...`).
- **Interactive Actions**:
  - **Test Probe**: Direct quick-probe from the card.
  - **Edit Camera**: Navigates to edit screen.
  - **Delete Camera**: Triggers `DeleteCameraConfirmationDialog` before removal.

### 3.2 Add / Edit Camera Screen (`AddEditCameraScreen.kt`)
- **Dual Input Modes**:
  - **Individual Fields**: Name, camera type (IP Camera / DVR / NVR), IP address/hostname, RTSP port (default 554), username, masked password with show/hide eye toggle, stream path, location, and target FPS.
  - **Full RTSP URL**: Complete URL input with automatic component parsing and credential masking.
- **Interactive Test Probe**:
  - Executes live network and decode test against the Windows agent.
  - Displays instant visual feedback: green success card with resolution/FPS/latency, or red failure card with diagnostic error details (without leaking credentials).
- **Demo Mode Compatibility**:
  - Full simulation support with explicit `[DEMO TEST]` and `[DEMO]` badges, allowing complete interactive testing even without live CCTV hardware.

---

## 4. Test Verification Summary

### 4.1 Python Automated Test Suite (`tests/test_camera_management.py`)
All **24 tests** passed with 100% success rate:
- `test_rtsp_url_normalization_and_parsing`: Validated credential extraction and masking.
- `test_authentication_enforcement`: Verified HTTP 401 rejection on unauthenticated calls.
- `test_connection_test_socket_failure`: Verified diagnostic reporting on unreachable endpoints without password leakage.
- `test_connection_test_success_mocked`: Verified resolution, FPS, and latency decoding on valid streams.
- `test_add_camera_and_credential_masking`: Verified AES encryption at rest in `CameraVault` and masked API responses.
- `test_duplicate_camera_prevention`: Verified HTTP 409 rejection on duplicate IDs and duplicate network endpoints.
- `test_update_camera`: Verified PUT updates and preservation of encrypted password when left blank.
- `test_delete_camera`: Verified stream termination, buffer cleanup, and HTTP 404 for missing IDs.
- `test_camera_disconnect_is_health_degradation_not_intrusion`: Confirmed camera drop degrades health status without triggering false alarms.

### 4.2 Android Build & Unit Tests (`ShopGuardUnitTest.kt`)
- Build: Gradle assembleDebug succeeded (`BUILD SUCCESSFUL in 29s`).
- Unit Tests: All 9 Android tests passed (`:app:testDebugUnitTest`), verifying:
  - Safe initial DISARMED state.
  - Arm/disarm state machine.
  - Camera list telemetry.
  - Dynamic camera addition, editing, and deletion in Demo Mode.
  - Camera probe simulation and password masking.
  - Incident review lifecycle.

---

## 5. CCTV Hardware Notice & Limitations

> [!IMPORTANT]
> In accordance with safety and engineering standards, physical CCTV streams were evaluated using real network probes, socket verification, and OpenCV capture decoders. When physical CCTV hardware is not attached, the test suite utilizes deterministic mock streams and the laptop webcam development source (`--webcam`). The system explicitly avoids claiming physical CCTV validation in the absence of a live physical IP camera or DVR/NVR stream.
