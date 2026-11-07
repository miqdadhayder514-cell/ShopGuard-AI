package com.shopguard.ai

import com.google.gson.Gson
import com.shopguard.ai.data.model.*
import com.shopguard.ai.data.network.UrlBuilder
import com.shopguard.ai.data.repository.DemoDataProvider
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

class ShopGuardUnitTest {

    private lateinit var demoProvider: DemoDataProvider

    @Before
    fun setUp() {
        demoProvider = DemoDataProvider()
    }

    @Test
    fun testDemoModeInitialStateIsDisarmed() {
        val status = demoProvider.getStatus()
        assertEquals("DISARMED", status.securityState)
        assertFalse(status.isArmed)
        assertEquals(SecurityState.DISARMED, demoProvider.currentDemoState)
        assertEquals("DEMO_MODE", status.mode)
    }

    @Test
    fun testDemoModeArmAndDisarmLifecycle() {
        // Arm
        val armRes = demoProvider.armSecurity("Test arm")
        assertTrue(armRes.success)
        assertEquals("ARMED", armRes.state)
        assertEquals(SecurityState.ARMED, demoProvider.currentDemoState)
        assertTrue(demoProvider.getStatus().isArmed)

        // Disarm
        val disarmRes = demoProvider.disarmSecurity("Test disarm")
        assertTrue(disarmRes.success)
        assertEquals("DISARMED", disarmRes.state)
        assertEquals(SecurityState.DISARMED, demoProvider.currentDemoState)
        assertFalse(demoProvider.getStatus().isArmed)
    }

    @Test
    fun testDemoModeCamerasTelemetry() {
        val camerasRes = demoProvider.getCameras()
        assertTrue(camerasRes.total >= 3)
        assertEquals(camerasRes.total, camerasRes.connected)

        val firstCam = camerasRes.cameras.first()
        assertTrue(firstCam.isConnected)
        assertTrue(firstCam.name.contains("[DEMO]"))
        assertNotNull(firstCam.resolutionFormatted)
        assertNotNull(firstCam.cameraType)
    }

    @Test
    fun testDemoModeCameraManagementLifecycle() {
        val initialCount = demoProvider.getCameras().total

        // 1. Add Camera
        val addReq = CameraCreateRequest(
            name = "Parking Lot South",
            cameraType = "IP Camera",
            ipAddress = "192.168.1.180",
            port = 554,
            username = "admin",
            password = "SecretPassword123",
            streamPath = "/h264/main",
            location = "South Perimeter Gate"
        )
        val addRes = demoProvider.addCamera(addReq)
        assertTrue(addRes.success)
        val newCamId = addRes.cameraId
        assertNotNull(newCamId)

        val afterAdd = demoProvider.getCameras()
        assertEquals(initialCount + 1, afterAdd.total)
        val created = afterAdd.cameras.find { it.id == newCamId }
        assertNotNull(created)
        assertTrue(created!!.name.contains("Parking Lot South"))
        assertEquals("South Perimeter Gate", created.location)
        assertEquals("IP Camera", created.cameraType)

        // 2. Update Camera
        val updateReq = CameraUpdateRequest(
            name = "Parking Lot South - Extended View",
            location = "South Perimeter & Fence",
            fps = 10.0
        )
        val updateRes = demoProvider.updateCamera(newCamId, updateReq)
        assertTrue(updateRes.success)
        val updatedCam = demoProvider.getCameras().cameras.find { it.id == newCamId }
        assertNotNull(updatedCam)
        assertTrue(updatedCam!!.name.contains("Parking Lot South - Extended View"))
        assertEquals("South Perimeter & Fence", updatedCam.location)
        assertEquals(10.0, updatedCam.fps, 0.01)

        // 3. Delete Camera
        val delRes = demoProvider.deleteCamera(newCamId)
        assertTrue(delRes.success)
        assertEquals(initialCount, demoProvider.getCameras().total)
        assertNull(demoProvider.getCameras().cameras.find { it.id == newCamId })
    }

