package com.shopguard.ai.data.repository

import com.shopguard.ai.data.model.*
import java.text.SimpleDateFormat
import java.util.*

class DemoDataProvider {
    // In-memory mutable security state for functional interactive demo controls
    var currentDemoState: SecurityState = SecurityState.DISARMED
        private set

    private val demoCameras = mutableListOf(
        CameraInfo(
            id = "demo_cam_01",
            name = "[DEMO] Front Entrance CCTV",
            sourceMasked = "rtsp://admin:***@192.168.1.101:554/live",
            isConnected = true,
            status = "CONNECTED",
            fps = 15.0,
            resolution = listOf(1920, 1080),
            consecutiveFailures = 0,
            lastFrameTimestamp = System.currentTimeMillis() / 1000.0,
            isWebcam = false,
            cameraType = "IP Camera",
            location = "Main Building Entry Foyer",
            ipAddress = "192.168.1.101",
            port = 554,
            streamPath = "/live",
            lastStatusUpdate = "Just now"
        ),
        CameraInfo(
            id = "demo_cam_02",
            name = "[DEMO] Cash Counter & Safe",
            sourceMasked = "rtsp://admin:***@192.168.1.102:554/live",
            isConnected = true,
            status = "CONNECTED",
            fps = 15.0,
            resolution = listOf(1280, 720),
            consecutiveFailures = 0,
            lastFrameTimestamp = System.currentTimeMillis() / 1000.0,
            isWebcam = false,
            cameraType = "DVR",
            location = "Cashier Station & Vault",
            ipAddress = "192.168.1.102",
            port = 554,
            streamPath = "/ch2/main",
            lastStatusUpdate = "Just now"
        ),
        CameraInfo(
            id = "demo_cam_03",
            name = "[DEMO] Rear Storage Bay",
            sourceMasked = "rtsp://admin:***@192.168.1.103:554/live",
            isConnected = true,
            status = "CONNECTED",
            fps = 15.0,
            resolution = listOf(1920, 1080),
            consecutiveFailures = 0,
            lastFrameTimestamp = System.currentTimeMillis() / 1000.0,
            isWebcam = false,
            cameraType = "NVR",
            location = "Loading Dock / Service Exit",
            ipAddress = "192.168.1.103",
            port = 554,
            streamPath = "/cam/realmonitor?channel=3&subtype=0",
            lastStatusUpdate = "Just now"
        )
    )

    private val demoIncidents = mutableListOf(
        IncidentSummary(
            incidentId = "demo_inc_001",
            cameraId = "demo_cam_02",
            cameraName = "[DEMO] Cash Counter & Safe",
            eventType = "PERSON_ENTERED_RESTRICTED_ZONE",
            eventTimestamp = "2026-11-05 21:45:12",
            timestamp = System.currentTimeMillis() / 1000.0 - 180,
            trackId = 12,
            confidence = 0.94,
            zoneName = "Cash Drawer Restricted Area",
            videoFilename = "incident_demo_001.mp4",
            hasVideo = true,
            durationSeconds = 15.0,
            reviewStatus = "UNREVIEWED"
        ),
        IncidentSummary(
            incidentId = "demo_inc_002",
            cameraId = "demo_cam_01",
            cameraName = "[DEMO] Front Entrance CCTV",
            eventType = "PERSON_PRESENT_IN_RESTRICTED_ZONE",
            eventTimestamp = "2026-11-05 21:12:05",
            timestamp = System.currentTimeMillis() / 1000.0 - 2100,
            trackId = 8,
            confidence = 0.88,
            zoneName = "Entrance Protected Perimeter",
            videoFilename = "incident_demo_002.mp4",
            hasVideo = true,
            durationSeconds = 12.5,
            reviewStatus = "REVIEWED"
        ),
        IncidentSummary(
            incidentId = "demo_inc_003",
            cameraId = "demo_cam_03",
            cameraName = "[DEMO] Rear Storage Bay",
            eventType = "POSSIBLE_SUSPICIOUS_ACTIVITY",
            eventTimestamp = "2026-11-05 20:30:40",
            timestamp = System.currentTimeMillis() / 1000.0 - 4500,
            trackId = 5,
            confidence = 0.79,
            zoneName = "Emergency Exit Corridor",
            videoFilename = "incident_demo_003.mp4",
            hasVideo = true,
            durationSeconds = 8.0,
            reviewStatus = "UNREVIEWED"
        )
    )

