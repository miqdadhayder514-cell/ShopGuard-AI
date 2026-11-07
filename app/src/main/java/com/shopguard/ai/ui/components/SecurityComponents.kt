package com.shopguard.ai.ui.components

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.shopguard.ai.data.model.SecurityState
import com.shopguard.ai.ui.theme.*

@Composable
fun SecurityStatusBadge(
    state: SecurityState,
    modifier: Modifier = Modifier
) {
    val (bgColor, textColor, icon) = when (state) {
        SecurityState.ARMED    -> Triple(StatusGreenLight,  StatusGreen,  Icons.Filled.Shield)
        SecurityState.DISARMED -> Triple(StatusAmberLight,  StatusAmber,  Icons.Filled.LockOpen)
        SecurityState.ARMING   -> Triple(StatusAmberLight,  StatusAmber,  Icons.Filled.HourglassEmpty)
        SecurityState.PARTIAL  -> Triple(StatusOrangeLight, StatusOrange, Icons.Filled.Warning)
        SecurityState.OFFLINE  -> Triple(StatusSlateLight,  StatusSlate,  Icons.Filled.SignalCellularConnectedNoInternet0Bar)
    }

    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(16.dp),
        color = bgColor,
        border = BorderStroke(1.dp, textColor.copy(alpha = 0.4f))
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            Box(
                modifier = Modifier
                    .size(8.dp)
                    .clip(CircleShape)
                    .background(textColor)
            )
            Text(
                text = state.displayName.uppercase(),
                style = MaterialTheme.typography.labelSmall.copy(fontWeight = FontWeight.Bold),
                color = textColor,
                letterSpacing = 1.sp
            )
        }
    }
}