    @Test
    fun testDemoModeCameraTestProbe() {
        val probeReq = CameraTestRequest(
            name = "Main Gate Probe",
            cameraType = "NVR",
            ipAddress = "192.168.1.200",
            port = 554,
            username = "admin",
            password = "SecretPassword999",
            streamPath = "/cam0"
        )
        val probeRes = demoProvider.testCameraConnection(probeReq)
        assertTrue(probeRes.success)
        assertNotNull(probeRes.resolution)
        assertEquals(2, probeRes.resolution?.size)
        assertTrue(probeRes.message.contains("[DEMO TEST]"))
        assertFalse(probeRes.sourceMasked.contains("SecretPassword999"))
        assertTrue(probeRes.sourceMasked.contains("***"))
    }

    @Test
    fun testDemoModeIncidentsAndReviewWorkflow() {
        val listRes = demoProvider.getIncidents(limit = 10, offset = 0)
        assertTrue(listRes.total >= 1)

        val firstInc = listRes.incidents.first()
        val detail = demoProvider.getIncidentDetail(firstInc.incidentId)
        assertEquals(firstInc.incidentId, detail.incidentId)
        assertTrue(detail.simulationMode)

        // Mark as reviewed
        val marked = demoProvider.markIncidentReviewed(firstInc.incidentId)
        assertTrue(marked)
        val updatedDetail = demoProvider.getIncidentDetail(firstInc.incidentId)
        assertEquals("REVIEWED", updatedDetail.reviewStatus)
    }

    @Test
    fun testDeviceConfigBaseUrlFormatting() {
        // Standard Tailscale HTTPS on port 443 -> must be https://HOSTNAME/ without duplicate :443
        val tailscaleConfig = DeviceConfig(host = "shopguard-agent.tailscale.net", port = 443, useHttps = true)
        assertEquals("https://shopguard-agent.tailscale.net/", tailscaleConfig.baseUrl)

        // Raw Host with .ts.net auto-detected as HTTPS
        val autoTsConfig = DeviceConfig(host = "node-alpha.ts.net", port = 443)
        assertEquals("https://node-alpha.ts.net/", autoTsConfig.baseUrl)

        // Local emulator HTTP
        val emulatorConfig = DeviceConfig(host = "10.0.2.2", port = 8000, useHttps = false)
        assertEquals("http://10.0.2.2:8000/", emulatorConfig.baseUrl)
    }

    @Test
    fun testUrlBuilderTailscaleHttpsNoDuplicateProtocolOrPort() {
        // 1. Raw hostname with port 443
        val url1 = UrlBuilder.buildBaseUrl("laptop-agent.tailscale.net", port = 443, useHttps = true)
        assertEquals("https://laptop-agent.tailscale.net/", url1)

        // 2. User typed "https://" into host input
        val url2 = UrlBuilder.buildBaseUrl("https://laptop-agent.tailscale.net", port = 443)
        assertEquals("https://laptop-agent.tailscale.net/", url2)

        // 3. User typed trailing slash and path
        val url3 = UrlBuilder.buildBaseUrl("https://laptop-agent.tailscale.net/", port = 443)
        assertEquals("https://laptop-agent.tailscale.net/", url3)

        // 4. User typed path in host: "https://laptop-agent.tailscale.net/api/health"
        val url4 = UrlBuilder.buildBaseUrl("https://laptop-agent.tailscale.net/api/health", port = 443)
        assertEquals("https://laptop-agent.tailscale.net/", url4)

        // 5. Host has embedded :443
        val url5 = UrlBuilder.buildBaseUrl("laptop-agent.tailscale.net:443", port = 443)
        assertEquals("https://laptop-agent.tailscale.net/", url5)

        // 6. Custom HTTPS port (e.g. 8443) preserves port
        val url6 = UrlBuilder.buildBaseUrl("laptop-agent.tailscale.net", port = 8443, useHttps = true)
        assertEquals("https://laptop-agent.tailscale.net:8443/", url6)
    }

    @Test
    fun testUrlBuilderEndpointConstructionNoDuplicateSlashesOrApi() {
        val base = "https://laptop-agent.tailscale.net/"

        // GET /api/health
        val healthUrl = UrlBuilder.buildEndpointUrl(base, "/api/health")
        assertEquals("https://laptop-agent.tailscale.net/api/health", healthUrl)

        // Without leading slash
        val healthUrlNoSlash = UrlBuilder.buildEndpointUrl(base, "api/health")
        assertEquals("https://laptop-agent.tailscale.net/api/health", healthUrlNoSlash)

        // Base URL already containing /api
        val baseWithApi = "https://laptop-agent.tailscale.net/api"
        val resolved = UrlBuilder.buildEndpointUrl(baseWithApi, "/api/health")
        assertEquals("https://laptop-agent.tailscale.net/api/health", resolved)
    }

