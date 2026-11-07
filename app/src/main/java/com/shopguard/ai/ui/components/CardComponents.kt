package com.shopguard.ai.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.shopguard.ai.data.model.CameraInfo
import com.shopguard.ai.data.model.IncidentSummary
import com.shopguard.ai.ui.theme.*

@Composable
fun CameraCard(
    camera: CameraInfo,
    onEditClick: (() -> Unit)? = null,
    onDeleteClick: (() -> Unit)? = null,
    onTestClick: (() -> Unit)? = null,
    modifier: Modifier = Modifier
) {
    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        color = BgCard,
        shadowElevation = 2.dp,
        border = BorderStroke(1.dp, BorderLight)
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            // Header: Name + Type Badge + Status Badge
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(
                    modifier = Modifier.weight(1f),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    Box(
                        modifier = Modifier
                            .size(40.dp)
                            .clip(RoundedCornerShape(8.dp))
                            .background(
                                if (camera.isConnected) StatusGreenLight else StatusSlateLight
                            ),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = if (camera.isWebcam) Icons.Filled.CameraAlt else Icons.Filled.Videocam,
                            contentDescription = null,
                            tint = if (camera.isConnected) StatusGreen else StatusSlate,
                            modifier = Modifier.size(22.dp)
                        )
                    }
                    Column {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(6.dp)
                        ) {
                            Text(
                                text = camera.name,
                                style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold),
                                color = TextDark,
                                maxLines = 1
                            )
                        }
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(6.dp)
                        ) {
                            // Camera Type Pill
                            Surface(
                                shape = RoundedCornerShape(4.dp),
                                color = PrimaryBlueLight,
                                border = BorderStroke(0.5.dp, PrimaryBlue.copy(alpha = 0.3f))
                            ) {
                                Text(
                                    text = camera.cameraType.uppercase(),
                                    style = MaterialTheme.typography.labelSmall.copy(fontSize = 10.sp),
                                    color = PrimaryBlue,
                                    modifier = Modifier.padding(horizontal = 5.dp, vertical = 2.dp)
                                )
                            }
                            if (!camera.location.isNullOrBlank()) {
                                Text(
                                    text = "• ${camera.location}",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = TextMid,
                                    maxLines = 1
                                )
                            }
                        }
                    }
                }

                // Connection status pill
                Surface(
                    shape = RoundedCornerShape(12.dp),
                    color = if (camera.isConnected) StatusGreenLight else StatusRedLight,
                    border = BorderStroke(1.dp, if (camera.isConnected) StatusGreen else StatusRed)
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        Box(
                            modifier = Modifier
                                .size(6.dp)
                                .clip(CircleShape)
                                .background(if (camera.isConnected) StatusGreen else StatusRed)
                        )
                        Text(
                            text = if (camera.isConnected) "ONLINE" else "OFFLINE",
                            style = MaterialTheme.typography.labelSmall.copy(fontWeight = FontWeight.Bold),
                            color = if (camera.isConnected) StatusGreen else StatusRed
                        )
                    }
                }
            }

            HorizontalDivider(color = BorderLight)

            // Camera Specs Row
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column {
                    Text("RESOLUTION", style = MaterialTheme.typography.labelSmall, color = TextMuted)
                    Text(
                        camera.resolutionFormatted,
                        style = MaterialTheme.typography.bodyMedium.copy(fontWeight = FontWeight.SemiBold),
                        color = TextDark
                    )
                }
                Column {
                    Text("FRAMERATE", style = MaterialTheme.typography.labelSmall, color = TextMuted)
                    Text(
                        "${camera.fps} FPS",
                        style = MaterialTheme.typography.bodyMedium.copy(fontWeight = FontWeight.SemiBold),
                        color = TextDark
                    )
                }
                Column {
                    Text("STATUS", style = MaterialTheme.typography.labelSmall, color = TextMuted)
                    Text(
                        camera.status,
                        style = MaterialTheme.typography.bodyMedium.copy(fontWeight = FontWeight.SemiBold),
                        color = if (camera.isConnected) StatusGreen else StatusSlate
                    )
                }
            }

            // Source String
            Surface(
                shape = RoundedCornerShape(8.dp),
                color = BgMuted,
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    Icon(
                        imageVector = Icons.Filled.Link,
                        contentDescription = null,
                        tint = TextMuted,
                        modifier = Modifier.size(14.dp)
                    )
                    Text(
                        text = camera.sourceMasked,
                        style = MaterialTheme.typography.bodySmall.copy(fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace),
                        color = TextMid,
                        maxLines = 1
                    )
                }
            }

            // Actions Row: Test Connection, Edit, Delete
            if (onTestClick != null || onEditClick != null || onDeleteClick != null) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    if (onTestClick != null) {
                        OutlinedButton(
                            onClick = onTestClick,
                            shape = RoundedCornerShape(8.dp),
                            border = BorderStroke(1.dp, PrimaryBlue.copy(alpha = 0.5f)),
                            colors = ButtonDefaults.outlinedButtonColors(contentColor = PrimaryBlue),
                            contentPadding = PaddingValues(horizontal = 10.dp, vertical = 4.dp),
                            modifier = Modifier.height(32.dp)
                        ) {
                            Icon(Icons.Filled.NetworkCheck, contentDescription = null, modifier = Modifier.size(14.dp))
                            Spacer(Modifier.width(4.dp))
                            Text("Test Probe", style = MaterialTheme.typography.labelSmall)
                        }
                    } else {
                        Spacer(Modifier.width(1.dp))
                    }

                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        if (onEditClick != null && !camera.isWebcam) {
                            FilledTonalIconButton(
                                onClick = onEditClick,
                                modifier = Modifier.size(32.dp),
                                colors = IconButtonDefaults.filledTonalIconButtonColors(
                                    containerColor = BgSubtle,
                                    contentColor = PrimaryBlue
                                )
                            ) {
                                Icon(Icons.Filled.Edit, contentDescription = "Edit Camera", modifier = Modifier.size(16.dp))
                            }
                        }

                        if (onDeleteClick != null && !camera.isWebcam) {
                            FilledTonalIconButton(
                                onClick = onDeleteClick,
                                modifier = Modifier.size(32.dp),
                                colors = IconButtonDefaults.filledTonalIconButtonColors(
                                    containerColor = StatusRedLight,
                                    contentColor = StatusRed
                                )
                            ) {
                                Icon(Icons.Filled.Delete, contentDescription = "Delete Camera", modifier = Modifier.size(16.dp))
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun IncidentCard(
    incident: IncidentSummary,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    Surface(
        modifier = modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(14.dp),
        color = BgCard,
        shadowElevation = 2.dp,
        border = BorderStroke(1.dp, BorderLight)
    ) {
        Row(
            modifier = Modifier.padding(14.dp),
            horizontalArrangement = Arrangement.spacedBy(14.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // Severity Icon Badge
            Box(
                modifier = Modifier
                    .size(44.dp)
                    .clip(RoundedCornerShape(10.dp))
                    .background(StatusRedLight),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = Icons.Filled.WarningAmber,
                    contentDescription = "Alert",
                    tint = StatusRed,
                    modifier = Modifier.size(24.dp)
                )
            }

            // Details
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = incident.zoneName,
                        style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold),
                        color = TextDark,
                        maxLines = 1
                    )
                    // Review status chip
                    Surface(
                        shape = RoundedCornerShape(8.dp),
                        color = if (incident.reviewStatus == "REVIEWED") StatusGreenLight else StatusAmberLight
                    ) {
                        Text(
                            text = incident.reviewStatus,
                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                            style = MaterialTheme.typography.labelSmall.copy(
                                fontWeight = FontWeight.Bold,
                                fontSize = 10.sp
                            ),
                            color = if (incident.reviewStatus == "REVIEWED") StatusGreen else StatusAmber
                        )
                    }
                }

                Text(
                    text = "${incident.cameraName} • ${incident.eventTimestamp}",
                    style = MaterialTheme.typography.bodySmall,
                    color = TextMid
                )

                Row(
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "Confidence: ${incident.confidencePercentage}%",
                        style = MaterialTheme.typography.labelSmall,
                        color = PrimaryBlue
                    )
                    if (incident.durationSeconds > 0) {
                        Text(
                            text = "Duration: ${incident.durationSeconds}s",
                            style = MaterialTheme.typography.labelSmall,
                            color = TextMuted
                        )
                    }
                }
            }

            Icon(
                imageVector = Icons.Filled.ChevronRight,
                contentDescription = "View Details",
                tint = TextMid,
                modifier = Modifier.size(20.dp)
            )
        }
    }
}
