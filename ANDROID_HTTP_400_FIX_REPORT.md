# ShopGuard AI — Android HTTP 400 Bad Request Resolution Report

**Date:** 2026-11-06  
**Component:** ShopGuard AI Android Mobile Client & Agent Connection Architecture  
**Status:** Resolved & Verified  

---

## 1. Executive Summary

When attempting to connect the ShopGuard AI Android application to the Windows FastAPI agent over an encrypted **Tailscale HTTPS** tunnel (port 443), the connection test previously failed with an **`HTTP 400 Bad Request`** error. 

Following a comprehensive inspection of the networking stack, the root cause was identified, fixed, and verified with automated unit tests and an updated APK build.

---

## 2. Root Cause Analysis

### 2.1 The Primary Cause: Plain HTTP Sent to a TLS Port
In `ShopGuardRepository.kt`, the connection test method previously constructed the URL as:
```kotlin
// PREVIOUS IMPLEMENTATION (BUGGED):
val baseUrl = "http://$host:$port"
return apiClient.testConnection(baseUrl, apiKey)
```
When a user entered their Tailscale hostname with port `443` or entered an HTTPS URL, the Android app initiated a **plain, unencrypted HTTP request** to port `443`. Because Tailscale HTTPS enforces TLS encryption, the web server/reverse proxy immediately aborted the handshake and returned:
```text
HTTP 400 Bad Request
"The plain HTTP request was sent to HTTPS port"
```

### 2.2 Scheme and Port Duplication
When users entered `https://HOSTNAME` into the host field:
- The previous string concatenation created invalid URIs like `http://https://HOSTNAME:443/`.
- Appending `:443` explicitly to an HTTPS URL can cause TLS Server Name Indication (SNI) or strict Host header validations to reject requests.

### 2.3 Wrong Endpoint for Health Probing
In `ApiClient.kt`, `testConnection` was querying `GET /api/status` instead of the standard health endpoint `GET /api/health`.

### 2.4 Lack of Error Diagnostics
Failed HTTP requests previously only surfaced a generic string (`HTTP 400: Bad Request`) without reading the actual response body or distinguishing between bad request configurations, unauthorized access, invalid paths, or network timeouts.

---

## 3. Implementation Details

### 3.1 Dedicated URL Normalizer (`UrlBuilder.kt`)
Created `com.shopguard.ai.data.network.UrlBuilder` to normalize and validate base URLs:
- **Exact Base URL Construction**: For Tailscale HTTPS on port 443, the base URL is formatted exactly as:
  ```text
  https://HOSTNAME/
  ```
- **Duplicate Prevention**: Strips existing schemes (`http://`, `https://`), embedded ports, and path segments (`/api`, `/api/health`) before rebuilding the URL.
- **Port 443 Omission**: Automatically omits `:443` on HTTPS connections to maintain clean RFC-compliant URLs.
- **Endpoint URL Builder**: Safely combines the base URL with `/api/health` without duplicated `/api` segments or double slashes.

### 3.2 Tailscale HTTPS OkHttp Client (`ApiClient.kt`)
- **GET /api/health Probing**: `testConnection` now targets `/api/health`.
- **Public vs. Protected Health Reads**:
  - If `apiKey` is blank, `/api/health` is queried unauthenticated without sending auth headers, allowing public health inspection if enabled on the Windows agent.
  - If `apiKey` is provided, it is sent via the exact `X-API-Key: <key>` HTTP header expected by the backend.
  - **No Query Parameters**: The API key is never placed in the URL query string.
- **Full JSON Telemetry Parsing**: Successful health responses parse all backend telemetry fields:
  - `healthy`: Boolean
  - `overall_health`: String (`HEALTHY`, `DEGRADED`, etc.)
  - `security_state`: String (`DISARMED`, `ARMED`)
  - `ai_model_loaded`: Boolean
  - `mode`: String (`CCTV` or `WEBCAM_TEST`)
  - `cameras`: List of camera health snapshots
