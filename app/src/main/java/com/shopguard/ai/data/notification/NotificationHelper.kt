package com.shopguard.ai.data.notification

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.os.Build
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.shopguard.ai.MainActivity
import com.shopguard.ai.R
import com.shopguard.ai.data.local.PreferencesManager
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicInteger

object NotificationHelper {

    private const val TAG = "ShopGuardNotif"

    const val CHANNEL_ID = "shopguard_security_alerts"
    const val CHANNEL_NAME = "ShopGuard Security Alerts"
    const val CHANNEL_DESCRIPTION = "Real-time security alerts and restricted zone intrusion warnings"

    const val EXTRA_INCIDENT_ID = "com.shopguard.ai.EXTRA_INCIDENT_ID"
    const val EXTRA_CAMERA_ID = "com.shopguard.ai.EXTRA_CAMERA_ID"

    private val notificationIdGenerator = AtomicInteger(1000)

    // In-memory cache for recent notification suppression (TTL: 1 hour)
    private val inMemoryRecentAlerts = ConcurrentHashMap<String, Long>()
    private const val DUPLICATE_WINDOW_MS = 60 * 60 * 1000L // 1 hour

    /**
     * Creates the high-importance notification channel required on Android 8.0 (API 26) and above.
     */
    fun createNotificationChannel(context: Context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager ?: return

            val channel = NotificationChannel(
                CHANNEL_ID,
                CHANNEL_NAME,
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = CHANNEL_DESCRIPTION
                enableLights(true)
                lightColor = Color.RED
                enableVibration(true)
                vibrationPattern = longArrayOf(0, 400, 200, 400)
                setShowBadge(true)
                lockscreenVisibility = NotificationCompat.VISIBILITY_PUBLIC
            }

            manager.createNotificationChannel(channel)
            Log.d(TAG, "Notification channel '$CHANNEL_NAME' registered successfully.")
        }
    }

    /**
     * Thread-safe check and record for duplicate incident notifications.
     */
    @Synchronized
    fun isDuplicateIncident(context: Context, incidentId: String): Boolean {
        if (incidentId.isBlank()) return false
        val now = System.currentTimeMillis()

        // 1. Check in-memory TTL map
        val lastSeen = inMemoryRecentAlerts[incidentId]
        if (lastSeen != null && (now - lastSeen) < DUPLICATE_WINDOW_MS) {
            return true
        }

        // 2. Check persistent preferences cache
        val prefs = PreferencesManager(context)
        if (prefs.isIncidentAlreadyNotified(incidentId)) {
            inMemoryRecentAlerts[incidentId] = now
            return true
        }

        return false
    }

    /**
     * Records that an alert for this incident ID has been presented.
     */
    @Synchronized
    fun markIncidentNotified(context: Context, incidentId: String) {
        if (incidentId.isBlank()) return
        val now = System.currentTimeMillis()
        inMemoryRecentAlerts[incidentId] = now

        // Clean up expired in-memory keys
        val iterator = inMemoryRecentAlerts.entries.iterator()
        while (iterator.hasNext()) {
            val entry = iterator.next()
            if (now - entry.value > DUPLICATE_WINDOW_MS) {
                iterator.remove()
            }
        }

        // Persist to SharedPreferences
        val prefs = PreferencesManager(context)
        prefs.recordNotifiedIncident(incidentId)
    }

    /**
     * Builds and displays a high-importance security incident alert notification.
     * Contains incident type, camera name, detection time, and deep links into the incident screen.
     */
    fun showIncidentNotification(
        context: Context,
        incidentId: String,
        incidentType: String,
        cameraName: String,
        detectionTime: String,
        cameraId: String? = null,
        confidence: String? = null
    ) {
        // Ensure channel exists
        createNotificationChannel(context)

        // Verify notification permission on Android 13+
        if (!areNotificationsEnabled(context)) {
            Log.w(TAG, "Notification permission not granted or notifications disabled. Alert suppressed.")
            return
        }

        // Deduplication check
        if (incidentId.isNotBlank() && isDuplicateIncident(context, incidentId)) {
            Log.i(TAG, "Duplicate incident alert suppressed for ID: '$incidentId'")
            return
        }

        val displayType = incidentType.ifBlank { "Intrusion Alert" }.replace("_", " ")
        val displayCamera = cameraName.ifBlank { "Monitored Camera" }
        val displayTime = detectionTime.ifBlank { "Just now" }

        val title = "SECURITY ALERT: $displayType"
        val shortContent = "$displayCamera • $displayTime"
        val expandedDetails = buildString {
            append("$displayType detected on $displayCamera at $displayTime.")
            if (!confidence.isNullOrBlank()) {
                append("\nConfidence: $confidence")
            }
            append("\nTap to view live CCTV incident details.")
        }

        // Intent to launch MainActivity with destination incidentId
        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
            putExtra(EXTRA_INCIDENT_ID, incidentId)
            if (!cameraId.isNullOrBlank()) {
                putExtra(EXTRA_CAMERA_ID, cameraId)
            }
        }

        val notificationId = if (incidentId.isNotBlank()) {
            incidentId.hashCode()
        } else {
            notificationIdGenerator.incrementAndGet()
        }

        val pendingIntent = PendingIntent.getActivity(
            context,
            notificationId,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val builder = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setContentTitle(title)
            .setContentText(shortContent)
            .setStyle(
                NotificationCompat.BigTextStyle()
                    .setBigContentTitle(title)
                    .setSummaryText(displayCamera)
                    .bigText(expandedDetails)
            )
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)
            .setColor(Color.RED)
            .setDefaults(NotificationCompat.DEFAULT_ALL)

        try {
            val manager = NotificationManagerCompat.from(context)
            manager.notify(notificationId, builder.build())
            if (incidentId.isNotBlank()) {
                markIncidentNotified(context, incidentId)
            }
            Log.i(TAG, "Security alert notification dispatched for incident '$incidentId' (notificationId: $notificationId).")
        } catch (e: SecurityException) {
            Log.e(TAG, "SecurityException while displaying notification (missing POST_NOTIFICATIONS): ${e.message}")
        } catch (e: Exception) {
            Log.e(TAG, "Unexpected error displaying notification: ${e.message}", e)
        }
    }

    /**
     * Checks if notifications are permitted and enabled for the application.
     */
    fun areNotificationsEnabled(context: Context): Boolean {
        return NotificationManagerCompat.from(context).areNotificationsEnabled()
    }
}
