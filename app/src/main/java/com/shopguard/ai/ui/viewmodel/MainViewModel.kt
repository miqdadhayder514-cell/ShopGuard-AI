package com.shopguard.ai.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.google.firebase.messaging.FirebaseMessaging
import com.shopguard.ai.data.alarm.AlarmState
import com.shopguard.ai.data.model.*
import com.shopguard.ai.data.repository.ShopGuardRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.tasks.await

data class SecurityUiState(
    val securityState: SecurityState = SecurityState.DISARMED,
    val status: StatusResponse = StatusResponse(),
    val securityStateDetails: SecurityStateResponse = SecurityStateResponse(),
    val cameras: List<CameraInfo> = emptyList(),
    val incidents: List<IncidentSummary> = emptyList(),
    val selectedIncident: IncidentDetail? = null,
    val isLoading: Boolean = false,
    val isArmingDisarming: Boolean = false,
    val errorMessage: String? = null,
    val successMessage: String? = null,
    val isDemoMode: Boolean = true,
    val deviceConfig: DeviceConfig = DeviceConfig(),
    val connectionTestResult: ConnectionTestResult? = null,
    val isTestingConnection: Boolean = false,
    val cameraTestResult: CameraTestResponse? = null,
    val isTestingCamera: Boolean = false,
    val isSavingCamera: Boolean = false,
    val cameraOperationSuccess: Boolean = false,
    val pendingIncidentDetailId: String? = null,
    val fcmTokenMasked: String = "Not Registered",
    val isNotificationPermissionGranted: Boolean = true,
    val showNotificationRationaleDialog: Boolean = false,
    // Alarm state — mirrored from AlarmState singleton so Compose can observe it
    val isAlarmActive: Boolean = false,
    val alarmIncidentId: String = "",
    val alarmIncidentType: String = "",
    val alarmCameraName: String = "",
    val alarmDetectedAt: String = ""
)

