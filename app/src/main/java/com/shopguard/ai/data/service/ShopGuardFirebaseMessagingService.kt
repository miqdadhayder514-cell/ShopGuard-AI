package com.shopguard.ai.data.service

import android.util.Log
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import com.shopguard.ai.data.alarm.AlarmState
import com.shopguard.ai.data.local.PreferencesManager
import com.shopguard.ai.data.notification.NotificationHelper
import com.shopguard.ai.data.repository.ShopGuardRepository
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class ShopGuardFirebaseMessagingService : FirebaseMessagingService() {

    companion object {
        private const val TAG = "ShopGuardFCM"
    }

    /**
     * Called when a new FCM registration token is generated or refreshed.
     * Tokens must be securely saved for subsequent registration with the Windows FastAPI backend.
     */
    override fun onNewToken(token: String) {
        super.onNewToken(token)

        val prefs = PreferencesManager(applicationContext)
        prefs.fcmToken = token

        // Safe logging: Never log the complete registration token in production logs
        val maskedToken = if (token.length > 12) {
            "${token.take(6)}...${token.takeLast(6)}"
        } else {
            "fcm_***"
        }
        Log.i(TAG, "New FCM registration token received (length=${token.length}, preview=$maskedToken).")

        if (!prefs.isDemoMode) {
            val repository = ShopGuardRepository(prefs)
            val deviceName = "${android.os.Build.MANUFACTURER} ${android.os.Build.MODEL}".trim()
            CoroutineScope(Dispatchers.IO).launch {
                try {
                    repository.registerDeviceToken(deviceName = if (deviceName.isNotBlank()) deviceName else "Android Device")
                } catch (e: Exception) {
                    Log.w(TAG, "Failed to auto-register new FCM token with agent: ${e.message}")
                }
            }
        }
    }

    /**
     * Called when an incoming FCM message is received while the app is in foreground or background.
     * Extracts security incident details and dispatches a high-priority heads-up alert notification.
     */
    override fun onMessageReceived(remoteMessage: RemoteMessage) {
        super.onMessageReceived(remoteMessage)

        val data = remoteMessage.data
        Log.d(TAG, "FCM message received from '${remoteMessage.from}'. Data payload size: ${data.size}")

        // 1. Extract incident identifier
        val incidentId = data["incident_id"]
            ?: data["id"]
            ?: data["event_id"]
            ?: ""

        // 2. Extract event / incident type (e.g. PERSON_ENTERED_RESTRICTED_ZONE, INTRUSION)
        val rawType = data["event_type"]
            ?: data["incident_type"]
            ?: data["type"]
            ?: remoteMessage.notification?.title
            ?: "Restricted Zone Intrusion"

        // 3. Extract camera details
        val cameraName = data["camera_name"]
            ?: data["camera"]
            ?: data["cam_name"]
            ?: "CCTV Security Camera"
        val cameraId = data["camera_id"] ?: data["cam_id"]

        // 4. Extract timestamp of detection
        val detectionTime = data["event_timestamp"]
            ?: data["detection_time"]
            ?: data["timestamp_iso"]
            ?: data["time"]
            ?: SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(Date())

        val confidence = data["confidence"]

        Log.i(TAG, "Processing security alert message: incidentId='$incidentId', type='$rawType', camera='$cameraName'")

        // 5. Present high-importance notification with deep link to incident screen
        NotificationHelper.showIncidentNotification(
            context = applicationContext,
            incidentId = incidentId,
            incidentType = rawType,
            cameraName = cameraName,
            detectionTime = detectionTime,
            cameraId = cameraId,
            confidence = confidence
        )

        // 6. Trigger repeating alarm for genuine security incidents only.
        //    Skips test pings, heartbeats, camera health messages, and duplicates.
        val nonAlarmTypes = setOf(
            "TEST_NOTIFICATION", "STATUS_UPDATE", "CAMERA_HEALTH",
            "HEARTBEAT", "TOKEN_REFRESH", "PING"
        )
        val isGenuineAlert = incidentId.isNotBlank() &&
            rawType.isNotBlank() &&
            rawType.uppercase() !in nonAlarmTypes

        if (isGenuineAlert) {
            if (!AlarmState.isAlarmActive || AlarmState.activeIncidentId != incidentId) {
                Log.i(TAG, "Starting security alarm for new incident '$incidentId'.")
                SecurityAlarmService.startAlarm(
                    context      = applicationContext,
                    incidentId   = incidentId,
                    incidentType = rawType,
                    cameraName   = cameraName,
                    detectedAt   = detectionTime
                )
            } else {
                Log.i(TAG, "Alarm already active for incident '$incidentId' — not restarting.")
            }
        }
    }
}
