package com.shopguard.ai.data.service

import android.app.NotificationManager
import android.content.Context
import android.media.AudioManager
import android.os.Build
import android.util.Log

/**
 * Temporarily raises the alarm stream and allows all interruptions while a
 * security alarm is active. Original values are persisted so a service restart
 * can recover and restore them.
 */
object AlarmAudioOverride {

    private const val TAG = "AlarmAudioOverride"
    private const val PREFS_NAME = "shopguard_alarm_audio_override"
    private const val KEY_OVERRIDE_ACTIVE = "override_active"
    private const val KEY_PREVIOUS_ALARM_VOLUME = "previous_alarm_volume"
    private const val KEY_FORCED_ALARM_VOLUME = "forced_alarm_volume"
    private const val KEY_PREVIOUS_INTERRUPTION_FILTER = "previous_interruption_filter"
    private const val NO_SAVED_FILTER = -1

    fun hasDoNotDisturbAccess(context: Context): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) return true
        return try {
            val manager =
                context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            manager.isNotificationPolicyAccessGranted
        } catch (e: Exception) {
            Log.e(TAG, "Could not check Do Not Disturb access: ${e.message}", e)
            false
        }
    }

    fun restoreIfPending(context: Context): Boolean {
        return try {
            restorePendingOverride(context)
        } catch (e: Exception) {
            Log.e(TAG, "Could not restore pending alarm audio settings: ${e.message}", e)
            false
        }
    }

    private fun restorePendingOverride(context: Context): Boolean {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        if (!prefs.getBoolean(KEY_OVERRIDE_ACTIVE, false)) return true

        var restored = true
        val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        val previousVolume = prefs.getInt(KEY_PREVIOUS_ALARM_VOLUME, -1)
        val forcedVolume = prefs.getInt(KEY_FORCED_ALARM_VOLUME, -1)

        if (previousVolume >= 0 && forcedVolume >= 0) {
            try {
                if (audioManager.getStreamVolume(AudioManager.STREAM_ALARM) == forcedVolume) {
                    audioManager.setStreamVolume(AudioManager.STREAM_ALARM, previousVolume, 0)
                    Log.i(TAG, "Restored the alarm stream volume saved before the security alarm.")
                } else {
                    Log.i(TAG, "Alarm stream volume changed during the alert; preserving the user's new setting.")
                }
            } catch (e: Exception) {
                restored = false
                Log.e(TAG, "Could not restore the previous alarm stream volume: ${e.message}", e)
            }
        }

        val previousFilter = prefs.getInt(KEY_PREVIOUS_INTERRUPTION_FILTER, NO_SAVED_FILTER)
        if (previousFilter != NO_SAVED_FILTER) {
            val notificationManager =
                context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            if (!hasDoNotDisturbAccess(context)) {
                restored = false
                Log.w(TAG, "Cannot restore the previous Do Not Disturb filter until policy access is granted.")
            } else {
                try {
                    if (notificationManager.currentInterruptionFilter ==
                        NotificationManager.INTERRUPTION_FILTER_ALL
                    ) {
                        notificationManager.setInterruptionFilter(previousFilter)
                        Log.i(TAG, "Restored the interruption filter saved before the security alarm.")
                    } else {
                        Log.i(TAG, "Do Not Disturb changed during the alert; preserving the user's new setting.")
                    }
                } catch (e: Exception) {
                    restored = false
                    Log.e(TAG, "Could not restore the previous Do Not Disturb filter: ${e.message}", e)
                }
            }
        }

        if (restored) {
            val cleared = prefs.edit().clear().commit()
            if (!cleared) {
                Log.e(TAG, "Restored audio settings but could not clear the recovery record.")
            }
            return cleared
        } else {
            Log.w(TAG, "Audio override restoration is pending and will be retried later.")
            return false
        }
    }

    fun apply(context: Context) {
        try {
            applyOverride(context)
        } catch (e: Exception) {
            Log.e(TAG, "Could not apply temporary alarm audio settings: ${e.message}", e)
        }
    }

    private fun applyOverride(context: Context) {
        if (!restoreIfPending(context)) {
            Log.e(TAG, "Skipping new audio overrides because a previous override is not fully restored.")
            return
        }

        val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        val notificationManager =
            context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val previousVolume = audioManager.getStreamVolume(AudioManager.STREAM_ALARM)
        val forcedVolume = audioManager.getStreamMaxVolume(AudioManager.STREAM_ALARM)
        val previousFilter = if (hasDoNotDisturbAccess(context)) {
            try {
                notificationManager.currentInterruptionFilter
            } catch (e: Exception) {
                Log.e(TAG, "Could not read the current Do Not Disturb filter: ${e.message}", e)
                NO_SAVED_FILTER
            }
        } else {
            Log.w(TAG, "Do Not Disturb access is not granted; the alarm will use the current DND filter.")
            NO_SAVED_FILTER
        }

        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val saved = prefs.edit()
            .putBoolean(KEY_OVERRIDE_ACTIVE, true)
            .putInt(KEY_PREVIOUS_ALARM_VOLUME, previousVolume)
            .putInt(KEY_FORCED_ALARM_VOLUME, forcedVolume)
            .putInt(KEY_PREVIOUS_INTERRUPTION_FILTER, previousFilter)
            .commit()
        if (!saved) {
            Log.e(TAG, "Could not persist original audio settings; leaving system settings unchanged.")
            return
        }

        try {
            audioManager.setStreamVolume(AudioManager.STREAM_ALARM, forcedVolume, 0)
            Log.i(TAG, "Temporarily raised alarm stream volume to its maximum.")
        } catch (e: Exception) {
            Log.e(TAG, "Could not raise alarm stream volume: ${e.message}", e)
        }

        if (previousFilter != NO_SAVED_FILTER) {
            try {
                notificationManager.setInterruptionFilter(NotificationManager.INTERRUPTION_FILTER_ALL)
                Log.i(TAG, "Temporarily allowed all interruptions for the security alarm.")
            } catch (e: Exception) {
                Log.e(TAG, "Could not temporarily override Do Not Disturb: ${e.message}", e)
            }
        }
    }
}