    @Test
    fun testHealthResponseJsonDeserialization() {
        val json = """
            {
                "healthy": true,
                "overall_health": "HEALTHY",
                "security_state": "DISARMED",
                "ai_model_loaded": true,
                "ai_model_path": "models/yolov8n.pt",
                "ai_device": "cpu",
                "disk_free_gb": 45.2,
                "disk_total_gb": 512.0,
                "cameras": [
                    {
                        "camera_id": "camera_01",
                        "is_connected": true,
                        "consecutive_failures": 0,
                        "last_frame_age_seconds": 0.2,
                        "total_frames_read": 1450,
                        "stream_source_masked": "rtsp://admin:***@192.168.1.100:554/live"
                    }
                ],
                "timestamp": 1730000000.0,
                "mode": "CCTV",
                "notice": null
            }
        """.trimIndent()

        val gson = Gson()
        val health = gson.fromJson(json, HealthResponse::class.java)

        assertNotNull(health)
        assertTrue(health.healthy)
        assertEquals("HEALTHY", health.overallHealth)
        assertEquals("DISARMED", health.securityState)
        assertTrue(health.aiModelLoaded)
        assertEquals("CCTV", health.mode)
        assertEquals(1, health.cameras.size)
        assertEquals("camera_01", health.cameras.first().cameraId)
        assertTrue(health.cameras.first().isConnected)
    }

    @Test
    fun testConnectionTestResultStatusErrorMapping() {
        val badRequest = ConnectionTestResult(
            isSuccess = false,
            statusCode = 400,
            message = "HTTP 400 Bad Request: Host rejected the request.",
            rawResponseBody = "The plain HTTP request was sent to HTTPS port",
            errorType = ConnectionErrorType.BAD_REQUEST_400
        )
        assertFalse(badRequest.isSuccess)
        assertEquals(400, badRequest.statusCode)
        assertEquals(ConnectionErrorType.BAD_REQUEST_400, badRequest.errorType)
        assertTrue(badRequest.rawResponseBody!!.contains("HTTP request was sent to HTTPS port"))

        val unauthorized = ConnectionTestResult(
            isSuccess = false,
            statusCode = 401,
            message = "HTTP 401 Unauthorized",
            rawResponseBody = "{\"error\":\"UNAUTHORIZED\"}",
            errorType = ConnectionErrorType.UNAUTHORIZED_401
        )
        assertEquals(401, unauthorized.statusCode)
        assertEquals(ConnectionErrorType.UNAUTHORIZED_401, unauthorized.errorType)
    }

    @Test
    fun testSecurityStateDisplayNames() {
        assertEquals("Armed", SecurityState.ARMED.displayName)
        assertEquals("Disarmed", SecurityState.DISARMED.displayName)
        assertEquals("Arming", SecurityState.ARMING.displayName)
        assertEquals("Partial", SecurityState.PARTIAL.displayName)
        assertEquals("Offline", SecurityState.OFFLINE.displayName)
    }

    @Test
    fun testArmAndDisarmResponseDeserialization() {
        val armJson = """
            {
                "success": true,
                "state": "ARMED",
                "message": "Security system successfully ARMED. All protected zones are active.",
                "timestamp": 1730001000.0,
                "timestamp_iso": "2026-11-06T09:00:00Z"
            }
        """.trimIndent()

        val gson = Gson()
        val armRes = gson.fromJson(armJson, ArmOperationResponse::class.java)
        assertTrue(armRes.success)
        assertEquals("ARMED", armRes.state)
        assertTrue(armRes.message.contains("ARMED"))

        val disarmJson = """
            {
                "success": true,
                "state": "DISARMED",
                "message": "Security system DISARMED. Intrusion monitoring inactive.",
                "timestamp": 1730002000.0,
                "timestamp_iso": "2026-11-06T09:15:00Z"
            }
        """.trimIndent()

        val disarmRes = gson.fromJson(disarmJson, DisarmOperationResponse::class.java)
        assertTrue(disarmRes.success)
        assertEquals("DISARMED", disarmRes.state)
        assertTrue(disarmRes.message.contains("DISARMED"))
    }