- **Granular Error Handling**:
  - `HTTP 400 Bad Request`: Identifies URL, port, and protocol mismatches.
  - `HTTP 401 Unauthorized`: Distinguishes missing or invalid API keys.
  - `HTTP 403 Forbidden`: Flags agent access policy restrictions.
  - `HTTP 404 Not Found`: Flags missing endpoint paths or agent not running.
  - `HTTP 422 Unprocessable Entity`: Flags parameter validation errors.
  - `HTTP 5xx`: Flags internal agent server issues.
  - `Network / TLS Errors`: Categorizes timeouts, DNS failures, connection refusals, and TLS handshake issues.
  - **Response Body Display**: Surfaces the actual server response body in the UI for instant debugging.
- **Security & TLS Verification**: Tailscale Let's Encrypt certificates are validated using Android's standard trusted root CA store. TLS verification is strictly preserved.

### 3.3 Protocol Management & Live URL Preview (`DeviceConnectionScreen.kt`)
- Added protocol selector chips: **🔒 HTTPS (Tailscale / SSL)** and **🌐 HTTP (LAN / Local)**.
- Automatically switches to HTTPS if `.ts.net` or `https://` is typed into the host field.
- Added a **Live Target URL Preview** displaying the exact computed base URL and probe endpoint before the user tests the connection.
- Rich test result card showing latency, overall health, security state, model readiness, and camera counts on success, or error diagnostics and raw server output on failure.

### 3.4 Persistent HTTPS Configuration (`PreferencesManager.kt`)
- Persists the user's `useHttps` toggle across app launches alongside `host`, `port`, and `apiKey`.

---

## 4. Verification and Test Results

### 4.1 Android Unit Tests
Ran `./gradlew testDebugUnitTest`:
- `testDeviceConfigBaseUrlFormatting`: Passed (verified Tailscale HTTPS port 443 formats to `https://HOSTNAME/`).
- `testUrlBuilderTailscaleHttpsNoDuplicateProtocolOrPort`: Passed (tested 6 URL edge cases).
- `testUrlBuilderEndpointConstructionNoDuplicateSlashesOrApi`: Passed (tested clean endpoint concatenation).
- `testHealthResponseJsonDeserialization`: Passed (verified all health telemetry fields).
- `testConnectionTestResultStatusErrorMapping`: Passed (verified error categorization).
- `testDemoModeInitialStateIsDisarmed`: Passed.
- `testDemoModeArmAndDisarmLifecycle`: Passed.
- `testDemoModeCamerasTelemetry`: Passed.
- `testDemoModeCameraManagementLifecycle`: Passed.
- `testDemoModeCameraTestProbe`: Passed.
- `testDemoModeIncidentsAndReviewWorkflow`: Passed.
- `testSecurityStateDisplayNames`: Passed.

**Result: 12/12 unit tests PASSED.**

### 4.2 Python FastAPI Agent Backend Tests
Ran `pytest tests/test_agent_api.py tests/test_agent_webcam.py tests/test_camera_management.py`:
- 24 tests covering `/api/health`, `/api/status`, `/api/cameras`, `/api/cameras/test`, camera vault encryption, and authentication.

**Result: 24/24 tests PASSED in 9.71s.**

### 4.3 APK Compilation
Ran `./gradlew assembleDebug`:
- Built successfully in 39s.
- Output artifact: `app/build/outputs/apk/debug/app-debug.apk`.

---

## 5. Tailscale Connection Setup Guide

To connect your physical Android phone to your Windows PC over Tailscale:

1. **On your Windows PC**:
   - Ensure Tailscale is running and connected.
   - Start the ShopGuard AI agent:
     ```powershell
     .\venv\Scripts\Activate.ps1
     python tools/run_agent.py
     ```
   - If using Tailscale Serve for HTTPS:
     ```powershell
     tailscale serve --https=443 http://127.0.0.1:8000
     ```

2. **On your Android Phone**:
   - Ensure Tailscale is running and connected on the phone.
   - Open **ShopGuard AI** → **Settings** → **Device Connection**.
   - Toggle **Demo Mode** to **OFF**.
   - Select **🔒 HTTPS (Tailscale / SSL)**.
   - Enter your Tailscale machine name (e.g., `my-laptop.tailscale.net`).
   - Port: `443`.
   - Tap **Test Connection**.
   - A green card will appear confirming `Agent Reachable` with latency, health state, and camera telemetry!
   - Tap **Save & Apply**.
