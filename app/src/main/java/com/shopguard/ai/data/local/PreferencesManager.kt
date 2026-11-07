package com.shopguard.ai.data.local

import android.content.Context
import android.content.SharedPreferences
import com.shopguard.ai.data.model.DeviceConfig

class PreferencesManager(context: Context) {
    private val prefs: SharedPreferences =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    companion object {
        private const val PREFS_NAME = "shopguard_security_prefs"
        private const val KEY_HOST = "device_host"
        private const val KEY_PORT = "device_port"
        private const val KEY_API_KEY = "device_api_key"
        private const val KEY_DEMO_MODE = "is_demo_mode"
        private const val KEY_USE_HTTPS = "device_use_https"
        private const val KEY_NOTIFICATIONS = "notifications_enabled"
        private const val KEY_FCM_TOKEN = "fcm_registration_token"
        private const val KEY_NOTIFIED_INCIDENTS = "notified_incident_ids"

        // 10.0.2.2 is Android emulator's loopback alias for the host Windows PC 127.0.0.1
        const val DEFAULT_HOST = "10.0.2.2"
        const val DEFAULT_PORT = 8000
        private const val MAX_TRACKED_INCIDENTS = 100
    }

    var host: String
        get() = prefs.getString(KEY_HOST, DEFAULT_HOST) ?: DEFAULT_HOST
        set(value) = prefs.edit().putString(KEY_HOST, value.trim()).apply()

    var port: Int
        get() = prefs.getInt(KEY_PORT, DEFAULT_PORT)
        set(value) = prefs.edit().putInt(KEY_PORT, value).apply()

    var apiKey: String
        get() = prefs.getString(KEY_API_KEY, "") ?: ""
        set(value) = prefs.edit().putString(KEY_API_KEY, value.trim()).apply()

    var isDemoMode: Boolean
        get() = prefs.getBoolean(KEY_DEMO_MODE, true)
        set(value) = prefs.edit().putBoolean(KEY_DEMO_MODE, value).apply()

    var useHttps: Boolean
        get() = prefs.getBoolean(KEY_USE_HTTPS, host.contains(".ts.net", ignoreCase = true) || port == 443)
        set(value) = prefs.edit().putBoolean(KEY_USE_HTTPS, value).apply()

    var isNotificationsEnabled: Boolean
        get() = prefs.getBoolean(KEY_NOTIFICATIONS, true)
        set(value) = prefs.edit().putBoolean(KEY_NOTIFICATIONS, value).apply()

    var fcmToken: String
        get() = prefs.getString(KEY_FCM_TOKEN, "") ?: ""
        set(value) = prefs.edit().putString(KEY_FCM_TOKEN, value.trim()).apply()

    /**
     * Returns a privacy-safe masked representation of the FCM token (e.g. for debug/status UI).
     * Never exposes the full token in logs or production UI.
     */
    fun getMaskedFcmToken(): String {
        val token = fcmToken
        return when {
            token.isBlank() -> "Not Registered"
            token.length <= 12 -> "fcm_***"
            else -> "${token.take(6)}...${token.takeLast(6)}"
        }
    }

    /**
     * Checks whether an incident ID has already been notified to prevent duplicate alerts.
     */
    fun isIncidentAlreadyNotified(incidentId: String): Boolean {
        if (incidentId.isBlank()) return false
        val set = prefs.getStringSet(KEY_NOTIFIED_INCIDENTS, emptySet()) ?: emptySet()
        return set.contains(incidentId)
    }

    /**
     * Records an incident ID as notified, pruning older entries if necessary.
     */
    @Synchronized
    fun recordNotifiedIncident(incidentId: String) {
        if (incidentId.isBlank()) return
        val currentSet = prefs.getStringSet(KEY_NOTIFIED_INCIDENTS, emptySet())?.toMutableSet() ?: mutableSetOf()
        currentSet.add(incidentId)
        if (currentSet.size > MAX_TRACKED_INCIDENTS) {
            // Drop oldest items to prevent unbounded preference growth
            val trimmed = currentSet.toList().takeLast(MAX_TRACKED_INCIDENTS).toSet()
            prefs.edit().putStringSet(KEY_NOTIFIED_INCIDENTS, trimmed).apply()
        } else {
            prefs.edit().putStringSet(KEY_NOTIFIED_INCIDENTS, currentSet).apply()
        }
    }

    fun getDeviceConfig(): DeviceConfig {
        return DeviceConfig(
            host = host,
            port = port,
            apiKey = apiKey,
            isDemoMode = isDemoMode,
            useHttps = useHttps
        )
    }

    fun saveDeviceConfig(config: DeviceConfig) {
        host = config.host
        port = config.port
        apiKey = config.apiKey
        isDemoMode = config.isDemoMode
        useHttps = config.useHttps
    }
}
