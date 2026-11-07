package com.shopguard.ai.data.model

import com.google.gson.annotations.SerializedName

enum class SecurityState(val displayName: String) {
    @SerializedName("DISARMED")
    DISARMED("Disarmed"),

    @SerializedName("ARMING")
    ARMING("Arming"),

    @SerializedName("ARMED")
    ARMED("Armed"),

    @SerializedName("PARTIAL")
    PARTIAL("Partial"),

    @SerializedName("OFFLINE")
    OFFLINE("Offline")
}

data class StatusResponse(
    @SerializedName("service_status") val serviceStatus: String = "UNKNOWN",
    @SerializedName("security_state") val securityState: String = "DISARMED",
    @SerializedName("is_armed") val isArmed: Boolean = false,
    @SerializedName("timestamp") val timestamp: Double = 0.0,
    @SerializedName("timestamp_iso") val timestampIso: String = "",
    @SerializedName("cameras_total") val camerasTotal: Int = 0,
    @SerializedName("cameras_connected") val camerasConnected: Int = 0,
    @SerializedName("active_incidents_today") val activeIncidentsToday: Int = 0,
    @SerializedName("uptime_seconds") val uptimeSeconds: Double = 0.0,
    @SerializedName("mode") val mode: String = "CCTV",
    @SerializedName("notice") val notice: String? = null
)

data class SecurityStateResponse(
    @SerializedName("state") val state: String = "DISARMED",
    @SerializedName("is_armed") val isArmed: Boolean = false,
    @SerializedName("can_arm") val canArm: Boolean = true,
    @SerializedName("active_zones_count") val activeZonesCount: Int = 0,
    @SerializedName("connected_cameras") val connectedCameras: Int = 0,
    @SerializedName("total_cameras") val totalCameras: Int = 0,
    @SerializedName("last_state_change") val lastStateChange: String? = null,
    @SerializedName("rejection_reasons") val rejectionReasons: List<String> = emptyList()
)

data class ArmRequest(
    @SerializedName("reason") val reason: String = "Mobile app armed by user"
)

data class ArmOperationResponse(
    @SerializedName("success") val success: Boolean = false,
    @SerializedName("state") val state: String = "",
    @SerializedName("message") val message: String = "",
    @SerializedName("timestamp") val timestamp: Double = 0.0,
    @SerializedName("timestamp_iso") val timestampIso: String = "",
    @SerializedName("reason") val reason: String? = null,
    @SerializedName("reasons") val reasons: List<String>? = null
)

data class DisarmRequest(
    @SerializedName("reason") val reason: String = "Mobile app disarmed by user"
)

data class DisarmOperationResponse(
    @SerializedName("success") val success: Boolean = false,
    @SerializedName("state") val state: String = "",
    @SerializedName("message") val message: String = "",
    @SerializedName("timestamp") val timestamp: Double = 0.0,
    @SerializedName("timestamp_iso") val timestampIso: String = "",
    @SerializedName("reason") val reason: String? = null
)

data class CameraInfo(
    @SerializedName("id") val id: String,
    @SerializedName("name") val name: String,
    @SerializedName("source_masked") val sourceMasked: String,
    @SerializedName("is_connected") val isConnected: Boolean,
    @SerializedName("status") val status: String,
    @SerializedName("fps") val fps: Double = 0.0,
    @SerializedName("resolution") val resolution: List<Int>? = null,
    @SerializedName("consecutive_failures") val consecutiveFailures: Int = 0,
    @SerializedName("last_frame_timestamp") val lastFrameTimestamp: Double? = null,
    @SerializedName("is_webcam") val isWebcam: Boolean = false,
    @SerializedName("camera_type") val cameraType: String = "IP Camera",
    @SerializedName("location") val location: String? = null,
    @SerializedName("ip_address") val ipAddress: String? = null,
    @SerializedName("port") val port: Int? = null,
    @SerializedName("stream_path") val streamPath: String? = null,
    @SerializedName("last_status_update") val lastStatusUpdate: String? = null
) {
    val resolutionFormatted: String
        get() = if (resolution != null && resolution.size >= 2) "${resolution[0]}x${resolution[1]}" else "N/A"
}

data class CameraTestRequest(
    @SerializedName("name") val name: String? = "Test Camera",
    @SerializedName("camera_type") val cameraType: String = "IP Camera",
    @SerializedName("ip_address") val ipAddress: String? = null,
    @SerializedName("port") val port: Int = 554,
    @SerializedName("username") val username: String? = null,
    @SerializedName("password") val password: String? = null,
    @SerializedName("stream_path") val streamPath: String? = null,
    @SerializedName("rtsp_url") val rtspUrl: String? = null,
    @SerializedName("timeout_seconds") val timeoutSeconds: Double = 4.0
)