@Composable
fun DemoModeBanner(
    onConfigureClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        color = DemoBadgeBackground,
        border = BorderStroke(1.dp, DemoPurple.copy(alpha = 0.5f))
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 14.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Row(
                modifier = Modifier.weight(1f),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Icon(
                    imageVector = Icons.Filled.Info,
                    contentDescription = "Demo Mode",
                    tint = DemoPurple,
                    modifier = Modifier.size(20.dp)
                )
                Column {
                    Text(
                        text = "DEMO SIMULATION MODE",
                        style = MaterialTheme.typography.labelMedium.copy(fontWeight = FontWeight.Bold),
                        color = DemoPurple
                    )
                    Text(
                        text = "Simulated mode active. Arm/Disarm here does NOT affect your Windows agent.",
                        style = MaterialTheme.typography.bodySmall,
                        color = TextMid
                    )
                }
            }
            TextButton(
                onClick = onConfigureClick,
                colors = ButtonDefaults.textButtonColors(contentColor = PrimaryBlue)
            ) {
                Text("Connect Agent", style = MaterialTheme.typography.labelMedium.copy(fontWeight = FontWeight.Bold))
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ShopGuardTopBar(
    title: String,
    isDemoMode: Boolean,
    onSyncClick: () -> Unit,
    onDeviceClick: () -> Unit
) {
    TopAppBar(
        title = {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Icon(
                    imageVector = Icons.Filled.Security,
                    contentDescription = "ShopGuard Logo",
                    tint = PrimaryBlue,
                    modifier = Modifier.size(26.dp)
                )
                Column {
                    Text(
                        text = title,
                        style = MaterialTheme.typography.titleLarge.copy(fontWeight = FontWeight.Bold),
                        color = TextDark
                    )
                    if (isDemoMode) {
                        Text(
                            text = "DEMO MODE",
                            style = MaterialTheme.typography.labelSmall.copy(fontWeight = FontWeight.SemiBold),
                            color = DemoPurple
                        )
                    }
                }
            }
        },
        actions = {
            IconButton(onClick = onSyncClick) {
                Icon(
                    imageVector = Icons.Filled.Refresh,
                    contentDescription = "Refresh Telemetry",
                    tint = PrimaryBlue
                )
            }
            IconButton(onClick = onDeviceClick) {
                Icon(
                    imageVector = Icons.Filled.Dns,
                    contentDescription = "Device Settings",
                    tint = TextMid
                )
            }
        },
        colors = TopAppBarDefaults.topAppBarColors(
            containerColor = BgCard,
            titleContentColor = TextDark
        )
    )
}

@Composable
fun ShopGuardBottomNavBar(
    currentRoute: String,
    onNavigate: (String) -> Unit
) {
    NavigationBar(
        containerColor = BgCard,
        contentColor = TextDark,
        tonalElevation = 0.dp
    ) {
        val items = listOf(
            Triple("dashboard", "Dashboard",  Icons.Filled.Dashboard),
            Triple("cameras",   "Cameras",    Icons.Filled.Videocam),
            Triple("incidents", "Incidents",  Icons.Filled.NotificationsActive),
            Triple("settings",  "Settings",   Icons.Filled.Settings)
        )

        items.forEach { (route, label, icon) ->
            val isSelected = currentRoute == route
            NavigationBarItem(
                selected = isSelected,
                onClick = { onNavigate(route) },
                icon = {
                    Icon(
                        imageVector = icon,
                        contentDescription = label,
                        modifier = Modifier.size(22.dp)
                    )
                },
                label = {
                    Text(
                        text = label,
                        style = MaterialTheme.typography.labelSmall.copy(
                            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal
                        )
                    )
                },
                colors = NavigationBarItemDefaults.colors(
                    selectedIconColor   = PrimaryBlue,
                    selectedTextColor   = PrimaryBlue,
                    indicatorColor      = PrimaryBlueLight,
                    unselectedIconColor = TextMid,
                    unselectedTextColor = TextMid
                )
            )
        }
    }
}

@Composable
fun StatCard(
    title: String,
    value: String,
    subtitle: String,
    icon: ImageVector,
    iconColor: Color,
    modifier: Modifier = Modifier
) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(14.dp),
        color = BgCard,
        shadowElevation = 2.dp,
        border = BorderStroke(1.dp, BorderLight)
    ) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = title,
                    style = MaterialTheme.typography.labelMedium,
                    color = TextMid
                )
                Box(
                    modifier = Modifier
                        .size(32.dp)
                        .clip(RoundedCornerShape(8.dp))
                        .background(iconColor.copy(alpha = 0.12f)),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        imageVector = icon,
                        contentDescription = title,
                        tint = iconColor,
                        modifier = Modifier.size(18.dp)
                    )
                }
            }
            Text(
                text = value,
                style = MaterialTheme.typography.headlineSmall.copy(fontWeight = FontWeight.Bold),
                color = TextDark
            )
            Text(
                text = subtitle,
                style = MaterialTheme.typography.bodySmall,
                color = TextMuted
            )
        }
    }
}

@Composable
fun ArmConfirmationDialog(
    canArm: Boolean = true,
    rejectionReasons: List<String> = emptyList(),
    onConfirm: (reason: String) -> Unit,
    onDismiss: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Icon(
                    imageVector = Icons.Filled.Security,
                    contentDescription = null,
                    tint = StatusGreen
                )
                Text("Arm Security System", style = MaterialTheme.typography.titleLarge, color = TextDark)
            }
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                if (!canArm && rejectionReasons.isNotEmpty()) {
                    Surface(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(8.dp),
                        color = StatusRedLight,
                        border = BorderStroke(1.dp, StatusRed)
                    ) {
                        Column(modifier = Modifier.padding(10.dp)) {
                            Text(
                                text = "⚠️ Prerequisites Warning",
                                style = MaterialTheme.typography.labelSmall.copy(fontWeight = FontWeight.Bold),
                                color = StatusRed
                            )
                            rejectionReasons.forEach { r ->
                                Text("• $r", style = MaterialTheme.typography.bodySmall, color = TextDark)
                            }
                        }
                    }
                }

                Text(
                    text = "Are you sure you want to ARM the security system?",
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextDark
                )
                Text(
                    text = "All protected restricted zones will actively detect people. Any intrusion will trigger automated incident recording and save audit clips.",
                    style = MaterialTheme.typography.bodySmall,
                    color = TextMid
                )
            }
        },
        confirmButton = {
            Button(
                onClick = { onConfirm("Armed via mobile application confirmation") },
                colors = ButtonDefaults.buttonColors(
                    containerColor = StatusGreen,
                    contentColor   = Color.White,
                    disabledContainerColor = BgMuted,
                    disabledContentColor   = TextMuted
                )
            ) {
                Text("Arm System", fontWeight = FontWeight.Bold)
            }
        },
        dismissButton = {
            OutlinedButton(
                onClick = onDismiss,
                border = BorderStroke(1.dp, BorderLight)
            ) {
                Text("Cancel", color = TextMid)
            }
        },
        containerColor = BgCard,
        titleContentColor = TextDark,
        textContentColor  = TextMid
    )
}

