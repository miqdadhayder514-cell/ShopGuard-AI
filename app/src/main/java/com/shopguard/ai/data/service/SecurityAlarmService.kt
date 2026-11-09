package com.shopguard.ai.data.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.media.MediaPlayer
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.util.Log
import androidx.core.app.NotificationCompat
import com.shopguard.ai.MainActivity
import com.shopguard.ai.R
import com.shopguard.ai.data.alarm.AlarmState

/**
 * Foreground service that plays a looping alarm sound when a ShopGuard AI security
 * incident is detected. Runs independently of the UI — alarm continues even when
 * the app is backgrounded or the screen is off.
 *
 * Start via [startAlarm] / stop via [stopAlarm] companion helpers.
 */
class SecurityAlarmService : Service() {

    companion object {
        private const val TAG = "SecurityAlarmService"

        const val ACTION_START_ALARM = "com.shopguard.ai.action.START_ALARM"
        const val ACTION_STOP_ALARM  = "com.shopguard.ai.action.STOP_ALARM"

        const val EXTRA_INCIDENT_ID   = "extra_incident_id"
        const val EXTRA_INCIDENT_TYPE = "extra_incident_type"
        const val EXTRA_CAMERA_NAME   = "extra_camera_name"
        const val EXTRA_DETECTED_AT   = "extra_detected_at"

        const val ALARM_NOTIFICATION_ID     = 9001
        private const val ALARM_CHANNEL_ID  = "shopguard_alarm_service"
        private const val ALARM_CHANNEL_NAME = "ShopGuard Active Alarm"

        /**
         * Starts the security alarm foreground service.
         * Safe to call from FCM service or any Context.
         */
        fun startAlarm(
            context: Context,
            incidentId: String,
            incidentType: String,
            cameraName: String,
            detectedAt: String
        ) {
            val intent = Intent(context, SecurityAlarmService::class.java).apply {
                action = ACTION_START_ALARM
                putExtra(EXTRA_INCIDENT_ID,   incidentId)
                putExtra(EXTRA_INCIDENT_TYPE, incidentType)
                putExtra(EXTRA_CAMERA_NAME,   cameraName)
                putExtra(EXTRA_DETECTED_AT,   detectedAt)
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }

        /** Stops the alarm service. Safe to call from any Context or thread. */
        fun stopAlarm(context: Context) {
            val intent = Intent(context, SecurityAlarmService::class.java).apply {
                action = ACTION_STOP_ALARM
            }
            context.startService(intent)
        }
    }

    private var mediaPlayer: MediaPlayer? = null
    private var audioManager: AudioManager? = null
    private var audioFocusRequest: AudioFocusRequest? = null
    private var isForegroundStarted = false
    private var wakeLock: PowerManager.WakeLock? = null

    // ─── Lifecycle ────────────────────────────────────────────────────────────

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        audioManager = getSystemService(Context.AUDIO_SERVICE) as AudioManager
        if (!AlarmState.isAlarmActive) {
            AlarmAudioOverride.restoreIfPending(this)
        }
        createAlarmNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START_ALARM -> handleStartAlarm(intent)
            ACTION_STOP_ALARM  -> stopAlarmAndSelf()
            else -> {
                // System restarted service with null intent — stop cleanly
                Log.w(TAG, "Restarted with null/unknown action — stopping.")
                stopSelf()
            }
        }
        return START_STICKY
    }

    override fun onDestroy() {
        releaseAudio()
        AlarmState.clearAlarm()
        isForegroundStarted = false
        Log.i(TAG, "SecurityAlarmService destroyed.")
        super.onDestroy()
    }

    // ─── Alarm start ──────────────────────────────────────────────────────────

    private fun handleStartAlarm(intent: Intent) {
        val incidentId   = intent.getStringExtra(EXTRA_INCIDENT_ID)   ?: ""
        val incidentType = intent.getStringExtra(EXTRA_INCIDENT_TYPE) ?: "Security Alert"
        val cameraName   = intent.getStringExtra(EXTRA_CAMERA_NAME)   ?: "Camera"
        val detectedAt   = intent.getStringExtra(EXTRA_DETECTED_AT)   ?: ""

        // Deduplication: same incident already ringing — do nothing
        if (AlarmState.isAlarmActive &&
            incidentId.isNotBlank() &&
            AlarmState.activeIncidentId == incidentId
        ) {
            Log.i(TAG, "Alarm already active for incident '$incidentId' — ignoring duplicate.")
            return
        }

        AlarmState.setAlarmActive(incidentId, incidentType, cameraName, detectedAt)
        promoteToForeground(incidentType, cameraName)
        startAudio()
    }

    // ─── Foreground notification ──────────────────────────────────────────────

    private fun promoteToForeground(incidentType: String, cameraName: String) {
        val notification = buildAlarmNotification(incidentType, cameraName)
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                startForeground(
                    ALARM_NOTIFICATION_ID,
                    notification,
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK
                )
            } else {
                startForeground(ALARM_NOTIFICATION_ID, notification)
            }
            isForegroundStarted = true
            Log.i(TAG, "Alarm foreground started: type='$incidentType', camera='$cameraName'.")
        } catch (e: Exception) {
            Log.e(TAG, "startForeground failed: ${e.message}", e)
        }
    }

    private fun buildAlarmNotification(incidentType: String, cameraName: String): Notification {
        val displayType = incidentType.replace("_", " ")
            .split(" ").joinToString(" ") { it.replaceFirstChar { c -> c.uppercase() } }

        // Tap → open MainActivity
        val openIntent = PendingIntent.getActivity(
            this, 0,
            Intent(this, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
            },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        // STOP ALARM action in notification
        val stopIntent = PendingIntent.getService(
            this, 1,
            Intent(this, SecurityAlarmService::class.java).apply {
                action = ACTION_STOP_ALARM
            },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, ALARM_CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setContentTitle("🚨 ALARM — $displayType")
            .setContentText("$cameraName • Tap to open ShopGuard AI")
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setOngoing(true)
            .setAutoCancel(false)
            .setContentIntent(openIntent)
            .addAction(android.R.drawable.ic_delete, "STOP ALARM", stopIntent)
            .setColor(android.graphics.Color.RED)
            .build()
    }

    private fun createAlarmNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            if (manager.getNotificationChannel(ALARM_CHANNEL_ID) != null) return

            val channel = NotificationChannel(
                ALARM_CHANNEL_ID,
                ALARM_CHANNEL_NAME,
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Ongoing ShopGuard security alarm foreground service"
                setSound(null, null)      // Audio handled by MediaPlayer, not channel
                enableVibration(false)
                setShowBadge(true)
                lockscreenVisibility = NotificationCompat.VISIBILITY_PUBLIC
            }
            manager.createNotificationChannel(channel)
        }
    }

    // ─── Audio ────────────────────────────────────────────────────────────────

    private fun startAudio() {
        releaseAudio()
        AlarmAudioOverride.apply(this)

        // Acquire a PARTIAL_WAKE_LOCK so the CPU stays awake and MediaPlayer keeps
        // playing even when the screen is off / phone is locked.
        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = pm.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK,
            "ShopGuardAI::SecurityAlarmWakeLock"
        ).also { it.acquire(60 * 60 * 1000L) } // max 1 hour — released on stop

        // Request audio focus on the ALARM stream
        val alarmAttributes = AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_ALARM)
            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
            .build()

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val req = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN)
                .setAudioAttributes(alarmAttributes)
                .setAcceptsDelayedFocusGain(false)
                .build()
            audioFocusRequest = req
            audioManager?.requestAudioFocus(req)
        } else {
            @Suppress("DEPRECATION")
            audioManager?.requestAudioFocus(
                null,
                AudioManager.STREAM_ALARM,
                AudioManager.AUDIOFOCUS_GAIN
            )
        }

        try {
            val player = MediaPlayer.create(this, R.raw.security_alarm)
            if (player == null) {
                Log.e(TAG, "MediaPlayer.create returned null — R.raw.security_alarm missing?")
                return
            }
            player.apply {
                isLooping = true
                setAudioAttributes(alarmAttributes)
                setOnErrorListener { _, what, extra ->
                    Log.e(TAG, "MediaPlayer error: what=$what, extra=$extra — stopping alarm.")
                    stopAlarmAndSelf()
                    true
                }
                start()
            }
            mediaPlayer = player
            Log.i(TAG, "Alarm audio started (looping).")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to start alarm audio: ${e.message}", e)
        }
    }

    private fun releaseAudio() {
        try {
            mediaPlayer?.let { p ->
                if (p.isPlaying) p.stop()
                p.release()
            }
        } catch (_: Exception) {}
        mediaPlayer = null

        // Release WakeLock — CPU can sleep again once alarm is stopped
        try {
            if (wakeLock?.isHeld == true) wakeLock?.release()
        } catch (_: Exception) {}
        wakeLock = null

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            audioFocusRequest?.let { audioManager?.abandonAudioFocusRequest(it) }
        } else {
            @Suppress("DEPRECATION")
            audioManager?.abandonAudioFocus(null)
        }
        audioFocusRequest = null
        AlarmAudioOverride.restoreIfPending(this)
    }

    private fun stopAlarmAndSelf() {
        releaseAudio()
        AlarmState.clearAlarm()
        if (isForegroundStarted) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
                stopForeground(STOP_FOREGROUND_REMOVE)
            } else {
                @Suppress("DEPRECATION")
                stopForeground(true)
            }
            isForegroundStarted = false
        }
        stopSelf()
    }
}