data class CameraTestResponse(
    @SerializedName("success") val success: Boolean = false,
    @SerializedName("message") val message: String = "",
    @SerializedName("resolution") val resolution: List<Int>? = null,
    @SerializedName("fps") val fps: Double? = null,
    @SerializedName("latency_ms") val latencyMs: Double? = null,
    @SerializedName("source_masked") val sourceMasked: String = "",
    @SerializedName("details") val details: String? = null
)

data class CameraCreateRequest(
    @SerializedName("id") val id: String? = null,
    @SerializedName("name") val name: String,
    @SerializedName("camera_type") val cameraType: String = "IP Camera",
    @SerializedName("ip_address") val ipAddress: String? = null,
    @SerializedName("port") val port: Int = 554,
    @SerializedName("username") val username: String? = null,
    @SerializedName("password") val password: String? = null,
    @SerializedName("stream_path") val streamPath: String? = null,
    @SerializedName("rtsp_url") val rtspUrl: String? = null,
    @SerializedName("location") val location: String? = null,
    @SerializedName("fps") val fps: Double = 5.0,
    @SerializedName("enabled") val enabled: Boolean = true
)

data class CameraUpdateRequest(
    @SerializedName("name") val name: String? = null,
    @SerializedName("camera_type") val cameraType: String? = null,
    @SerializedName("ip_address") val ipAddress: String? = null,
    @SerializedName("port") val port: Int? = null,
    @SerializedName("username") val username: String? = null,
    @SerializedName("password") val password: String? = null,
    @SerializedName("stream_path") val streamPath: String? = null,
    @SerializedName("rtsp_url") val rtspUrl: String? = null,
    @SerializedName("location") val location: String? = null,
    @SerializedName("fps") val fps: Double? = null,
    @SerializedName("enabled") val enabled: Boolean? = null
)

data class CameraOperationResponse(
    @SerializedName("success") val success: Boolean = false,
    @SerializedName("camera_id") val cameraId: String = "",
    @SerializedName("message") val message: String = "",
    @SerializedName("camera") val camera: CameraInfo? = null
)

data class CamerasResponse(
    @SerializedName("total") val total: Int = 0,
    @SerializedName("connected") val connected: Int = 0,
    @SerializedName("cameras") val cameras: List<CameraInfo> = emptyList()
)

data class IncidentSummary(
    @SerializedName("incident_id") val incidentId: String,
    @SerializedName("camera_id") val cameraId: String,
    @SerializedName("camera_name") val cameraName: String,
    @SerializedName("event_type") val eventType: String,
    @SerializedName("event_timestamp") val eventTimestamp: String,
    @SerializedName("timestamp") val timestamp: Double = 0.0,
    @SerializedName("track_id") val trackId: Int? = null,
    @SerializedName("confidence") val confidence: Double = 0.0,
    @SerializedName("zone_name") val zoneName: String,
    @SerializedName("video_filename") val videoFilename: String? = null,
    @SerializedName("has_video") val hasVideo: Boolean = false,
    @SerializedName("duration_seconds") val durationSeconds: Double = 0.0,
    @SerializedName("review_status") var reviewStatus: String = "UNREVIEWED"
) {
    val confidencePercentage: Int
        get() = (confidence * 100).toInt().coerceIn(0, 100)
}

data class IncidentsListResponse(
    @SerializedName("total") val total: Int = 0,
    @SerializedName("limit") val limit: Int = 20,
    @SerializedName("offset") val offset: Int = 0,
    @SerializedName("incidents") val incidents: List<IncidentSummary> = emptyList()
)

data class IncidentDetail(
    @SerializedName("incident_id") val incidentId: String,
    @SerializedName("camera_id") val cameraId: String,
    @SerializedName("camera_name") val cameraName: String,
    @SerializedName("event_type") val eventType: String,
    @SerializedName("event_timestamp") val eventTimestamp: String,
    @SerializedName("track_id") val trackId: Int? = null,
    @SerializedName("confidence") val confidence: Double = 0.0,
    @SerializedName("zone_id") val zoneId: String = "",
    @SerializedName("zone_name") val zoneName: String = "",
    @SerializedName("video_filename") val videoFilename: String = "",
    @SerializedName("video_exists") val videoExists: Boolean = false,
    @SerializedName("video_size_bytes") val videoSizeBytes: Long = 0L,
    @SerializedName("review_status") var reviewStatus: String = "UNREVIEWED",
    @SerializedName("duration_seconds") val durationSeconds: Double = 0.0,
    @SerializedName("total_frames") val totalFrames: Int = 0,
    @SerializedName("source_type") val sourceType: String = "live_cctv",
    @SerializedName("simulation_mode") val simulationMode: Boolean = false,
    @SerializedName("rtsp_verified") val rtspVerified: Boolean = false
)

