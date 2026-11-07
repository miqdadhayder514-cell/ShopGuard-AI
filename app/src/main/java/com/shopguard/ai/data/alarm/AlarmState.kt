package com.shopguard.ai.data.alarm

import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicReference

/**
 * Global singleton tracking whether the ShopGuard security alarm is currently active.
 * Thread-safe — readable from Service, ViewModel, and UI without additional locking.
 */
object AlarmState {

    private val _isAlarmActive      = AtomicBoolean(false)
    private val _activeIncidentId   = AtomicReference("")
    private val _activeIncidentType = AtomicReference("")
    private val _activeCameraName   = AtomicReference("")
    private val _activeDetectedAt   = AtomicReference("")

    val isAlarmActive: Boolean   get() = _isAlarmActive.get()
    val activeIncidentId: String get() = _activeIncidentId.get()
    val activeIncidentType: String get() = _activeIncidentType.get()
    val activeCameraName: String get() = _activeCameraName.get()
    val activeDetectedAt: String get() = _activeDetectedAt.get()

    /** Mark an alarm as active with the given incident details. */
    fun setAlarmActive(
        incidentId: String,
        incidentType: String,
        cameraName: String,
        detectedAt: String
    ) {
        _activeIncidentId.set(incidentId)
        _activeIncidentType.set(incidentType)
        _activeCameraName.set(cameraName)
        _activeDetectedAt.set(detectedAt)
        _isAlarmActive.set(true)
    }

    /** Clear all alarm state — called when alarm is stopped. */
    fun clearAlarm() {
        _isAlarmActive.set(false)
        _activeIncidentId.set("")
        _activeIncidentType.set("")
        _activeCameraName.set("")
        _activeDetectedAt.set("")
    }
}
