# ShopGuard AI – Local Security Agent REST API Specification

**API Version:** 2.0.0  
**Target:** Local Security Agent (Windows) & Android Client  
**Default Base URL:** `http://127.0.0.1:8000`  
**Content-Type:** `application/json`

---

## 1. Authentication & Security Policy

The agent binds only to a loopback address. Non-loopback hosts are rejected by the
runner and app factory; do not expose the API directly to a LAN or the public internet.
The Windows agent runs independently of the Android app and always starts DISARMED.
Camera capture and person-inference workers start only after an authenticated ARM
request and stop on DISARM; the API itself stays available.

All administrative or state-altering requests (`POST /api/security/arm`, `POST /api/security/disarm`) require authentication. They accept a valid API key or an allowlisted `Tailscale-User-Login` identity added by Tailscale Serve. The allowlist is configured on the Windows host in `config/tailscale_allowed_users.txt`; do not expose the loopback API directly. Read endpoints can optionally enforce the same authentication depending on `agent.require_auth_for_read`.

When requests arrive through Tailscale Serve, it adds a verified `Tailscale-User-Login` header. The agent accepts it only when that exact login is listed in `config/tailscale_allowed_users.txt` (case-insensitive). The one-time Windows installer configures the allowlist. Tailscale ACLs should independently restrict who can reach the ShopGuard machine. The Android client can omit its API key when it connects through this private Serve endpoint.

### Supported Authentication Headers

You can provide the API key using either of the following standard headers:

1. **Custom API Key Header:**
   ```http
   X-API-Key: your_secure_token_here
   ```
2. **Standard Authorization Bearer Header:**
   ```http
   Authorization: Bearer your_secure_token_here
   ```

### Obtaining the API Key
- Set the key via environment variable: `SHOPGUARD_API_KEY=my_secure_api_key_123`
- Or read the auto-generated 32-byte secret generated on the Windows host at `config/agent_api_key.secret`.

### API-key fallback
The Android client can leave the key blank when connecting through the private
Tailscale Serve endpoint configured by the Windows installer. Local tools and
other deployments can continue to use API-key authentication.

---

## 2. Standard Error Response Schema

All error responses return a structured JSON body with an appropriate HTTP status code:

```json
{
  "detail": {
    "error": "ERROR_CODE_STRING",
    "message": "Human readable description of the error."
  }
}
```

| HTTP Status | Error Code | Description |
| :---: | :--- | :--- |
| `400 Bad Request` | `VALIDATION_ERROR` / `CANNOT_ARM` | Prerequisites not met (e.g., no cameras or no active zones). |
| `401 Unauthorized` | `UNAUTHORIZED` | Missing or invalid API key / Bearer token. |
| `404 Not Found` | `NOT_FOUND` | The requested incident ID does not exist. |
| `409 Conflict` | `ALREADY_ARMED` / `ALREADY_DISARMED` | Duplicate operation (system already in desired state). |
| `500 Server Error` | `SERVER_ERROR` | Internal server or storage exception. |

---

## 3. API Endpoints

### 3.1 Get System & Security Status
Retrieves a high-level summary of the agent service, current arm state, camera counts, and today's incident count.

- **Method:** `GET`
- **Path:** `/api/status`
- **Authentication:** Optional (unless read auth is enabled)

#### Response `200 OK`
```json
{
  "service_status": "RUNNING",
  "security_state": "DISARMED",
  "is_armed": false,
  "timestamp": 1793887000.12,
  "timestamp_iso": "2026-11-05T21:40:00.120000+00:00",
  "cameras_total": 2,
  "cameras_connected": 2,
  "active_incidents_today": 0,
  "uptime_seconds": 1245.8
}
```

---

### 3.2 List Cameras & Health Telemetry
Retrieves the list of configured CCTV and webcam streams. All RTSP credentials are automatically masked for privacy.

- **Method:** `GET`
- **Path:** `/api/cameras`
- **Authentication:** Optional (unless read auth is enabled)