    @Test
    fun testSecurityStateResponseDeserialization() {
        val stateJson = """
            {
                "state": "DISARMED",
                "is_armed": false,
                "can_arm": true,
                "active_zones_count": 2,
                "connected_cameras": 1,
                "total_cameras": 1,
                "last_state_change": "2026-11-06T08:00:00Z",
                "rejection_reasons": []
            }
        """.trimIndent()

        val gson = Gson()
        val secState = gson.fromJson(stateJson, SecurityStateResponse::class.java)
        assertEquals("DISARMED", secState.state)
        assertFalse(secState.isArmed)
        assertTrue(secState.canArm)
        assertEquals(2, secState.activeZonesCount)
        assertEquals(1, secState.connectedCameras)
        assertTrue(secState.rejectionReasons.isEmpty())
    }

    @Test
    fun testSecurityStateRejectionDetails() {
        val rejectedJson = """
            {
                "state": "DISARMED",
                "is_armed": false,
                "can_arm": false,
                "active_zones_count": 0,
                "connected_cameras": 0,
                "total_cameras": 1,
                "rejection_reasons": [
                    "None of the enabled cameras are currently connected.",
                    "No valid intrusion zones defined."
                ]
            }
        """.trimIndent()

        val gson = Gson()
        val rejectedState = gson.fromJson(rejectedJson, SecurityStateResponse::class.java)
        assertEquals("DISARMED", rejectedState.state)
        assertFalse(rejectedState.isArmed)
        assertFalse(rejectedState.canArm)
        assertEquals(2, rejectedState.rejectionReasons.size)
        assertTrue(rejectedState.rejectionReasons.first().contains("None of the enabled cameras"))
    }

    @Test
    fun testSecurityApiExceptionHandling() {
        val authError = com.shopguard.ai.data.network.SecurityApiException(
            statusCode = 401,
            errorCode = "UNAUTHORIZED",
            message = "Authentication Failed (HTTP 401): Invalid or missing Agent Secret API Key. Check Settings → Device Connection."
        )
        assertEquals(401, authError.statusCode)
        assertEquals("UNAUTHORIZED", authError.errorCode)
        assertTrue(authError.message.contains("Authentication Failed"))

        val rejectError = com.shopguard.ai.data.network.SecurityApiException(
            statusCode = 400,
            errorCode = "ARMING_REJECTED",
            message = "Arming Rejected: None of the enabled cameras are currently connected.",
            reasons = listOf("None of the enabled cameras are currently connected.")
        )
        assertEquals(400, rejectError.statusCode)
        assertEquals("ARMING_REJECTED", rejectError.errorCode)
        assertEquals(1, rejectError.reasons.size)
    }

    @Test
    fun testFcmTokenMaskingPrivacy() {
        val fullToken = "fcm_test_token_abcdef1234567890_secret_registration_key_xyz987"
        val masked = when {
            fullToken.isBlank() -> "Not Registered"
            fullToken.length <= 12 -> "fcm_***"
            else -> "${fullToken.take(6)}...${fullToken.takeLast(6)}"
        }

        assertFalse(masked.contains("secret_registration_key"))
        assertTrue(masked.startsWith("fcm_te"))
        assertTrue(masked.endsWith("xyz987"))
        assertTrue(masked.contains("..."))

        // Blank token fallback
        val emptyMasked = "".ifBlank { "Not Registered" }
        assertEquals("Not Registered", emptyMasked)
    }

    @Test
    fun testFcmAlertPayloadParsing() {
        val payloadMap = mapOf(
            "incident_id" to "incident_20261106_001",
            "event_type" to "PERSON_ENTERED_RESTRICTED_ZONE",
            "camera_name" to "Front Counter CCTV",
            "camera_id" to "cam_01",
            "event_timestamp" to "2026-11-06T15:30:00Z",
            "confidence" to "0.94"
        )

        assertEquals("incident_20261106_001", payloadMap["incident_id"])
        assertEquals("PERSON_ENTERED_RESTRICTED_ZONE", payloadMap["event_type"])
        assertEquals("Front Counter CCTV", payloadMap["camera_name"])
        assertEquals("cam_01", payloadMap["camera_id"])
        assertEquals("2026-11-06T15:30:00Z", payloadMap["event_timestamp"])
        assertEquals("0.94", payloadMap["confidence"])
    }
}
