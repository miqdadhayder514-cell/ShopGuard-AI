# ShopGuard AI — Camera Management REST API Specification

This document details the REST API endpoints provided by the ShopGuard AI Windows Local Security Agent for managing physical CCTV cameras, DVR channels, and NVR streams.

The agent remains DISARMED after startup. Camera configuration and connection
probes remain available while disarmed, but registered camera streams start only
when an authenticated ARM request activates monitoring. Adding an enabled camera
to an already-armed system starts that camera immediately.
If a camera has no zone configuration, the agent assigns an enabled full-frame
restricted zone so Android camera onboarding can proceed without a separate zone
editor. This includes the entire visible image and may detect people outside the
shop; cameras with existing zones keep those zones unchanged.

---

## Base Configuration

- **Default Agent URL**: `http://127.0.0.1:8000`
- **Android Emulator Loopback**: `http://10.0.2.2:8000`
- **Authentication**: Strict authentication is enforced on all camera management endpoints. Use an API key or an allowlisted Tailscale Serve identity. The Windows installer creates the Tailscale allowlist; Tailscale ACLs should also restrict access.
  - Header: `X-API-Key: <YOUR_SECRET_KEY>`
  - Header: `Authorization: Bearer <YOUR_SECRET_KEY>`
- **Content-Type**: `application/json`

---

## 1. Test Camera Connection

Probes network socket reachability and OpenCV RTSP frame decoding without persisting the camera into the system.

- **Method**: `POST`
- **Path**: `/api/cameras/test`
- **Authentication**: Required (`X-API-Key` or Bearer)

### Request Payload (`CameraTestRequest`)

You can provide either discrete fields or a complete RTSP URL:

```json
{
  "name": "Front Entrance Test",
  "camera_type": "IP Camera",
  "ip_address": "192.168.1.150",
  "port": 554,
  "username": "admin",
  "password": "CameraPassword123",
  "stream_path": "/live/ch0",
  "timeout_seconds": 4.0
}
```

Or using a complete URL:

```json
{
  "name": "Front Entrance Test",
  "camera_type": "IP Camera",
  "rtsp_url": "rtsp://admin:CameraPassword123@192.168.1.150:554/live/ch0",
  "timeout_seconds": 4.0
}
```

### Successful Response (`HTTP 200 OK`)

```json
{
  "success": true,
  "message": "Camera connection verified successfully (1920x1080 @ 15.0 FPS, 35ms latency).",
  "resolution": [1920, 1080],
  "fps": 15.0,
  "latency_ms": 35.2,
  "source_masked": "rtsp://admin:***@192.168.1.150:554/live/ch0",
  "details": null
}
```

### Failed Response (`HTTP 200 OK`)

```json
{
  "success": false,
  "message": "Connection timed out reaching 192.168.1.150:554. Verify camera power, IP address, and network routing.",
  "resolution": null,
  "fps": null,
  "latency_ms": 2501.4,
  "source_masked": "rtsp://admin:***@192.168.1.150:554/live/ch0",
  "details": "Socket connect timeout (device unreachable on LAN)."
}
```

---

## 2. Register New Camera

Registers a new camera and encrypts credentials in the Camera Vault
(`config/cameras_managed.json`). If the system is ARMED, its stream starts
dynamically; otherwise, the camera is prepared and starts on the next ARM request.

- **Method**: `POST`
- **Path**: `/api/cameras`
- **Authentication**: Required (`X-API-Key` or Bearer)

### Request Payload (`CameraCreateRequest`)

```json
{
  "id": "cam_entrance_01",
  "name": "Main Entrance Turnstiles",
  "camera_type": "IP Camera",
  "ip_address": "192.168.1.150",
  "port": 554,
  "username": "admin",
  "password": "CameraPassword123",
  "stream_path": "/live/ch0",
  "location": "North Lobby Entrance",
  "fps": 15.0,
  "enabled": true
}
```

### Successful Response (`HTTP 201 Created`)

