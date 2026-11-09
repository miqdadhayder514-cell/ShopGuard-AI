package com.shopguard.ai.ui.screens.settings

import android.content.Intent
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalClipboard
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.shopguard.ai.BuildConfig
import com.shopguard.ai.data.service.AlarmAudioOverride
import com.shopguard.ai.data.service.SecurityAlarmService
import com.shopguard.ai.ui.components.*
import com.shopguard.ai.ui.theme.*
import com.shopguard.ai.ui.viewmodel.MainViewModel

@Composable
fun SettingsScreen(
    viewModel: MainViewModel,
    onNavigateToDashboard: () -> Unit,
    onNavigateToCameras: () -> Unit,
    onNavigateToIncidents: () -> Unit,
    onNavigateToConnection: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    val scrollState = rememberScrollState()
    var tokenCopied by remember { mutableStateOf(false) }
    val context = LocalContext.current
    var hasDoNotDisturbAccess by remember {
        mutableStateOf(AlarmAudioOverride.hasDoNotDisturbAccess(context))
    }
    val dndSettingsLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) {
        hasDoNotDisturbAccess = AlarmAudioOverride.hasDoNotDisturbAccess(context)
    }

    // Fetch FCM token from Firebase on first composition
    LaunchedEffect(Unit) {
        viewModel.fetchFcmTokenFromFirebase()
    }

    Scaffold(
        topBar = {
            ShopGuardTopBar(
                title = "App Settings",
                isDemoMode = uiState.isDemoMode,
                onSyncClick = { viewModel.refreshAll() },
                onDeviceClick = onNavigateToConnection
            )
        },
        bottomBar = {
            ShopGuardBottomNavBar(
                currentRoute = "settings",
                onNavigate = { route ->
                    when (route) {
                        "dashboard" -> onNavigateToDashboard()
                        "cameras"   -> onNavigateToCameras()
                        "incidents" -> onNavigateToIncidents()
                    }
                }
            )
        },
        containerColor = BgPage
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .verticalScroll(scrollState)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Mode Banner
            if (uiState.isDemoMode) {
                DemoModeBanner(onConfigureClick = onNavigateToConnection)
            }

            // Connection Settings Group
            Text(
                text = "COMMUNICATION & AGENT CONNECTION",
                style = MaterialTheme.typography.labelMedium.copy(fontWeight = FontWeight.Bold),
                color = TextMid
            )

            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(14.dp),
                color = BgCard,
                shadowElevation = 2.dp,
                border = BorderStroke(1.dp, BorderLight)
            ) {
                Column(modifier = Modifier.padding(vertical = 4.dp)) {
                    SettingNavigationRow(
                        title    = "Windows Security Agent Device",
                        subtitle = "${uiState.deviceConfig.host}:${uiState.deviceConfig.port} (API Key: ${if (uiState.deviceConfig.apiKey.isNotBlank()) "Configured" else "None"})",
                        icon     = Icons.Filled.Computer,
                        onClick  = onNavigateToConnection
                    )

                    HorizontalDivider(color = BorderLight)

                    // Firebase Push Alerts Status Row
                    val clipboard = LocalClipboard.current
                    val context   = LocalContext.current

                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 16.dp, vertical = 12.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(12.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Filled.NotificationsActive,
                                contentDescription = null,
                                tint = if (uiState.isNotificationPermissionGranted) PrimaryBlue else StatusRed
                            )
                            Column(modifier = Modifier.weight(1f)) {
                                Text(
                                    text = "Firebase Cloud Messaging Alerts",
                                    style = MaterialTheme.typography.bodyLarge.copy(fontWeight = FontWeight.SemiBold),
                                    color = TextDark
                                )
                                Text(
                                    text = if (uiState.isNotificationPermissionGranted)
                                        "High-Importance Channel Active • Token: ${uiState.fcmTokenMasked}"
                                    else
                                        "Permission Denied in System Settings • Push Alerts Inactive",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = if (uiState.isNotificationPermissionGranted) TextMid else StatusRed
                                )
                            }
                        }

                        // Copy FCM token button
                        val fullFcmToken = viewModel.getFullFcmToken()
                        val hasToken     = fullFcmToken.isNotBlank()
                        OutlinedButton(
                            onClick = {
                                if (hasToken) {
                                    clipboard.nativeClipboard.setPrimaryClip(
                                        android.content.ClipData.newPlainText("FCM Token", fullFcmToken)
                                    )
                                    tokenCopied = true
                                } else {
                                    viewModel.fetchFcmTokenFromFirebase()
                                }
                            },
                            modifier = Modifier.fillMaxWidth(),
                            colors = ButtonDefaults.outlinedButtonColors(
                                contentColor = when {
                                    tokenCopied -> StatusGreen
                                    hasToken    -> PrimaryBlue
                                    else        -> TextMid
                                }
                            ),
                            border = BorderStroke(
                                1.dp,
                                when {
                                    tokenCopied -> StatusGreen
                                    hasToken    -> PrimaryBlue.copy(alpha = 0.5f)
                                    else        -> BorderLight
                                }
                            )
                        ) {
                            Icon(
                                imageVector = when {
                                    tokenCopied -> Icons.Filled.CheckCircle
                                    hasToken    -> Icons.Filled.ContentCopy
                                    else        -> Icons.Filled.Refresh
                                },
                                contentDescription = null,
                                modifier = Modifier.size(16.dp)
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            Text(
                                text = when {
                                    tokenCopied -> "Token Copied to Clipboard!"
                                    hasToken    -> "Copy FCM Token (Firebase Console Test)"
                                    else        -> "Refresh FCM Token from Firebase"
                                },
                                style = MaterialTheme.typography.labelMedium
                            )
                        }

                        // ── DEBUG ONLY: Test alarm without real intrusion ──────────────
                        if (BuildConfig.DEBUG) {
                            OutlinedButton(
                                onClick = {
                                    SecurityAlarmService.startAlarm(
                                        context      = context,
                                        incidentId   = "debug_test_${System.currentTimeMillis()}",
                                        incidentType = "TEST_INTRUSION",
                                        cameraName   = "Debug Camera",
                                        detectedAt   = java.text.SimpleDateFormat(
                                            "HH:mm:ss", java.util.Locale.getDefault()
                                        ).format(java.util.Date())
                                    )
                                    viewModel.syncAlarmState()
                                },
                                modifier = Modifier.fillMaxWidth(),
                                colors = ButtonDefaults.outlinedButtonColors(
                                    contentColor = StatusRed
                                ),
                                border = BorderStroke(1.dp, StatusRed.copy(alpha = 0.5f))
                            ) {
                                Icon(
                                    imageVector = Icons.Filled.NotificationsActive,
                                    contentDescription = null,
                                    modifier = Modifier.size(16.dp)
                                )
                                Spacer(modifier = Modifier.width(6.dp))
                                Text(
                                    text = "TEST ALARM (Debug Only)",
                                    style = MaterialTheme.typography.labelMedium
                                )
                            }
                        }
                    }

                    HorizontalDivider(color = BorderLight)

                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 16.dp, vertical = 12.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(12.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Filled.NotificationsActive,
                                contentDescription = null,
                                tint = if (hasDoNotDisturbAccess) StatusGreen else StatusRed
                            )
                            Column(modifier = Modifier.weight(1f)) {
                                Text(
                                    text = "Full-Volume Security Alarm",
                                    style = MaterialTheme.typography.bodyLarge.copy(fontWeight = FontWeight.SemiBold),
                                    color = TextDark
                                )
                                Text(
                                    text = if (hasDoNotDisturbAccess) {
                                        "Enabled: ShopGuard temporarily raises alarm volume and bypasses Do Not Disturb during alerts, then restores previous settings."
                                    } else {
                                        "ShopGuard raises alarm volume during alerts. Grant access to also bypass Do Not Disturb and silent mode."
                                    },
                                    style = MaterialTheme.typography.bodySmall,
                                    color = if (hasDoNotDisturbAccess) TextMid else StatusRed
                                )
                            }
                        }
                        OutlinedButton(
                            onClick = {
                                dndSettingsLauncher.launch(
                                    Intent(Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS)
                                )
                            },
                            modifier = Modifier.fillMaxWidth(),
                            colors = ButtonDefaults.outlinedButtonColors(
                                contentColor = if (hasDoNotDisturbAccess) StatusGreen else PrimaryBlue
                            )
                        ) {
                            Text(
                                if (hasDoNotDisturbAccess) {
                                    "Manage Do Not Disturb Access"
                                } else {
                                    "Enable Full-Volume Alarm"
                                }
                            )
                        }
                    }

                    HorizontalDivider(color = BorderLight)

                    // Demo Mode Switch
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 16.dp, vertical = 12.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(12.dp),
                            modifier = Modifier.weight(1f)
                        ) {
                            Icon(Icons.Filled.Science, contentDescription = null, tint = DemoPurple)
                            Column {
                                Text(
                                    text = "Demo Simulation Mode",
                                    style = MaterialTheme.typography.bodyLarge.copy(fontWeight = FontWeight.SemiBold),
                                    color = TextDark
                                )
                                Text(
                                    text = "Simulate CCTV cameras, alarms and arm/disarm without hardware connection",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = TextMid
                                )
                            }
                        }
                        Switch(
                            checked = uiState.isDemoMode,
                            onCheckedChange = { viewModel.setDemoMode(it) },
                            colors = SwitchDefaults.colors(
                                checkedThumbColor   = Color.White,
                                checkedTrackColor   = DemoPurple,
                                uncheckedThumbColor = TextMuted,
                                uncheckedTrackColor = BgMuted
                            )
                        )
                    }
                }
            }

            // Product & Security Architecture Group
            Text(
                text = "PRODUCT & SECURITY ARCHITECTURE",
                style = MaterialTheme.typography.labelMedium.copy(fontWeight = FontWeight.Bold),
                color = TextMid
            )

            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(14.dp),
                color = BgCard,
                shadowElevation = 2.dp,
                border = BorderStroke(1.dp, BorderLight)
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Text(
                        text = "ShopGuard AI Client",
                        style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold),
                        color = TextDark
                    )
                    Text(
                        text = "Version 2.0.0 (Phase 2 Local Agent Architecture)\n" +
                                "Engine: Ultralytics YOLO11n + ByteTrack Object Tracking\n" +
                                "Protocol: Local REST API (Loopback / Tailscale Encrypted Relay)\n" +
                                "Credential Security: Constant-Time HMAC-SHA256 Token Verification",
                        style = MaterialTheme.typography.bodySmall,
                        color = TextMid
                    )
                }
            }

            Spacer(modifier = Modifier.height(16.dp))
        }
    }
}

@Composable
private fun SettingNavigationRow(
    title: String,
    subtitle: String,
    icon: ImageVector,
    onClick: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 14.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            modifier = Modifier.weight(1f)
        ) {
            Icon(imageVector = icon, contentDescription = null, tint = PrimaryBlue)
            Column {
                Text(
                    text = title,
                    style = MaterialTheme.typography.bodyLarge.copy(fontWeight = FontWeight.SemiBold),
                    color = TextDark
                )
                Text(
                    text = subtitle,
                    style = MaterialTheme.typography.bodySmall,
                    color = TextMid
                )
            }
        }
        Icon(
            imageVector = Icons.Filled.ChevronRight,
            contentDescription = null,
            tint = TextMid
        )
    }
}