#### Response `200 OK`
```json
{
  "total": 2,
  "connected": 2,
  "cameras": [
    {
      "id": "cam_01",
      "name": "Front Entrance",
      "source_masked": "rtsp://admin:***@192.168.1.100:554/live",
      "is_connected": true,
      "status": "CONNECTED",
      "fps": 15.0,
      "resolution": [1280, 720],
      "consecutive_failures": 0,
      "last_frame_timestamp": 1793887015.4,
      "is_webcam": false
    },
    {
      "id": "cam_webcam",
      "name": "Laptop Built-in Webcam",
      "source_masked": "webcam:0",
      "is_connected": true,
      "status": "CONNECTED",
      "fps": 30.0,
      "resolution": [1280, 720],
      "consecutive_failures": 0,
      "last_frame_timestamp": 1793887015.6,
      "is_webcam": true
    }
  ]
}
```

---

### 3.3 Get Detailed Security State & Arm Readiness
Checks camera readiness, person-model availability, restricted-zone configuration,
and active frame-processing status. An enabled camera is ready only when its worker
is alive and producing fresh frames.

- **Method:** `GET`
- **Path:** `/api/security/state`
- **Authentication:** Optional (unless read auth is enabled)

#### Response `200 OK`
```json
{
  "state": "DISARMED",
  "is_armed": false,
  "can_arm": true,
  "active_zones_count": 2,
  "connected_cameras": 2,
  "total_cameras": 2,
  "last_state_change": "2026-11-05T21:30:00+00:00",
  "rejection_reasons": []
}
```

---

### 3.4 Arm Security System
Starts the camera-processing pipeline and enables intrusion evaluation across all
configured restricted zones. ARM waits up to
`agent.arm_readiness_timeout_seconds` (default 15 seconds) for every enabled camera
to provide fresh frames that have passed through person inference. Every enabled
camera must also have an enabled restricted zone. If any camera or the processing
pipeline is unavailable, the request is rejected and the response includes
`rejection_reasons`; a partial camera set is never reported as fully `ARMED`.

- **Method:** `POST`
- **Path:** `/api/security/arm`
- **Authentication:** **Mandatory** (`X-API-Key` or `Authorization: Bearer <token>`)
- **Request Body (Optional):**
  ```json
  {
    "reason": "Shop closed for the night - Manager activation"
  }
  ```

#### Response `200 OK`
```json
{
  "success": true,
  "state": "ARMED",
  "message": "Security system successfully ARMED.",
  "timestamp": 1793887100.5,
  "timestamp_iso": "2026-11-05T21:45:00.500000+00:00",
  "reason": "Shop closed for the night - Manager activation"
}
```

#### Rejection Examples
- **Prerequisites Failed (`400 Bad Request`):**
  ```json
  {
    "detail": {
      "error": "ARMING_REJECTED",
      "message": "Arming rejected: All enabled cameras must be connected and producing fresh frames before arming."
    }
  }
  ```
- **Duplicate Operation (`409 Conflict`):**
  ```json
  {
    "detail": {
      "error": "ALREADY_ARMED",
      "message": "Security system is already in ARMED state."
    }
  }
  ```

---

### 3.5 Disarm Security System
Immediately disables intrusion evaluation while keeping the API server, camera
capture workers, and health checks running. The Windows agent remains available
when the Android client closes; only an explicit DISARM command changes its state.

- **Method:** `POST`
- **Path:** `/api/security/disarm`
- **Authentication:** **Mandatory** (`X-API-Key` or `Authorization: Bearer <token>`)
- **Request Body (Optional):**
  ```json
  {
    "reason": "Morning opening"
  }
  ```

#### Response `200 OK`
```json
{
  "success": true,
  "state": "DISARMED",
  "message": "Security system successfully DISARMED.",
  "timestamp": 1793887200.0,
  "timestamp_iso": "2026-11-05T21:46:40.000000+00:00",
  "reason": "Morning opening"
}
```

#### Rejection Example
- **Duplicate Operation (`409 Conflict`):**
  ```json
  {
    "detail": {
      "error": "ALREADY_DISARMED",
      "message": "Security system is already in DISARMED state."
    }
  }
  ```

---

### 3.6 List Recorded Incidents
Retrieves stored intrusion incidents with pagination and camera filtering.

- **Method:** `GET`
- **Path:** `/api/incidents`
- **Query Parameters:**
  - `limit` (integer, default: 20, max: 100): Number of records per page.
  - `offset` (integer, default: 0): Pagination offset.
  - `camera_id` (string, optional): Filter by camera identifier.
  - `event_type` (string, optional): Filter by event type string.