```json
{
  "success": true,
  "camera_id": "cam_entrance_01",
  "message": "Camera 'Main Entrance Turnstiles' (cam_entrance_01) successfully registered and activated.",
  "camera": {
    "id": "cam_entrance_01",
    "name": "Main Entrance Turnstiles",
    "source_masked": "rtsp://admin:***@192.168.1.150:554/live/ch0",
    "is_connected": true,
    "status": "CONNECTING",
    "fps": 15.0,
    "resolution": null,
    "consecutive_failures": 0,
    "last_frame_timestamp": 0.0,
    "is_webcam": false,
    "camera_type": "IP Camera",
    "location": "North Lobby Entrance",
    "ip_address": "192.168.1.150",
    "port": 554,
    "stream_path": "/live/ch0",
    "last_status_update": "2026-11-06T12:00:00Z"
  }
}
```

### Error Responses

- **`HTTP 400 Bad Request`**: Missing IP address or malformed URL.
- **`HTTP 409 Conflict`**: Duplicate camera ID or identical network endpoint `(host:port/path)` already configured.

---

## 3. Update Existing Camera

Modifies an existing camera's configuration or metadata. If the password field is omitted or empty, the existing encrypted password in the vault is safely retained.

- **Method**: `PUT`
- **Path**: `/api/cameras/{camera_id}`
- **Authentication**: Required (`X-API-Key` or Bearer)

### Request Payload (`CameraUpdateRequest`)

```json
{
  "name": "Main Entrance - Extended Angle",
  "location": "North Lobby Entrance & Revolving Doors",
  "fps": 10.0
}
```

### Successful Response (`HTTP 200 OK`)

```json
{
  "success": true,
  "camera_id": "cam_entrance_01",
  "message": "Camera 'Main Entrance - Extended Angle' (cam_entrance_01) configuration updated.",
  "camera": {
    "id": "cam_entrance_01",
    "name": "Main Entrance - Extended Angle",
    "source_masked": "rtsp://admin:***@192.168.1.150:554/live/ch0",
    "is_connected": true,
    "status": "CONNECTED",
    "fps": 10.0,
    "camera_type": "IP Camera",
    "location": "North Lobby Entrance & Revolving Doors",
    "ip_address": "192.168.1.150",
    "port": 554,
    "stream_path": "/live/ch0",
    "last_status_update": "2026-11-06T12:05:00Z"
  }
}
```

### Error Responses

- **`HTTP 404 Not Found`**: Camera ID does not exist.
- **`HTTP 409 Conflict`**: New host/port/path conflicts with another camera.

---

## 4. Delete Camera

Gracefully terminates stream ingestion for the specified channel, clears rolling circular buffers, and removes the configuration from the encrypted vault.

- **Method**: `DELETE`
- **Path**: `/api/cameras/{camera_id}`
- **Authentication**: Required (`X-API-Key` or Bearer)

### Successful Response (`HTTP 200 OK`)

```json
{
  "success": true,
  "camera_id": "cam_entrance_01",
  "message": "Camera 'cam_entrance_01' was successfully unmounted and removed.",
  "camera": null
}
```

---

## 5. List All Cameras

Retrieves telemetry, connection health, and metadata for all configured cameras. Passwords are never returned in responses.

- **Method**: `GET`
- **Path**: `/api/cameras`
- **Authentication**: Optional for read or required (configured via `require_auth_for_read`)

### Successful Response (`HTTP 200 OK`)

```json
{
  "total": 2,
  "connected": 2,
  "cameras": [
    {
      "id": "cam_entrance_01",
      "name": "Main Entrance Turnstiles",
      "source_masked": "rtsp://admin:***@192.168.1.150:554/live/ch0",
      "is_connected": true,
      "status": "CONNECTED",
      "fps": 15.0,
      "resolution": [1920, 1080],
      "consecutive_failures": 0,
      "last_frame_timestamp": 1793962800.5,
      "is_webcam": false,
      "camera_type": "IP Camera",
      "location": "North Lobby Entrance",
      "ip_address": "192.168.1.150",
      "port": 554,
      "stream_path": "/live/ch0",
      "last_status_update": "2026-11-06T12:00:00Z"
    }
  ]
}
```