    fun getStatus(): StatusResponse {
        val now = System.currentTimeMillis() / 1000.0
        val sdf = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US)
        sdf.timeZone = TimeZone.getTimeZone("UTC")
        return StatusResponse(
            serviceStatus = "RUNNING (DEMO)",
            securityState = currentDemoState.name,
            isArmed = (currentDemoState == SecurityState.ARMED),
            timestamp = now,
            timestampIso = sdf.format(Date()),
            camerasTotal = demoCameras.size,
            camerasConnected = demoCameras.count { it.isConnected },
            activeIncidentsToday = demoIncidents.size,
            uptimeSeconds = 3600.0,
            mode = "DEMO_MODE",
            notice = "DEMO SIMULATION MODE — NOT CONNECTED TO HARDWARE CCTV"
        )
    }

    fun getSecurityState(): SecurityStateResponse {
        val sdf = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US)
        sdf.timeZone = TimeZone.getTimeZone("UTC")
        return SecurityStateResponse(
            state = currentDemoState.name,
            isArmed = (currentDemoState == SecurityState.ARMED),
            canArm = true,
            activeZonesCount = 3,
            connectedCameras = demoCameras.size,
            totalCameras = demoCameras.size,
            lastStateChange = sdf.format(Date()),
            rejectionReasons = emptyList()
        )
    }

    fun armSecurity(reason: String): ArmOperationResponse {
        currentDemoState = SecurityState.ARMED
        val sdf = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US)
        return ArmOperationResponse(
            success = true,
            state = SecurityState.ARMED.name,
            message = "Demo security system successfully ARMED.",
            timestamp = System.currentTimeMillis() / 1000.0,
            timestampIso = sdf.format(Date()),
            reason = reason
        )
    }

    fun disarmSecurity(reason: String): DisarmOperationResponse {
        currentDemoState = SecurityState.DISARMED
        val sdf = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US)
        return DisarmOperationResponse(
            success = true,
            state = SecurityState.DISARMED.name,
            message = "Demo security system successfully DISARMED.",
            timestamp = System.currentTimeMillis() / 1000.0,
            timestampIso = sdf.format(Date()),
            reason = reason
        )
    }

    fun getCameras(): CamerasResponse {
        return CamerasResponse(
            total = demoCameras.size,
            connected = demoCameras.count { it.isConnected },
            cameras = demoCameras.toList()
        )
    }

    fun testCameraConnection(req: CameraTestRequest): CameraTestResponse {
        val userStr = if (!req.username.isNullOrBlank()) "${req.username}:***@" else ""
        val masked = req.rtspUrl ?: "rtsp://${userStr}${req.ipAddress ?: "192.168.1.100"}:${req.port}${req.streamPath ?: ""}"
        return CameraTestResponse(
            success = true,
            message = "[DEMO TEST] Simulated stream probe verified (1920x1080 @ 15.0 FPS, 32ms latency).",
            resolution = listOf(1920, 1080),
            fps = 15.0,
            latencyMs = 32.0,
            sourceMasked = masked,
            details = "Demo simulation mode: Virtual RTSP feed responsive."
        )
    }

    fun addCamera(req: CameraCreateRequest): CameraOperationResponse {
        val newId = req.id ?: "demo_cam_${System.currentTimeMillis() % 10000}"
        val userStr = if (!req.username.isNullOrBlank()) "${req.username}:***@" else ""
        val masked = req.rtspUrl ?: "rtsp://${userStr}${req.ipAddress ?: "192.168.1.100"}:${req.port}${req.streamPath ?: ""}"

        val newCam = CameraInfo(
            id = newId,
            name = "[DEMO] ${req.name}",
            sourceMasked = masked,
            isConnected = true,
            status = "CONNECTED",
            fps = req.fps,
            resolution = listOf(1920, 1080),
            consecutiveFailures = 0,
            lastFrameTimestamp = System.currentTimeMillis() / 1000.0,
            isWebcam = false,
            cameraType = req.cameraType,
            location = req.location ?: "Monitored Zone",
            ipAddress = req.ipAddress,
            port = req.port,
            streamPath = req.streamPath,
            lastStatusUpdate = "Just now"
        )
        demoCameras.add(newCam)
        return CameraOperationResponse(
            success = true,
            cameraId = newId,
            message = "[DEMO] Camera '${req.name}' added successfully.",
            camera = newCam
        )
    }

    fun updateCamera(cameraId: String, req: CameraUpdateRequest): CameraOperationResponse {
        val index = demoCameras.indexOfFirst { it.id == cameraId }
        if (index == -1) {
            return CameraOperationResponse(
                success = false,
                cameraId = cameraId,
                message = "Camera '$cameraId' not found in demo storage."
            )
        }
        val existing = demoCameras[index]
        val updated = existing.copy(
            name = req.name?.let { if (it.startsWith("[DEMO]")) it else "[DEMO] $it" } ?: existing.name,
            cameraType = req.cameraType ?: existing.cameraType,
            location = req.location ?: existing.location,
            fps = req.fps ?: existing.fps,
            ipAddress = req.ipAddress ?: existing.ipAddress,
            port = req.port ?: existing.port,
            streamPath = req.streamPath ?: existing.streamPath,
            lastStatusUpdate = "Updated just now"
        )
        demoCameras[index] = updated
        return CameraOperationResponse(
            success = true,
            cameraId = cameraId,
            message = "[DEMO] Camera '${updated.name}' updated successfully.",
            camera = updated
        )
    }

    fun deleteCamera(cameraId: String): CameraOperationResponse {
        val removed = demoCameras.removeIf { it.id == cameraId }
        return CameraOperationResponse(
            success = removed,
            cameraId = cameraId,
            message = if (removed) "[DEMO] Camera '$cameraId' removed." else "Camera not found."
        )
    }

    fun getIncidents(limit: Int = 20, offset: Int = 0): IncidentsListResponse {
        val safeOffset = offset.coerceAtLeast(0)
        val paginated = demoIncidents.drop(safeOffset).take(limit)
        return IncidentsListResponse(
            total = demoIncidents.size,
            limit = limit,
            offset = safeOffset,
            incidents = paginated
        )
    }

    fun getIncidentDetail(incidentId: String): IncidentDetail {
        val summary = demoIncidents.find { it.incidentId == incidentId } ?: demoIncidents.first()
        return IncidentDetail(
            incidentId = summary.incidentId,
            cameraId = summary.cameraId,
            cameraName = summary.cameraName,
            eventType = summary.eventType,
            eventTimestamp = summary.eventTimestamp,
            trackId = summary.trackId,
            confidence = summary.confidence,
            zoneId = "zone_${summary.cameraId}_restricted",
            zoneName = summary.zoneName,
            videoFilename = summary.videoFilename ?: "incident_demo.mp4",
            videoExists = summary.hasVideo,
            videoSizeBytes = 2_458_120L,
            reviewStatus = summary.reviewStatus,
            durationSeconds = summary.durationSeconds,
            totalFrames = (summary.durationSeconds * 15).toInt(),
            sourceType = "demo_simulation",
            simulationMode = true,
            rtspVerified = false
        )
    }

    fun markIncidentReviewed(incidentId: String): Boolean {
        val inc = demoIncidents.find { it.incidentId == incidentId }
        return if (inc != null) {
            inc.reviewStatus = "REVIEWED"
            true
        } else {
            false
        }
    }

    fun getHealth(): HealthResponse {
        return HealthResponse(
            healthy = true,
            overallHealth = "HEALTHY",
            securityState = currentDemoState.name,
            aiModelLoaded = true,
            aiModelPath = "models/yolo11n.pt [DEMO SIMULATION]",
            aiDevice = "cpu",
            diskFreeGb = 145.2,
            diskTotalGb = 500.0,
            cameras = demoCameras.map {
                CameraHealthSnapshot(
                    cameraId = it.id,
                    isConnected = it.isConnected,
                    consecutiveFailures = 0,
                    lastFrameAgeSeconds = 0.1,
                    totalFramesRead = 1200L,
                    streamSourceMasked = it.sourceMasked
                )
            },
            timestamp = System.currentTimeMillis() / 1000.0,
            mode = "DEMO_MODE",
            notice = "DEMO SIMULATION MODE — NOT CONNECTED TO HARDWARE CCTV"
        )
    }
}