@Composable
fun DisarmConfirmationDialog(
    onConfirm: (reason: String) -> Unit,
    onDismiss: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Icon(
                    imageVector = Icons.Filled.LockOpen,
                    contentDescription = null,
                    tint = StatusAmber
                )
                Text("Disarm Security System", style = MaterialTheme.typography.titleLarge, color = TextDark)
            }
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(
                    text = "Are you sure you want to DISARM the security system?",
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextDark
                )
                Text(
                    text = "Camera streams and health monitoring will remain active, but intrusion events and automatic incident recordings will be paused.",
                    style = MaterialTheme.typography.bodySmall,
                    color = TextMid
                )
            }
        },
        confirmButton = {
            Button(
                onClick = { onConfirm("Disarmed via mobile application confirmation") },
                colors = ButtonDefaults.buttonColors(
                    containerColor = StatusAmber,
                    contentColor   = Color.White,
                    disabledContainerColor = BgMuted,
                    disabledContentColor   = TextMuted
                )
            ) {
                Text("Disarm System", fontWeight = FontWeight.Bold)
            }
        },
        dismissButton = {
            OutlinedButton(
                onClick = onDismiss,
                border = BorderStroke(1.dp, BorderLight)
            ) {
                Text("Cancel", color = TextMid)
            }
        },
        containerColor = BgCard,
        titleContentColor = TextDark,
        textContentColor  = TextMid
    )
}

@Composable
fun DeleteCameraConfirmationDialog(
    cameraName: String,
    onConfirm: () -> Unit,
    onDismiss: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        icon = {
            Icon(
                imageVector = Icons.Filled.DeleteForever,
                contentDescription = null,
                tint = StatusRed,
                modifier = Modifier.size(32.dp)
            )
        },
        title = {
            Text(
                text = "Remove Camera?",
                style = MaterialTheme.typography.titleLarge.copy(fontWeight = FontWeight.Bold),
                color = TextDark
            )
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    text = "Are you sure you want to remove '$cameraName' from monitoring?",
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextDark
                )
                Text(
                    text = "The Windows AI engine will disconnect the stream and cease intrusion detection on this channel.",
                    style = MaterialTheme.typography.bodySmall,
                    color = TextMid
                )
            }
        },
        confirmButton = {
            Button(
                onClick = onConfirm,
                colors = ButtonDefaults.buttonColors(
                    containerColor = StatusRed,
                    contentColor   = Color.White
                )
            ) {
                Text("Delete Camera", fontWeight = FontWeight.Bold)
            }
        },
        dismissButton = {
            OutlinedButton(
                onClick = onDismiss,
                border = BorderStroke(1.dp, BorderLight)
            ) {
                Text("Cancel", color = TextMid)
            }
        },
        containerColor = BgCard,
        titleContentColor = TextDark,
        textContentColor  = TextMid
    )
}
