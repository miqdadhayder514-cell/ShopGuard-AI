package com.shopguard.ai.ui.screens.alarm

import androidx.compose.animation.core.*
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.NotificationsActive
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.shopguard.ai.data.service.SecurityAlarmService
import com.shopguard.ai.ui.theme.*

/**
 * Full-screen alarm display shown when a security incident is active.
 * Provides pulsing visual feedback and a prominent STOP ALARM button.
 * Does NOT disarm ShopGuard AI — only silences the local alarm sound.
 */
@Composable
fun AlarmScreen(
    incidentType: String,
    cameraName: String,
    detectedAt: String,
    onStopAlarm: () -> Unit
) {
    val context = LocalContext.current

    // Pulsing scale animation for the alarm icon
    val infiniteTransition = rememberInfiniteTransition(label = "alarm_pulse")
    val scale by infiniteTransition.animateFloat(
        initialValue = 1.0f,
        targetValue  = 1.3f,
        animationSpec = infiniteRepeatable(
            animation  = tween(500, easing = EaseInOut),
            repeatMode = RepeatMode.Reverse
        ),
        label = "alarm_icon_scale"
    )

    val displayType = incidentType
        .replace("_", " ")
        .split(" ")
        .joinToString(" ") { word -> word.replaceFirstChar { it.uppercase() } }
        .ifBlank { "Security Alert" }

    // White background with red accent — stays readable and urgent on light theme
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(BgCard),
        contentAlignment = Alignment.Center
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(24.dp),
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 32.dp)
        ) {

            // ── Pulsing alarm icon ────────────────────────────────────────────
            Box(
                modifier = Modifier
                    .size(140.dp)
                    .scale(scale)
                    .background(StatusRedLight, CircleShape),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = Icons.Filled.NotificationsActive,
                    contentDescription = "Active Security Alarm",
                    tint = StatusRed,
                    modifier = Modifier.size(72.dp)
                )
            }

            // ── Title ─────────────────────────────────────────────────────────
            Text(
                text = "⚠ SECURITY ALERT",
                style = MaterialTheme.typography.headlineSmall.copy(
                    fontWeight = FontWeight.ExtraBold,
                    letterSpacing = 2.sp
                ),
                color = StatusRed,
                textAlign = TextAlign.Center
            )

            Text(
                text = "ShopGuard AI — Intrusion Detected",
                style = MaterialTheme.typography.bodyMedium,
                color = TextMid,
                textAlign = TextAlign.Center
            )

            // ── Incident details card ─────────────────────────────────────────
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                color = BgCard,
                shadowElevation = 4.dp,
                border = BorderStroke(1.5.dp, StatusRed.copy(alpha = 0.4f))
            ) {
                Column(
                    modifier = Modifier.padding(20.dp),
                    verticalArrangement = Arrangement.spacedBy(14.dp)
                ) {
                    AlarmInfoRow(label = "Incident Type", value = displayType)
                    HorizontalDivider(color = BorderLight)
                    AlarmInfoRow(label = "Camera", value = cameraName.ifBlank { "Unknown" })
                    HorizontalDivider(color = BorderLight)
                    AlarmInfoRow(label = "Detected At", value = detectedAt.ifBlank { "Just now" })
                    HorizontalDivider(color = BorderLight)

                    // Animated RINGING indicator
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Box(
                            modifier = Modifier
                                .size(10.dp)
                                .scale(scale)
                                .background(StatusRed, CircleShape)
                        )
                        Text(
                            text = "ALARM RINGING",
                            style = MaterialTheme.typography.labelLarge.copy(
                                fontWeight = FontWeight.Bold,
                                letterSpacing = 1.5.sp
                            ),
                            color = StatusRed
                        )
                    }
                }
            }

            // ── STOP ALARM button ─────────────────────────────────────────────
            Button(
                onClick = {
                    SecurityAlarmService.stopAlarm(context)
                    onStopAlarm()
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(64.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = StatusRed,
                    contentColor   = Color.White
                ),
                shape = RoundedCornerShape(14.dp),
                elevation = ButtonDefaults.buttonElevation(defaultElevation = 4.dp)
            ) {
                Icon(
                    imageVector = Icons.Filled.Stop,
                    contentDescription = "Stop Alarm",
                    modifier = Modifier.size(26.dp)
                )
                Spacer(modifier = Modifier.width(12.dp))
                Text(
                    text = "STOP ALARM",
                    style = MaterialTheme.typography.titleMedium.copy(
                        fontWeight = FontWeight.ExtraBold,
                        letterSpacing = 1.5.sp
                    )
                )
            }

            Text(
                text = "Stopping the alarm does not disarm ShopGuard AI\nor delete the incident from history.",
                style = MaterialTheme.typography.bodySmall,
                color = TextMuted,
                textAlign = TextAlign.Center,
                lineHeight = 18.sp
            )
        }
    }
}

@Composable
private fun AlarmInfoRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodyMedium,
            color = TextMid
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium.copy(fontWeight = FontWeight.SemiBold),
            color = TextDark,
            textAlign = TextAlign.End,
            modifier = Modifier
                .weight(1f)
                .padding(start = 16.dp)
        )
    }
}
