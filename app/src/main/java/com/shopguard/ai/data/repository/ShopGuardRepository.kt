package com.shopguard.ai.data.repository

import com.shopguard.ai.data.local.PreferencesManager
import com.shopguard.ai.data.model.*
import com.shopguard.ai.data.network.ApiClient
import com.shopguard.ai.data.network.UrlBuilder

class ShopGuardRepository(
    private val preferencesManager: PreferencesManager,
    private val apiClient: ApiClient = ApiClient(),
    private val demoProvider: DemoDataProvider = DemoDataProvider()
) {
    val isDemoMode: Boolean
        get() = preferencesManager.isDemoMode

    fun setDemoMode(enabled: Boolean) {
        preferencesManager.isDemoMode = enabled
    }

    fun getDeviceConfig(): DeviceConfig = preferencesManager.getDeviceConfig()

    fun saveDeviceConfig(config: DeviceConfig) {
        preferencesManager.saveDeviceConfig(config)
    }

    fun getFcmToken(): String? {
        val t = preferencesManager.fcmToken
        return t.ifBlank { null }
    }

    fun getMaskedFcmToken(): String = preferencesManager.getMaskedFcmToken()

    fun updateFcmToken(token: String) {
        preferencesManager.fcmToken = token
    }

    suspend fun registerDeviceToken(deviceName: String = "Android Device"): Result<NotificationOperationResponse>? {
        val token = getFcmToken() ?: return null
        if (preferencesManager.isDemoMode) return null
        val cfg = preferencesManager.getDeviceConfig()
        return apiClient.registerFcmToken(cfg.baseUrl, cfg.apiKey, token, deviceName)
    }

    suspend fun unregisterDeviceToken(): Result<NotificationOperationResponse>? {
        val token = getFcmToken() ?: return null
        if (preferencesManager.isDemoMode) return null
        val cfg = preferencesManager.getDeviceConfig()
        return apiClient.unregisterFcmToken(cfg.baseUrl, cfg.apiKey, token)
    }

    suspend fun getStatus(): Result<StatusResponse> {
        return if (preferencesManager.isDemoMode) {
            Result.success(demoProvider.getStatus())
        } else {
            val cfg = preferencesManager.getDeviceConfig()
            apiClient.getStatus(cfg.baseUrl, cfg.apiKey)
        }
    }

    suspend fun getCameras(): Result<CamerasResponse> {
        return if (preferencesManager.isDemoMode) {
            Result.success(demoProvider.getCameras())
        } else {
            val cfg = preferencesManager.getDeviceConfig()
            apiClient.getCameras(cfg.baseUrl, cfg.apiKey)
        }
    }

    suspend fun getSecurityState(): Result<SecurityStateResponse> {
        return if (preferencesManager.isDemoMode) {
            Result.success(demoProvider.getSecurityState())
        } else {
            val cfg = preferencesManager.getDeviceConfig()
            apiClient.getSecurityState(cfg.baseUrl, cfg.apiKey)
        }
    }

    suspend fun armSecurity(reason: String = "Armed via mobile app"): Result<ArmOperationResponse> {
        return if (preferencesManager.isDemoMode) {
            Result.success(demoProvider.armSecurity(reason))
        } else {
            val cfg = preferencesManager.getDeviceConfig()
            apiClient.armSecurity(cfg.baseUrl, cfg.apiKey, reason)
        }
    }

    suspend fun disarmSecurity(reason: String = "Disarmed via mobile app"): Result<DisarmOperationResponse> {
        return if (preferencesManager.isDemoMode) {
            Result.success(demoProvider.disarmSecurity(reason))
        } else {
            val cfg = preferencesManager.getDeviceConfig()
            apiClient.disarmSecurity(cfg.baseUrl, cfg.apiKey, reason)
        }
    }

    suspend fun getIncidents(limit: Int = 20, offset: Int = 0): Result<IncidentsListResponse> {
        return if (preferencesManager.isDemoMode) {
            Result.success(demoProvider.getIncidents(limit, offset))
        } else {
            val cfg = preferencesManager.getDeviceConfig()
            apiClient.getIncidents(cfg.baseUrl, cfg.apiKey, limit, offset)
        }
    }

    suspend fun getIncidentDetail(incidentId: String): Result<IncidentDetail> {
        return if (preferencesManager.isDemoMode) {
            Result.success(demoProvider.getIncidentDetail(incidentId))
        } else {
            val cfg = preferencesManager.getDeviceConfig()
            apiClient.getIncidentDetail(cfg.baseUrl, cfg.apiKey, incidentId)
        }
    }

    suspend fun markIncidentReviewed(incidentId: String): Boolean {
        return if (preferencesManager.isDemoMode) {
            demoProvider.markIncidentReviewed(incidentId)
        } else {
            // Live agent currently tracks state locally; optimistically succeed
            true
        }
    }

    suspend fun testCameraConnection(req: CameraTestRequest): Result<CameraTestResponse> {
        return if (preferencesManager.isDemoMode) {
            Result.success(demoProvider.testCameraConnection(req))
        } else {
            val cfg = preferencesManager.getDeviceConfig()
            apiClient.testCameraConnection(cfg.baseUrl, cfg.apiKey, req)
        }
    }

    suspend fun addCamera(req: CameraCreateRequest): Result<CameraOperationResponse> {
        return if (preferencesManager.isDemoMode) {
            Result.success(demoProvider.addCamera(req))
        } else {
            val cfg = preferencesManager.getDeviceConfig()
            apiClient.addCamera(cfg.baseUrl, cfg.apiKey, req)
        }
    }

    suspend fun updateCamera(cameraId: String, req: CameraUpdateRequest): Result<CameraOperationResponse> {
        return if (preferencesManager.isDemoMode) {
            Result.success(demoProvider.updateCamera(cameraId, req))
        } else {
            val cfg = preferencesManager.getDeviceConfig()
            apiClient.updateCamera(cfg.baseUrl, cfg.apiKey, cameraId, req)
        }
    }

    suspend fun deleteCamera(cameraId: String): Result<CameraOperationResponse> {
        return if (preferencesManager.isDemoMode) {
            Result.success(demoProvider.deleteCamera(cameraId))
        } else {
            val cfg = preferencesManager.getDeviceConfig()
            apiClient.deleteCamera(cfg.baseUrl, cfg.apiKey, cameraId)
        }
    }

    suspend fun getHealth(): Result<HealthResponse> {
        return if (preferencesManager.isDemoMode) {
            Result.success(demoProvider.getHealth())
        } else {
            val cfg = preferencesManager.getDeviceConfig()
            apiClient.getHealth(cfg.baseUrl, cfg.apiKey)
        }
    }

    suspend fun testConnection(host: String, port: Int, apiKey: String, useHttps: Boolean = false): ConnectionTestResult {
        val baseUrl = UrlBuilder.buildBaseUrl(host, port, useHttps)
        return apiClient.testConnection(baseUrl, apiKey)
    }
}
