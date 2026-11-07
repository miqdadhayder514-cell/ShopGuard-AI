package com.shopguard.ai.ui.screens.dashboard

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.shopguard.ai.data.model.SecurityState
import com.shopguard.ai.ui.components.*
import com.shopguard.ai.ui.theme.*
import com.shopguard.ai.ui.viewmodel.MainViewModel

@Composable
fun DashboardScreen(
    viewModel: MainViewModel,
    onNavigateToCameras: () -> Unit,
    onNavigateToIncidents: () -> Unit,
    onNavigateToIncidentDetail: (String) -> Unit,
    onNavigateToConnection: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    var showArmDialog by remember { mutableStateOf(false) }
    var showDisarmDialog by remember { mutableStateOf(false) }

    val scrollState = rememberScrollState()

    // Confirmation Dialogs
    if (showArmDialog) {
        ArmConfirmationDialog(
            canArm = uiState.securityStateDetails.canArm,
            rejectionReasons = uiState.securityStateDetails.rejectionReasons,
            onConfirm = { reason ->
                showArmDialog = false
                viewModel.armSecurity(reason)
            },
            onDismiss = { showArmDialog = false }
        )
    }

    if (showDisarmDialog) {
        DisarmConfirmationDialog(
            onConfirm = { reason ->
                showDisarmDialog = false
                viewModel.disarmSecurity(reason)
            },
            onDismiss = { showDisarmDialog = false }
        )
    }

    Scaffold(
        topBar = {
            ShopGuardTopBar(
                title = "Security Dashboard",
                isDemoMode = uiState.isDemoMode,
                onSyncClick = { viewModel.refreshAll() },
                onDeviceClick = onNavigateToConnection
            )
        },
        bottomBar = {
            ShopGuardBottomNavBar(
                currentRoute = "dashboard",
                onNavigate = { route ->
                    when (route) {
                        "cameras"   -> onNavigateToCameras()
                        "incidents" -> onNavigateToIncidents()
                        "settings"  -> onNavigateToConnection()
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
            // Demo Mode Notice Banner
            if (uiState.isDemoMode) {
                DemoModeBanner(onConfigureClick = onNavigateToConnection)
            }

            // Error banner
            if (uiState.errorMessage != null) {
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(10.dp),
                    color = StatusRedLight,
                    border = BorderStroke(1.dp, StatusRed.copy(alpha = 0.5f))
                ) {
                    Row(
                        modifier = Modifier.padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(
                            text = uiState.errorMessage ?: "",
                            style = MaterialTheme.typography.bodySmall,
                            color = StatusRed,
                            modifier = Modifier.weight(1f)
                        )
                        IconButton(onClick = { viewModel.clearMessages() }) {
                            Icon(Icons.Filled.Close, contentDescription = "Dismiss", tint = StatusRed)
                        }
                    }
                }
            }

            // Success banner
            if (uiState.successMessage != null) {
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(10.dp),
                    color = StatusGreenLight,
                    border = BorderStroke(1.dp, StatusGreen.copy(alpha = 0.5f))
                ) {
                    Row(
                        modifier = Modifier.padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(
                            text = uiState.successMessage ?: "",
                            style = MaterialTheme.typography.bodySmall,
                            color = StatusGreen,
                            modifier = Modifier.weight(1f)
                        )
                        IconButton(onClick = { viewModel.clearMessages() }) {
                            Icon(Icons.Filled.Close, contentDescription = "Dismiss", tint = StatusGreen)
                        }
                    }
                }
            }

            // PROMINENT SECURITY STATUS HERO CARD
            val isArmed = (uiState.securityState == SecurityState.ARMED)
            val heroBgColor   = if (isArmed) StatusGreenLight  else StatusAmberLight
            val heroBorder    = if (isArmed) StatusGreen        else StatusAmber
            val heroIconInner = if (isArmed) StatusGreenLight.copy(alpha = 0.7f) else StatusAmberLight.copy(alpha = 0.7f)
            val heroIcon      = if (isArmed) Icons.Filled.Shield else Icons.Filled.LockOpen

            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(20.dp),
                color = BgCard,
                shadowElevation = 3.dp,
                border = BorderStroke(1.5.dp, heroBorder.copy(alpha = 0.5f))
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(24.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    // Shield icon
                    Box(
                        modifier = Modifier
                            .size(110.dp)
                            .clip(CircleShape)
                            .background(heroBgColor),
                        contentAlignment = Alignment.Center
                    ) {
                        Box(
                            modifier = Modifier
                                .size(80.dp)
                                .clip(CircleShape)
                                .background(heroIconInner),
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(
                                imageVector = heroIcon,
                                contentDescription = "Security State",
                                tint = heroBorder,
                                modifier = Modifier.size(44.dp)
                            )
                        }
                    }

                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(
                            text = if (isArmed) "SYSTEM ARMED" else "SYSTEM DISARMED",
                            style = MaterialTheme.typography.headlineMedium.copy(fontWeight = FontWeight.ExtraBold),
                            color = if (isArmed) StatusGreen else StatusAmber,
                            letterSpacing = 1.sp
                        )
                        Text(
                            text = if (isArmed)
                                "Restricted zones active • Automated intrusion recording ON"
                            else
                                "CCTV streams live • Automated alarms stand-by",
                            style = MaterialTheme.typography.bodySmall,
                            color = TextMid
                        )
                    }

                    // Arm / Disarm Action Buttons Row
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        Button(
                            onClick = { showArmDialog = true },
                            enabled = !isArmed && !uiState.isArmingDisarming,
                            modifier = Modifier
                                .weight(1f)
                                .height(48.dp),
                            shape = RoundedCornerShape(12.dp),
                            colors = ButtonDefaults.buttonColors(
                                containerColor = StatusGreen,
                                contentColor   = Color.White,
                                disabledContainerColor = BgMuted,
                                disabledContentColor   = TextMuted
                            )
                        ) {
                            Icon(Icons.Filled.Security, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(Modifier.width(8.dp))
                            Text("Arm Security", fontWeight = FontWeight.Bold)
                        }

                        Button(
                            onClick = { showDisarmDialog = true },
                            enabled = isArmed && !uiState.isArmingDisarming,
                            modifier = Modifier
                                .weight(1f)
                                .height(48.dp),
                            shape = RoundedCornerShape(12.dp),
                            colors = ButtonDefaults.buttonColors(
                                containerColor = StatusAmber,
                                contentColor   = Color.White,
                                disabledContainerColor = BgMuted,
                                disabledContentColor   = TextMuted
                            )
                        ) {
                            Icon(Icons.Filled.LockOpen, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(Modifier.width(8.dp))
                            Text("Disarm Security", fontWeight = FontWeight.Bold)
                        }
                    }
                }
            }

            // Quick Stats Grid
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                StatCard(
                    title    = "Cameras",
                    value    = "${uiState.status.camerasConnected}/${uiState.status.camerasTotal}",
                    subtitle = "Online feeds",
                    icon     = Icons.Filled.Videocam,
                    iconColor = PrimaryBlue,
                    modifier  = Modifier.weight(1f)
                )
                StatCard(
                    title    = "Incidents",
                    value    = "${uiState.status.activeIncidentsToday}",
                    subtitle = "Detected today",
                    icon     = Icons.Filled.NotificationsActive,
                    iconColor = StatusRed,
                    modifier  = Modifier.weight(1f)
                )
                StatCard(
                    title    = "Service",
                    value    = uiState.status.serviceStatus.take(7),
                    subtitle = "Agent status",
                    icon     = Icons.Filled.CheckCircle,
                    iconColor = StatusGreen,
                    modifier  = Modifier.weight(1f)
                )
            }

            // Recent Incident Activity Section
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "Recent Incident Alerts",
                    style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold),
                    color = TextDark
                )
                TextButton(onClick = onNavigateToIncidents) {
                    Text("View All (${uiState.incidents.size})", color = PrimaryBlue)
                }
            }

            if (uiState.incidents.isEmpty()) {
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp),
                    color = BgCard,
                    shadowElevation = 1.dp,
                    border = BorderStroke(1.dp, BorderLight)
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(24.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Filled.CheckCircleOutline,
                            contentDescription = null,
                            tint = StatusGreen,
                            modifier = Modifier.size(36.dp)
                        )
                        Text(
                            text = "No Intrusions Detected",
                            style = MaterialTheme.typography.titleMedium,
                            color = TextDark
                        )
                        Text(
                            text = "All restricted zones are clear and secure.",
                            style = MaterialTheme.typography.bodySmall,
                            color = TextMid
                        )
                    }
                }
            } else {
                // Show up to 3 most recent incidents
                uiState.incidents.take(3).forEach { incident ->
                    IncidentCard(
                        incident = incident,
                        onClick  = { onNavigateToIncidentDetail(incident.incidentId) }
                    )
                }
            }
        }
    }
}
