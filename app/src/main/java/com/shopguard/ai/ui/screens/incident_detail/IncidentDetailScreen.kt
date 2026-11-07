package com.shopguard.ai.ui.screens.incident_detail

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.shopguard.ai.data.model.IncidentDetail
import com.shopguard.ai.ui.components.*
import com.shopguard.ai.ui.theme.*
import com.shopguard.ai.ui.viewmodel.MainViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun IncidentDetailScreen(
    incidentId: String,
    viewModel: MainViewModel,
    onNavigateBack: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()

    LaunchedEffect(incidentId) {
        viewModel.loadIncidentDetail(incidentId)
    }

    val detail: IncidentDetail? = uiState.selectedIncident
    val scrollState = rememberScrollState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        "Incident Details",
                        style = MaterialTheme.typography.titleLarge,
                        color = TextDark
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back", tint = TextDark)
                    }
                },
                actions = {
                    if (detail != null) {
                        val isReviewed = (detail.reviewStatus == "REVIEWED")
                        Button(
                            onClick = { viewModel.markIncidentReviewed(detail.incidentId) },
                            enabled = !isReviewed,
                            colors = ButtonDefaults.buttonColors(
                                containerColor = if (isReviewed) StatusGreenLight else StatusGreen,
                                contentColor   = if (isReviewed) StatusGreen else Color.White,
                                disabledContainerColor = StatusGreenLight,
                                disabledContentColor   = StatusGreen
                            ),
                            shape = RoundedCornerShape(8.dp)
                        ) {
                            Icon(
                                imageVector = if (isReviewed) Icons.Filled.Check else Icons.Filled.Done,
                                contentDescription = null,
                                modifier = Modifier.size(16.dp)
                            )
                            Spacer(Modifier.width(4.dp))
                            Text(if (isReviewed) "Reviewed" else "Mark Reviewed")
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = BgCard,
                    titleContentColor = TextDark
                )
            )
        },
        containerColor = BgPage
    ) { innerPadding ->
        if (detail == null) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(innerPadding),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator(color = PrimaryBlue)
            }
        } else {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(innerPadding)
                    .verticalScroll(scrollState)
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                // Demo Mode Warning
                if (detail.simulationMode || uiState.isDemoMode) {
                    Surface(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                        color = DemoBadgeBackground,
                        border = BorderStroke(1.dp, DemoPurple.copy(alpha = 0.4f))
                    ) {
                        Row(
                            modifier = Modifier.padding(14.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(10.dp)
                        ) {
                            Icon(Icons.Filled.Info, contentDescription = null, tint = DemoPurple)
                            Column {
                                Text(
                                    text = "SIMULATED INCIDENT DATA",
                                    style = MaterialTheme.typography.labelMedium.copy(fontWeight = FontWeight.Bold),
                                    color = DemoPurple
                                )
                                Text(
                                    text = "This record is generated by ShopGuard AI simulation testing and does not represent an actual physical break-in.",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = TextMid
                                )
                            }
                        }
                    }
                }

                // Video Player Simulation Viewport
                Surface(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(220.dp),
                    shape = RoundedCornerShape(16.dp),
                    color = Color(0xFF1A1A2E),
                    border = BorderStroke(1.dp, BorderMedium)
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        Column(
                            horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            Box(
                                modifier = Modifier
                                    .size(54.dp)
                                    .clip(RoundedCornerShape(27.dp))
                                    .background(PrimaryBlue.copy(alpha = 0.25f)),
                                contentAlignment = Alignment.Center
                            ) {
                                Icon(
                                    imageVector = Icons.Filled.PlayArrow,
                                    contentDescription = "Play Footage",
                                    tint = PrimaryBlueLight,
                                    modifier = Modifier.size(32.dp)
                                )
                            }
                            Text(
                                text = "H.264 INCIDENT CLIP PLAYBACK",
                                style = MaterialTheme.typography.labelSmall.copy(fontWeight = FontWeight.Bold),
                                color = Color.White
                            )
                            Text(
                                text = "${detail.videoFilename} (${detail.durationSeconds}s • ${detail.totalFrames} frames)",
                                style = MaterialTheme.typography.bodySmall,
                                color = Color(0xFFCBD5E1)
                            )
                        }

                        // Top-left camera stamp
                        Surface(
                            modifier = Modifier
                                .align(Alignment.TopStart)
                                .padding(12.dp),
                            shape = RoundedCornerShape(6.dp),
                            color = Color.Black.copy(alpha = 0.7f)
                        ) {
                            Text(
                                text = "REC • ${detail.cameraName}",
                                modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                                style = MaterialTheme.typography.labelSmall,
                                color = StatusRed
                            )
                        }
                    }
                }

                // Incident Core Information Card
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(14.dp),
                    color = BgCard,
                    shadowElevation = 2.dp,
                    border = BorderStroke(1.dp, BorderLight)
                ) {
                    Column(
                        modifier = Modifier.padding(18.dp),
                        verticalArrangement = Arrangement.spacedBy(14.dp)
                    ) {
                        Text(
                            text = "Intrusion Telemetry",
                            style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold),
                            color = TextDark
                        )

                        HorizontalDivider(color = BorderLight)

                        DetailRow("Incident ID",          detail.incidentId)
                        DetailRow("Camera Feed",          detail.cameraName)
                        DetailRow("Restricted Zone",      detail.zoneName)
                        DetailRow("Event Classification", detail.eventType)
                        DetailRow("Event Timestamp",      detail.eventTimestamp)
                        DetailRow("AI Person Confidence", "${(detail.confidence * 100).toInt()}% (YOLO11n)")
                        if (detail.trackId != null) {
                            DetailRow("ByteTrack Tracking ID", "#${detail.trackId}")
                        }
                        DetailRow("Clip Duration",   "${detail.durationSeconds} seconds")
                        DetailRow("Captured Frames", "${detail.totalFrames} frames")
                        DetailRow("Audit Status",    detail.reviewStatus)
                    }
                }
            }
        }
    }
}

@Composable
private fun DetailRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(text = label, style = MaterialTheme.typography.bodyMedium, color = TextMid)
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium.copy(fontWeight = FontWeight.SemiBold),
            color = TextDark
        )
    }
}