#### Response `200 OK`
```json
{
  "total": 1,
  "limit": 20,
  "offset": 0,
  "incidents": [
    {
      "incident_id": "incident_20261105_214532_cam_01",
      "camera_id": "cam_01",
      "camera_name": "Front Entrance",
      "event_type": "PERSON_ENTERED_RESTRICTED_ZONE",
      "event_timestamp": "2026-11-05T21:45:32Z",
      "confidence": 0.89,
      "zone_id": "zone_entrance",
      "zone_name": "Main Entrance Protected Area",
      "video_filename": "incident_20261105_214532_cam_01.mp4",
      "duration_seconds": 15.0,
      "total_frames": 225,
      "review_status": "UNREVIEWED"
    }
  ]
}
```

---

### 3.7 Get Incident Details
Retrieves the complete audit metadata for a specific incident. Protected against path-traversal attacks.

- **Method:** `GET`
- **Path:** `/api/incidents/{incident_id}`

#### Response `200 OK`
```json
{
  "incident_id": "incident_20261105_214532_cam_01",
  "camera_id": "cam_01",
  "camera_name": "Front Entrance",
  "event_type": "PERSON_ENTERED_RESTRICTED_ZONE",
  "event_timestamp": "2026-11-05T21:45:32Z",
  "confidence": 0.89,
  "zone_id": "zone_entrance",
  "zone_name": "Main Entrance Protected Area",
  "video_filename": "incident_20261105_214532_cam_01.mp4",
  "video_path": "data/incidents/incident_20261105_214532_cam_01.mp4",
  "video_file_exists": true,
  "duration_seconds": 15.0,
  "total_frames": 225,
  "review_status": "UNREVIEWED",
  "raw_metadata": {
    "track_id": 4,
    "contact_point": [0.42, 0.65],
    "dwell_time_seconds": 2.4,
    "model_name": "yolo11n.pt"
  }
}
```

---

### 3.8 Comprehensive System Health Diagnostic
Detailed hardware, storage, and stream diagnostic report.

- **Method:** `GET`
- **Path:** `/api/health`

#### Response `200 OK`
```json
{
  "healthy": true,
  "overall_health": "HEALTHY",
  "security_state": "DISARMED",
  "ai_model_loaded": true,
  "ai_model_path": "models/yolo11n.pt",
  "ai_device": "cpu",
  "disk_free_gb": 128.45,
  "disk_total_gb": 476.12,
  "cameras": [
    {
      "camera_id": "cam_01",
      "camera_name": "Front Entrance",
      "is_connected": true,
      "status": "CONNECTED",
      "last_frame_age_seconds": 0.1,
      "total_frames_read": 14200,
      "stream_source_masked": "rtsp://admin:***@192.168.1.100:554/live"
    }
  ],
  "timestamp": 1793887300.0
}
```

---

### 3.9 Host System Hardware Diagnostics
Reports host operating system and resource capacity.

- **Method:** `GET`
- **Path:** `/api/system/info`

#### Response `200 OK`
```json
{
  "app_name": "ShopGuard AI - Local Security Agent",
  "version": "2.0.0",
  "os": "Windows",
  "os_release": "10.0.26100",
  "python_version": "3.14.0",
  "cpu_count": 8,
  "memory_total_gb": 15.82,
  "memory_available_gb": 7.45,
  "agent_uptime_seconds": 3612.4,
  "storage_directory": "data/incidents",
  "incidents_recorded_total": 4
}
```

---

## 4. Guidance for Future Android Mobile Integration

1. **Local Network / Tunnel Access**:
   - The Local Security Agent binds to `127.0.0.1` on the shop PC.
   - For remote Android access outside the shop LAN, do **not** open port 8000 on the shop router. Instead, use an encrypted point-to-point mesh (e.g. **Tailscale**, **WireGuard**, or **Cloudflare Zero Trust Tunnel**).
2. **Polling vs WebSockets**:
   - For Phase 2, mobile apps can poll `GET /api/status` every 3–5 seconds when the app is foregrounded.
   - Background push notifications will be introduced via Firebase Cloud Messaging (FCM) in Phase 3.
3. **Incident Clip Playback**:
   - Incident MP4 clips are recorded in H.264 format, which is natively playable by Android's **Media3 / ExoPlayer**.