data class CameraHealthSnapshot(
    @SerializedName("camera_id") val cameraId: String? = null,
    @SerializedName("is_connected") val isConnected: Boolean = false,
    @SerializedName("consecutive_failures") val consecutiveFailures: Int = 0,
    @SerializedName("last_frame_age_seconds") val lastFrameAgeSeconds: Double = 0.0,
    @SerializedName("total_frames_read") val totalFramesRead: Long = 0L,
    @SerializedName("stream_source_masked") val streamSourceMasked: String? = null
)

data class HealthResponse(
    @SerializedName("healthy") val healthy: Boolean = true,
    @SerializedName("overall_health") val overallHealth: String = "HEALTHY",
    @SerializedName("security_state") val securityState: String = "DISARMED",
    @SerializedName("ai_model_loaded") val aiModelLoaded: Boolean = true,
    @SerializedName("ai_model_path") val aiModelPath: String = "",
    @SerializedName("ai_device") val aiDevice: String = "cpu",
    @SerializedName("disk_free_gb") val diskFreeGb: Double = 0.0,
    @SerializedName("disk_total_gb") val diskTotalGb: Double = 0.0,
    @SerializedName("cameras") val cameras: List<CameraHealthSnapshot> = emptyList(),
    @SerializedName("timestamp") val timestamp: Double = 0.0,
    @SerializedName("mode") val mode: String = "CCTV",
    @SerializedName("notice") val notice: String? = null
)

data class SystemInfo(
    @SerializedName("service_name") val serviceName: String = "",
    @SerializedName("version") val version: String = "2.0.0",
    @SerializedName("operating_system") val operatingSystem: String = "",
    @SerializedName("python_version") val pythonVersion: String = "",
    @SerializedName("uptime_seconds") val uptimeSeconds: Double = 0.0,
    @SerializedName("cpu_count") val cpuCount: Int = 0,
    @SerializedName("process_memory_mb") val processMemoryMb: Double = 0.0,
    @SerializedName("total_incidents_recorded") val totalIncidentsRecorded: Int = 0
)

data class DeviceConfig(
    val host: String = "10.0.2.2",
    val port: Int = 8000,
    val apiKey: String = "",
    val isDemoMode: Boolean = true,
    val useHttps: Boolean = false
) {
    val baseUrl: String
        get() = com.shopguard.ai.data.network.UrlBuilder.buildBaseUrl(host, port, useHttps)
}

data class DeviceTokenRegisterRequest(
    @SerializedName("token") val token: String,
    @SerializedName("device_name") val deviceName: String = "Android Device",
    @SerializedName("app_version") val appVersion: String = "1.0.0"
)

data class DeviceTokenUnregisterRequest(
    @SerializedName("token") val token: String
)

data class NotificationOperationResponse(
    @SerializedName("success") val success: Boolean = false,
    @SerializedName("message") val message: String = "",
    @SerializedName("tokens_count") val tokensCount: Int = 0,
    @SerializedName("timestamp") val timestamp: Double = 0.0,
    @SerializedName("timestamp_iso") val timestampIso: String = ""
)

enum class ConnectionErrorType {
    NONE,
    BAD_REQUEST_400,
    UNAUTHORIZED_401,
    FORBIDDEN_403,
    NOT_FOUND_404,
    UNPROCESSABLE_ENTITY_422,
    SERVER_ERROR_5XX,
    NETWORK_TIMEOUT,
    NETWORK_UNREACHABLE,
    TLS_ERROR,
    UNKNOWN
}

data class ConnectionTestResult(
    val isSuccess: Boolean,
    val statusCode: Int = 200,
    val message: String,
    val rawResponseBody: String? = null,
    val latencyMs: Long = 0L,
    val healthResponse: HealthResponse? = null,
    val detectedState: String? = null,
    val overallHealth: String? = null,
    val aiModelLoaded: Boolean? = null,
    val mode: String? = null,
    val camerasCount: Int = 0,
    val errorType: ConnectionErrorType = ConnectionErrorType.NONE
)