class MainViewModel(
    private val repository: ShopGuardRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(
        SecurityUiState(
            isDemoMode = repository.isDemoMode,
            deviceConfig = repository.getDeviceConfig(),
            fcmTokenMasked = repository.getMaskedFcmToken()
        )
    )
    val uiState: StateFlow<SecurityUiState> = _uiState.asStateFlow()

    init {
        refreshAll()
    }

    fun refreshAll() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true) }
            try {
                // 1. Fetch verified security state details from /api/security/state
                val secDetailsRes = repository.getSecurityState()
                val secDetails = secDetailsRes.getOrNull() ?: SecurityStateResponse()

                // Derive primary security state enum strictly from /api/security/state
                val secState = when (secDetails.state.uppercase()) {
                    "ARMED" -> SecurityState.ARMED
                    "PARTIAL" -> SecurityState.PARTIAL
                    "ARMING" -> SecurityState.ARMING
                    "OFFLINE" -> SecurityState.OFFLINE
                    else -> SecurityState.DISARMED
                }

                // 2. Fetch overall service status
                val statusRes = repository.getStatus()
                val status = statusRes.getOrNull() ?: StatusResponse()

                // 3. Fetch cameras
                val camerasRes = repository.getCameras()
                val cameras = camerasRes.getOrNull()?.cameras ?: emptyList()

                // 4. Fetch incidents
                val incidentsRes = repository.getIncidents(limit = 30)
                val incidents = incidentsRes.getOrNull()?.incidents ?: emptyList()

                _uiState.update { current ->
                    current.copy(
                        securityState = secState,
                        status = status,
                        securityStateDetails = secDetails,
                        cameras = cameras,
                        incidents = incidents,
                        isLoading = false,
                        isDemoMode = repository.isDemoMode
                    )
                }
            } catch (e: Exception) {
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        errorMessage = "Sync failed: ${e.localizedMessage ?: e.javaClass.simpleName}"
                    )
                }
            }
        }
    }

    fun armSecurity(reason: String = "Shop closed - Manager armed via mobile app") {
        viewModelScope.launch {
            val config = repository.getDeviceConfig()

            // Validate API key in live mode before sending request
            if (!repository.isDemoMode && config.apiKey.isBlank()) {
                _uiState.update {
                    it.copy(
                        isArmingDisarming = false,
                        errorMessage = "Cannot arm: Agent Secret API Key is required. Please configure your API key in Settings → Device Connection."
                    )
                }
                return@launch
            }

            _uiState.update { it.copy(isArmingDisarming = true, errorMessage = null, successMessage = null) }
            val result = repository.armSecurity(reason)

            result.onSuccess { res ->
                // Immediately fetch verified /api/security/state from backend
                val stateRes = repository.getSecurityState()
                val verifiedState = stateRes.getOrNull()

                val confirmedState = when ((verifiedState?.state ?: res.state).uppercase()) {
                    "ARMED" -> SecurityState.ARMED
                    "PARTIAL" -> SecurityState.PARTIAL
                    "ARMING" -> SecurityState.ARMING
                    "OFFLINE" -> SecurityState.OFFLINE
                    else -> SecurityState.DISARMED
                }

                _uiState.update { current ->
                    current.copy(
                        isArmingDisarming = false,
                        securityState = confirmedState,
                        securityStateDetails = verifiedState ?: current.securityStateDetails,
                        successMessage = res.message.ifBlank { "Security system successfully ARMED." }
                    )
                }

                // Refresh cameras & telemetry without wiping out successMessage
                refreshTelemetryQuietly()
            }.onFailure { err ->
                _uiState.update {
                    it.copy(
                        isArmingDisarming = false,
                        errorMessage = err.localizedMessage ?: err.message ?: "Arming rejected by agent."
                    )
                }
                // Verify actual state so UI never displays ARMED on failure
                syncSecurityStateQuietly()
            }
        }
    }

    fun disarmSecurity(reason: String = "Morning opening - Disarmed via mobile app") {
        viewModelScope.launch {
            val config = repository.getDeviceConfig()

            // Validate API key in live mode before sending request
            if (!repository.isDemoMode && config.apiKey.isBlank()) {
                _uiState.update {
                    it.copy(
                        isArmingDisarming = false,
                        errorMessage = "Cannot disarm: Agent Secret API Key is required. Please configure your API key in Settings → Device Connection."
                    )
                }
                return@launch
            }

            _uiState.update { it.copy(isArmingDisarming = true, errorMessage = null, successMessage = null) }
            val result = repository.disarmSecurity(reason)

            result.onSuccess { res ->
                // Immediately fetch verified /api/security/state from backend
                val stateRes = repository.getSecurityState()
                val verifiedState = stateRes.getOrNull()

                val confirmedState = when ((verifiedState?.state ?: res.state).uppercase()) {
                    "DISARMED" -> SecurityState.DISARMED
                    "ARMED" -> SecurityState.ARMED
                    "PARTIAL" -> SecurityState.PARTIAL
                    else -> SecurityState.DISARMED
                }

                _uiState.update { current ->
                    current.copy(
                        isArmingDisarming = false,
                        securityState = confirmedState,
                        securityStateDetails = verifiedState ?: current.securityStateDetails,
                        successMessage = res.message.ifBlank { "Security system successfully DISARMED." }
                    )
                }

                refreshTelemetryQuietly()
            }.onFailure { err ->
                _uiState.update {
                    it.copy(
                        isArmingDisarming = false,
                        errorMessage = err.localizedMessage ?: err.message ?: "Disarming rejected by agent."
                    )
                }
                syncSecurityStateQuietly()
            }
        }
    }

    private suspend fun syncSecurityStateQuietly() {
        try {
            val secDetailsRes = repository.getSecurityState()
            val secDetails = secDetailsRes.getOrNull() ?: return
            val secState = when (secDetails.state.uppercase()) {
                "ARMED" -> SecurityState.ARMED
                "PARTIAL" -> SecurityState.PARTIAL
                "ARMING" -> SecurityState.ARMING
                "OFFLINE" -> SecurityState.OFFLINE
                else -> SecurityState.DISARMED
            }
            _uiState.update { current ->
                current.copy(
                    securityState = secState,
                    securityStateDetails = secDetails
                )
            }
        } catch (_: Exception) {}
    }

    private suspend fun refreshTelemetryQuietly() {
        try {
            val camerasRes = repository.getCameras()
            val cameras = camerasRes.getOrNull()?.cameras ?: emptyList()
            val incidentsRes = repository.getIncidents(limit = 30)
            val incidents = incidentsRes.getOrNull()?.incidents ?: emptyList()
            val statusRes = repository.getStatus()
            val status = statusRes.getOrNull() ?: StatusResponse()

            _uiState.update { current ->
                current.copy(
                    cameras = cameras,
                    incidents = incidents,
                    status = status
                )
            }
        } catch (_: Exception) {}
    }

    fun loadIncidentDetail(incidentId: String) {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, errorMessage = null) }
            val result = repository.getIncidentDetail(incidentId)
            result.onSuccess { detail ->
                _uiState.update { it.copy(selectedIncident = detail, isLoading = false) }
            }.onFailure { err ->
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        errorMessage = "Could not load incident details: ${err.message}"
                    )
                }
            }
        }
    }

    fun markIncidentReviewed(incidentId: String) {
        viewModelScope.launch {
            repository.markIncidentReviewed(incidentId)
            // Update in-memory state
            _uiState.update { current ->
                val updatedIncidents = current.incidents.map {
                    if (it.incidentId == incidentId) it.copy(reviewStatus = "REVIEWED") else it
                }
                val updatedSelected = if (current.selectedIncident?.incidentId == incidentId) {
                    current.selectedIncident.copy(reviewStatus = "REVIEWED")
                } else {
                    current.selectedIncident
                }
                current.copy(
                    incidents = updatedIncidents,
                    selectedIncident = updatedSelected,
                    successMessage = "Incident marked as reviewed"
                )
            }
        }
    }

    fun setDemoMode(enabled: Boolean) {
        repository.setDemoMode(enabled)
        _uiState.update {
            it.copy(
                isDemoMode = enabled,
                successMessage = if (enabled) "Switched to Demo Simulation Mode" else "Switched to Live Agent Connection Mode"
            )
        }
        refreshAll()
    }

    fun saveDeviceConfig(config: DeviceConfig) {
        repository.saveDeviceConfig(config)
        _uiState.update {
            it.copy(
                deviceConfig = config,
                isDemoMode = config.isDemoMode,
                successMessage = "Device connection settings saved."
            )
        }
        syncFcmTokenWithBackend()
        refreshAll()
    }

    fun testConnection(host: String, port: Int, apiKey: String, useHttps: Boolean = false) {
        viewModelScope.launch {
            _uiState.update { it.copy(isTestingConnection = true, connectionTestResult = null) }
            val result = repository.testConnection(host, port, apiKey, useHttps)
            _uiState.update {
                it.copy(
                    isTestingConnection = false,
                    connectionTestResult = result
                )
            }
        }
    }

    fun testCameraConnection(req: CameraTestRequest) {
        viewModelScope.launch {
            _uiState.update { it.copy(isTestingCamera = true, cameraTestResult = null, errorMessage = null) }
            val res = repository.testCameraConnection(req)
            res.onSuccess { result ->
                _uiState.update {
                    it.copy(
                        isTestingCamera = false,
                        cameraTestResult = result
                    )
                }
            }.onFailure { err ->
                _uiState.update {
                    it.copy(
                        isTestingCamera = false,
                        cameraTestResult = CameraTestResponse(
                            success = false,
                            message = "Connection probe failed: ${err.message ?: "Unknown error"}",
                            details = err.localizedMessage
                        )
                    )
                }
            }
        }
    }

    fun clearCameraTestResult() {
        _uiState.update { it.copy(cameraTestResult = null) }
    }

    fun addCamera(req: CameraCreateRequest, onComplete: (Boolean) -> Unit = {}) {
        viewModelScope.launch {
            _uiState.update { it.copy(isSavingCamera = true, errorMessage = null, successMessage = null) }
            val res = repository.addCamera(req)
            res.onSuccess { op ->
                _uiState.update {
                    it.copy(
                        isSavingCamera = false,
                        cameraOperationSuccess = true,
                        successMessage = op.message
                    )
                }
                refreshAll()
                onComplete(true)
            }.onFailure { err ->
                _uiState.update {
                    it.copy(
                        isSavingCamera = false,
                        cameraOperationSuccess = false,
                        errorMessage = "Failed to add camera: ${err.message}"
                    )
                }
                onComplete(false)
            }
        }
    }

    fun updateCamera(cameraId: String, req: CameraUpdateRequest, onComplete: (Boolean) -> Unit = {}) {
        viewModelScope.launch {
            _uiState.update { it.copy(isSavingCamera = true, errorMessage = null, successMessage = null) }
            val res = repository.updateCamera(cameraId, req)
            res.onSuccess { op ->
                _uiState.update {
                    it.copy(
                        isSavingCamera = false,
                        cameraOperationSuccess = true,
                        successMessage = op.message
                    )
                }
                refreshAll()
                onComplete(true)
            }.onFailure { err ->
                _uiState.update {
                    it.copy(
                        isSavingCamera = false,
                        cameraOperationSuccess = false,
                        errorMessage = "Failed to update camera: ${err.message}"
                    )
                }
                onComplete(false)
            }
        }
    }

    fun deleteCamera(cameraId: String, onComplete: (Boolean) -> Unit = {}) {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, errorMessage = null, successMessage = null) }
            val res = repository.deleteCamera(cameraId)
            res.onSuccess { op ->
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        successMessage = op.message
                    )
                }
                refreshAll()
                onComplete(true)
            }.onFailure { err ->
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        errorMessage = "Failed to remove camera: ${err.message}"
                    )
                }
                onComplete(false)
            }
        }
    }

    fun resetCameraOperationState() {
        _uiState.update { it.copy(cameraTestResult = null, cameraOperationSuccess = false) }
    }

    fun setPendingIncidentDetailId(incidentId: String?) {
        _uiState.update { it.copy(pendingIncidentDetailId = incidentId) }
    }

    fun clearPendingIncidentDetailId() {
        _uiState.update { it.copy(pendingIncidentDetailId = null) }
    }

    fun updateFcmToken(token: String) {
        repository.updateFcmToken(token)
        _uiState.update { it.copy(fcmTokenMasked = repository.getMaskedFcmToken()) }
        syncFcmTokenWithBackend()
    }

    /** Returns the full raw FCM registration token for clipboard copy / Firebase Console testing. */
    fun getFullFcmToken(): String = repository.getFcmToken() ?: ""

    /**
     * Fetches the current FCM registration token directly from Firebase (bypassing onNewToken).
     * This is needed when the app is reinstalled but Firebase hasn't rotated the token,
     * so onNewToken is never called but a valid token exists in Firebase's cache.
     * Saves the token to SharedPreferences and syncs with the backend.
     */
    fun fetchFcmTokenFromFirebase() {
        viewModelScope.launch {
            try {
                val token = FirebaseMessaging.getInstance().token.await()
                if (token.isNotBlank()) {
                    repository.updateFcmToken(token)
                    _uiState.update { it.copy(fcmTokenMasked = repository.getMaskedFcmToken()) }
                    syncFcmTokenWithBackend()
                }
            } catch (_: Exception) {
                // Firebase not available or token fetch failed — silently ignore
            }
        }
    }

    fun syncFcmTokenWithBackend() {
        viewModelScope.launch {
            try {
                if (!repository.isDemoMode) {
                    val deviceName = "${android.os.Build.MANUFACTURER} ${android.os.Build.MODEL}".trim()
                    repository.registerDeviceToken(deviceName = if (deviceName.isNotBlank()) deviceName else "Android Device")
                }
            } catch (_: Exception) {
                // Background sync failure should not disrupt UI
            }
        }
    }

    fun setNotificationPermissionState(granted: Boolean) {
        _uiState.update { it.copy(isNotificationPermissionGranted = granted) }
    }

    fun setShowNotificationRationaleDialog(show: Boolean) {
        _uiState.update { it.copy(showNotificationRationaleDialog = show) }
    }

    fun clearMessages() {
        _uiState.update { it.copy(errorMessage = null, successMessage = null) }
    }

    /**
     * Reads the current [AlarmState] singleton and pushes its values into the
     * observable [SecurityUiState] so Compose can react to changes that happen
     * while the UI is not in the foreground (e.g. FCM received while app backgrounded).
     */
    fun syncAlarmState() {
        _uiState.update {
            it.copy(
                isAlarmActive    = AlarmState.isAlarmActive,
                alarmIncidentId  = AlarmState.activeIncidentId,
                alarmIncidentType = AlarmState.activeIncidentType,
                alarmCameraName  = AlarmState.activeCameraName,
                alarmDetectedAt  = AlarmState.activeDetectedAt
            )
        }
    }

    /** Clears alarm from both the singleton and observable state. */
    fun clearAlarmState() {
        AlarmState.clearAlarm()
        _uiState.update {
            it.copy(
                isAlarmActive    = false,
                alarmIncidentId  = "",
                alarmIncidentType = "",
                alarmCameraName  = "",
                alarmDetectedAt  = ""
            )
        }
    }
}
