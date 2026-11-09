package com.shopguard.ai

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.navigation.compose.rememberNavController
import com.google.firebase.messaging.FirebaseMessaging
import com.shopguard.ai.data.alarm.AlarmState
import com.shopguard.ai.data.local.PreferencesManager
import com.shopguard.ai.data.notification.NotificationHelper
import com.shopguard.ai.data.repository.ShopGuardRepository
import com.shopguard.ai.data.service.AlarmAudioOverride
import com.shopguard.ai.data.service.SecurityAlarmService
import com.shopguard.ai.ui.components.NotificationPermissionDialog
import com.shopguard.ai.ui.navigation.ShopGuardNavGraph
import com.shopguard.ai.ui.theme.ShopGuardTheme
import com.shopguard.ai.ui.viewmodel.MainViewModel

class MainActivity : ComponentActivity() {

    companion object {
        private const val TAG = "MainActivity"
    }

    private val viewModel: MainViewModel by viewModels {
        object : ViewModelProvider.Factory {
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                val prefs = PreferencesManager(applicationContext)
                val repository = ShopGuardRepository(prefs)
                @Suppress("UNCHECKED_CAST")
                return MainViewModel(repository) as T
            }
        }
    }

    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted: Boolean ->
        viewModel.setNotificationPermissionState(isGranted)
        if (isGranted) {
            Log.i(TAG, "Notification permission POST_NOTIFICATIONS granted by user.")
        } else {
            Log.w(TAG, "Notification permission POST_NOTIFICATIONS denied by user.")
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (!AlarmState.isAlarmActive) {
            AlarmAudioOverride.restoreIfPending(applicationContext)
        }

        // 1. Initialize high-importance security notification channel
        NotificationHelper.createNotificationChannel(applicationContext)

        // 2. Fetch & cache current FCM registration token asynchronously
        fetchFcmToken()

        // 3. Check & request notification permission for Android 13+ (API 33+)
        checkNotificationPermission()

        // 4. Handle incoming intent (e.g. from notification click)
        handleNotificationIntent(intent)

        setContent {
            ShopGuardTheme {
                val uiState by viewModel.uiState.collectAsState()
                val navController = rememberNavController()

                // Rationale dialog for notification permission
                if (uiState.showNotificationRationaleDialog) {
                    NotificationPermissionDialog(
                        onConfirm = {
                            viewModel.setShowNotificationRationaleDialog(false)
                            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                                requestPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                            }
                        },
                        onDismiss = {
                            viewModel.setShowNotificationRationaleDialog(false)
                        }
                    )
                }

                ShopGuardNavGraph(
                    navController = navController,
                    viewModel = viewModel
                )
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleNotificationIntent(intent)
    }

    override fun onResume() {
        super.onResume()
        if (!AlarmState.isAlarmActive) {
            AlarmAudioOverride.restoreIfPending(applicationContext)
        }
        // Sync alarm state so UI reflects alarms that started while the app was backgrounded
        viewModel.syncAlarmState()
    }

    private fun handleNotificationIntent(intent: Intent?) {
        if (intent == null) return
        val incidentId = intent.getStringExtra(NotificationHelper.EXTRA_INCIDENT_ID)
        if (!incidentId.isNullOrBlank()) {
            Log.i(TAG, "Notification click detected with incidentId='$incidentId'. Routing to incident screen.")
            viewModel.setPendingIncidentDetailId(incidentId)

            // Fallback: if alarm wasn't started by FCM service (e.g. app was backgrounded
            // and an older build delivered the notification without calling onMessageReceived),
            // start it now from the notification tap. No-op if alarm already active for this ID.
            val incidentType = intent.getStringExtra("event_type") ?: "Security Alert"
            val cameraName   = intent.getStringExtra("camera_name") ?: ""
            val detectedAt   = intent.getStringExtra("event_timestamp") ?: ""
            if (!AlarmState.isAlarmActive) {
                SecurityAlarmService.startAlarm(
                    context      = this,
                    incidentId   = incidentId,
                    incidentType = incidentType,
                    cameraName   = cameraName,
                    detectedAt   = detectedAt
                )
            }
        }
    }

    private fun checkNotificationPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            val isGranted = ContextCompat.checkSelfPermission(
                this,
                Manifest.permission.POST_NOTIFICATIONS
            ) == PackageManager.PERMISSION_GRANTED

            viewModel.setNotificationPermissionState(isGranted)

            if (!isGranted) {
                // Show clear rationale dialog explaining importance of intrusion alerts
                viewModel.setShowNotificationRationaleDialog(true)
            }
        } else {
            viewModel.setNotificationPermissionState(true)
        }
    }

    private fun fetchFcmToken() {
        try {
            FirebaseMessaging.getInstance().token.addOnCompleteListener { task ->
                if (task.isSuccessful && task.result != null) {
                    val token = task.result
                    viewModel.updateFcmToken(token)
                    val masked = if (token.length > 12) "${token.take(6)}...${token.takeLast(6)}" else "fcm_***"
                    Log.i(TAG, "FCM registration token successfully initialized (preview: $masked).")
                } else {
                    Log.w(TAG, "Fetching FCM registration token failed: ${task.exception?.message}")
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Exception accessing FirebaseMessaging instance: ${e.message}")
        }
    }
}
