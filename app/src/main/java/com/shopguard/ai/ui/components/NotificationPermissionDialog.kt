package com.shopguard.ai.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.NotificationsActive
import androidx.compose.material.icons.filled.Security
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.shopguard.ai.ui.theme.*

@Composable
fun NotificationPermissionDialog(
    onConfirm: () -> Unit,
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
                    imageVector = Icons.Filled.NotificationsActive,
                    contentDescription = null,
                    tint = PrimaryBlue
                )
                Text(
                    text = "Enable Security Alerts",
                    style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold),
                    color = TextDark
                )
            }
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(
                    text = "ShopGuard AI requires notification permission to instantly alert you of unauthorized human entries, perimeter breaches, and alarm triggers while your system is armed.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextMid
                )

                Surface(
                    shape = RoundedCornerShape(8.dp),
                    color = StatusGreenLight,
                    border = BorderStroke(1.dp, StatusGreen.copy(alpha = 0.4f))
                ) {
                    Row(
                        modifier = Modifier.padding(10.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Filled.Security,
                            contentDescription = null,
                            tint = StatusGreen,
                            modifier = Modifier.size(18.dp)
                        )
                        Text(
                            text = "High-importance alerts provide immediate lockscreen warnings with live camera snapshots.",
                            style = MaterialTheme.typography.bodySmall,
                            color = TextDark
                        )
                    }
                }
            }
        },
        confirmButton = {
            Button(
                onClick = onConfirm,
                colors = ButtonDefaults.buttonColors(
                    containerColor = PrimaryBlue,
                    contentColor   = Color.White
                )
            ) {
                Text("Allow Notifications", fontWeight = FontWeight.Bold)
            }
        },
        dismissButton = {
            OutlinedButton(
                onClick = onDismiss,
                border = BorderStroke(1.dp, BorderLight)
            ) {
                Text("Not Now", color = TextMid)
            }
        },
        containerColor = BgCard,
        shape = RoundedCornerShape(16.dp)
    )
}
