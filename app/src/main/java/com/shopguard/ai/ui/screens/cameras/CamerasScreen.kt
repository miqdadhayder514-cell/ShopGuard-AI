package com.shopguard.ai.ui.screens.cameras

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.VideocamOff
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.shopguard.ai.data.model.CameraInfo
import com.shopguard.ai.data.model.CameraTestRequest
import com.shopguard.ai.ui.components.*
import com.shopguard.ai.ui.theme.*
import com.shopguard.ai.ui.viewmodel.MainViewModel

@Composable
fun CamerasScreen(
    viewModel: MainViewModel,
    onNavigateToDashboard: () -> Unit,
    onNavigateToIncidents: () -> Unit,
    onNavigateToSettings: () -> Unit,
    onNavigateToAddCamera: () -> Unit,
    onNavigateToEditCamera: (String) -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    var cameraToDelete by remember { mutableStateOf<CameraInfo?>(null) }

    Scaffold(
        topBar = {
            ShopGuardTopBar(
                title = "Cameras & Streams",
                isDemoMode = uiState.isDemoMode,
                onSyncClick = { viewModel.refreshAll() },
                onDeviceClick = onNavigateToSettings
            )
        },
        bottomBar = {
            ShopGuardBottomNavBar(
                currentRoute = "cameras",
                onNavigate = { route ->
                    when (route) {
                        "dashboard" -> onNavigateToDashboard()
                        "incidents" -> onNavigateToIncidents()
                        "settings"  -> onNavigateToSettings()
                    }
                }
            )
        },
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = onNavigateToAddCamera,
                containerColor = PrimaryBlue,
                contentColor   = androidx.compose.ui.graphics.Color.White,
                elevation = FloatingActionButtonDefaults.elevation(defaultElevation = 4.dp),
                icon = { Icon(Icons.Filled.Add, contentDescription = "Add Camera") },
                text = { Text("Add New Camera") }
            )
        },
        containerColor = BgPage
    ) { innerPadding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            item {
                Spacer(modifier = Modifier.height(4.dp))
                if (uiState.isDemoMode) {
                    DemoModeBanner(onConfigureClick = onNavigateToSettings)
                    Spacer(modifier = Modifier.height(10.dp))
                }
            }

            // Overview header
            item {
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp),
                    color = BgCard,
                    shadowElevation = 2.dp,
                    border = BorderStroke(1.dp, BorderLight)
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Text(
                                text = "Camera Feeds Telemetry",
                                style = MaterialTheme.typography.titleMedium,
                                color = TextDark
                            )
                            Text(
                                text = "${uiState.cameras.count { it.isConnected }} connected • ${uiState.cameras.size} registered",
                                style = MaterialTheme.typography.bodySmall,
                                color = TextMid
                            )
                        }

                        Button(
                            onClick = onNavigateToAddCamera,
                            colors = ButtonDefaults.buttonColors(
                                containerColor = PrimaryBlue,
                                contentColor   = androidx.compose.ui.graphics.Color.White
                            ),
                            shape = RoundedCornerShape(8.dp)
                        ) {
                            Icon(Icons.Filled.Add, contentDescription = null, modifier = Modifier.size(16.dp))
                            Spacer(Modifier.width(4.dp))
                            Text("Add Camera")
                        }
                    }
                }
            }

            if (uiState.cameras.isEmpty()) {
                item {
                    Surface(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(14.dp),
                        color = BgCard,
                        shadowElevation = 2.dp,
                        border = BorderStroke(1.dp, BorderLight)
                    ) {
                        Column(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(32.dp),
                            horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.spacedBy(12.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Filled.VideocamOff,
                                contentDescription = null,
                                tint = StatusSlate,
                                modifier = Modifier.size(48.dp)
                            )
                            Text("No Cameras Connected", style = MaterialTheme.typography.titleMedium, color = TextDark)
                            Text(
                                "Configure your camera in config.yaml or add an IP camera / DVR / NVR channel.",
                                style = MaterialTheme.typography.bodySmall,
                                color = TextMid,
                                textAlign = androidx.compose.ui.text.style.TextAlign.Center
                            )
                            Button(
                                onClick = onNavigateToAddCamera,
                                colors = ButtonDefaults.buttonColors(
                                    containerColor = PrimaryBlue,
                                    contentColor   = androidx.compose.ui.graphics.Color.White
                                )
                            ) {
                                Text("Add Camera Now")
                            }
                        }
                    }
                }
            } else {
                items(uiState.cameras) { camera ->
                    CameraCard(
                        camera = camera,
                        onEditClick   = { onNavigateToEditCamera(camera.id) },
                        onDeleteClick = { cameraToDelete = camera },
                        onTestClick   = {
                            viewModel.testCameraConnection(
                                CameraTestRequest(
                                    name       = camera.name,
                                    cameraType = camera.cameraType,
                                    ipAddress  = camera.ipAddress,
                                    port       = camera.port ?: 554,
                                    streamPath = camera.streamPath
                                )
                            )
                        }
                    )
                }
            }

            item {
                Spacer(modifier = Modifier.height(80.dp)) // Padding for FAB
            }
        }
    }

    // Delete Confirmation Dialog
    if (cameraToDelete != null) {
        DeleteCameraConfirmationDialog(
            cameraName = cameraToDelete?.name ?: "Camera",
            onConfirm  = {
                val camId = cameraToDelete?.id
                cameraToDelete = null
                if (camId != null) {
                    viewModel.deleteCamera(camId)
                }
            },
            onDismiss = {
                cameraToDelete = null
            }
        )
    }
}
