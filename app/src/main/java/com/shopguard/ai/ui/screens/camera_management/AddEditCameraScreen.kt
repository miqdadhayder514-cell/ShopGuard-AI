package com.shopguard.ai.ui.screens.camera_management

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import com.shopguard.ai.data.model.CameraCreateRequest
import com.shopguard.ai.data.model.CameraTestRequest
import com.shopguard.ai.data.model.CameraUpdateRequest
import com.shopguard.ai.ui.components.DemoModeBanner
import com.shopguard.ai.ui.theme.*
import com.shopguard.ai.ui.viewmodel.MainViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AddEditCameraScreen(
    viewModel: MainViewModel,
    cameraId: String? = null,
    onNavigateBack: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    val isEditMode = !cameraId.isNullOrBlank()

    val existingCamera = remember(cameraId, uiState.cameras) {
        cameraId?.let { id -> uiState.cameras.find { it.id == id } }
    }

    var cameraName  by remember(existingCamera) { mutableStateOf(existingCamera?.name?.removePrefix("[DEMO] ") ?: "") }
    var cameraType  by remember(existingCamera) { mutableStateOf(existingCamera?.cameraType ?: "IP Camera") }
    var useFullUrl  by remember { mutableStateOf(false) }
    var ipAddress   by remember(existingCamera) { mutableStateOf(existingCamera?.ipAddress ?: "") }
    var portStr     by remember(existingCamera) { mutableStateOf(existingCamera?.port?.toString() ?: "554") }
    var username    by remember { mutableStateOf("") }
    var password    by remember { mutableStateOf("") }
    var streamPath  by remember(existingCamera) { mutableStateOf(existingCamera?.streamPath ?: "/live/ch0") }
    var fullRtspUrl by remember { mutableStateOf("") }
    var location    by remember(existingCamera) { mutableStateOf(existingCamera?.location ?: "") }
    var fpsStr      by remember(existingCamera) { mutableStateOf(existingCamera?.fps?.toInt()?.toString() ?: "5") }
    var isPasswordVisible by remember { mutableStateOf(false) }
    var validationError   by remember { mutableStateOf<String?>(null) }

    DisposableEffect(Unit) {
        onDispose { viewModel.clearCameraTestResult() }
    }

    // Shared OutlinedTextField colours for light theme
    val fieldColors = OutlinedTextFieldDefaults.colors(
        focusedBorderColor   = PrimaryBlue,
        unfocusedBorderColor = BorderLight,
        focusedTextColor     = TextDark,
        unfocusedTextColor   = TextDark,
        focusedLabelColor    = PrimaryBlue,
        unfocusedLabelColor  = TextMid,
        focusedContainerColor   = BgCard,
        unfocusedContainerColor = BgCard
    )

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            text = if (isEditMode) "Edit Camera" else "Add New Camera",
                            style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold),
                            color = TextDark
                        )
                        Text(
                            text = if (isEditMode) "ID: $cameraId" else "RTSP • DVR • NVR Stream",
                            style = MaterialTheme.typography.labelSmall,
                            color = PrimaryBlue
                        )
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "Back",
                            tint = TextDark
                        )
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
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            if (uiState.isDemoMode) {
                DemoModeBanner(onConfigureClick = {})
            }

            // Section 1: Camera Identity
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(12.dp),
                color = BgCard,
                shadowElevation = 2.dp,
                border = BorderStroke(1.dp, BorderLight)
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(14.dp)
                ) {
                    Text(
                        text = "CAMERA IDENTITY",
                        style = MaterialTheme.typography.labelMedium.copy(fontWeight = FontWeight.Bold),
                        color = PrimaryBlue
                    )

                    OutlinedTextField(
                        value = cameraName,
                        onValueChange = { cameraName = it; validationError = null },
                        label = { Text("Camera Name *") },
                        placeholder = { Text("e.g. Front Entrance CCTV") },
                        leadingIcon = { Icon(Icons.Filled.Videocam, contentDescription = null, tint = PrimaryBlue) },
                        modifier = Modifier.fillMaxWidth(),
                        colors = fieldColors
                    )

                    // Camera Type Selection Chips
                    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text("Camera Device Architecture", style = MaterialTheme.typography.labelSmall, color = TextMid)
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            listOf("IP Camera", "DVR", "NVR").forEach { type ->
                                val isSelected = cameraType == type
                                FilterChip(
                                    selected = isSelected,
                                    onClick  = { cameraType = type },
                                    label    = { Text(type) },
                                    colors = FilterChipDefaults.filterChipColors(
                                        selectedContainerColor = PrimaryBlue,
                                        selectedLabelColor     = Color.White,
                                        containerColor         = BgCard,
                                        labelColor             = TextMid
                                    ),
                                    border = FilterChipDefaults.filterChipBorder(
                                        enabled  = true,
                                        selected = isSelected,
                                        borderColor = if (isSelected) PrimaryBlue else BorderLight
                                    )
                                )
                            }
                        }
                    }

                    OutlinedTextField(
                        value = location,
                        onValueChange = { location = it },
                        label = { Text("Location / Zone Description (Optional)") },
                        placeholder = { Text("e.g. Main Entrance Turnstiles / North Alley") },
                        leadingIcon = { Icon(Icons.Filled.Place, contentDescription = null, tint = TextMid) },
                        modifier = Modifier.fillMaxWidth(),
                        colors = fieldColors
                    )
                }
            }

            // Section 2: Network Stream Configuration
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(12.dp),
                color = BgCard,
                shadowElevation = 2.dp,
                border = BorderStroke(1.dp, BorderLight)
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(14.dp)
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "NETWORK STREAM CONFIGURATION",
                            style = MaterialTheme.typography.labelMedium.copy(fontWeight = FontWeight.Bold),
                            color = PrimaryBlue
                        )
                        TextButton(onClick = { useFullUrl = !useFullUrl }) {
                            Text(
                                text = if (useFullUrl) "Enter Individual Fields" else "Enter Complete RTSP URL",
                                style = MaterialTheme.typography.labelSmall,
                                color = PrimaryBlue
                            )
                        }
                    }

                    if (!useFullUrl) {
                        OutlinedTextField(
                            value = ipAddress,
                            onValueChange = { ipAddress = it; validationError = null },
                            label = { Text("IP Address or Hostname *") },
                            placeholder = { Text("192.168.1.100") },
                            leadingIcon = { Icon(Icons.Filled.Router, contentDescription = null, tint = PrimaryBlue) },
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                            modifier = Modifier.fillMaxWidth(),
                            colors = fieldColors
                        )

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(12.dp)
                        ) {
                            OutlinedTextField(
                                value = portStr,
                                onValueChange = { portStr = it },
                                label = { Text("RTSP Port") },
                                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                                modifier = Modifier.weight(1f),
                                colors = fieldColors
                            )
                            OutlinedTextField(
                                value = streamPath,
                                onValueChange = { streamPath = it },
                                label = { Text("Stream Path") },
                                placeholder = { Text("/live/ch0") },
                                modifier = Modifier.weight(2f),
                                colors = fieldColors
                            )
                        }

                        OutlinedTextField(
                            value = username,
                            onValueChange = { username = it },
                            label = { Text("Username") },
                            placeholder = { Text("admin") },
                            leadingIcon = { Icon(Icons.Filled.Person, contentDescription = null, tint = TextMid) },
                            modifier = Modifier.fillMaxWidth(),
                            colors = fieldColors
                        )

                        OutlinedTextField(
                            value = password,
                            onValueChange = { password = it },
                            label = { Text(if (isEditMode) "Password (Leave blank to keep existing)" else "Password") },
                            placeholder = { Text("••••••••") },
                            leadingIcon = { Icon(Icons.Filled.Lock, contentDescription = null, tint = TextMid) },
                            trailingIcon = {
                                IconButton(onClick = { isPasswordVisible = !isPasswordVisible }) {
                                    Icon(
                                        imageVector = if (isPasswordVisible) Icons.Filled.Visibility else Icons.Filled.VisibilityOff,
                                        contentDescription = "Toggle password visibility",
                                        tint = TextMid
                                    )
                                }
                            },
                            visualTransformation = if (isPasswordVisible) VisualTransformation.None else PasswordVisualTransformation(),
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                            modifier = Modifier.fillMaxWidth(),
                            colors = fieldColors
                        )
                    } else {
                        OutlinedTextField(
                            value = fullRtspUrl,
                            onValueChange = { fullRtspUrl = it; validationError = null },
                            label = { Text("Complete RTSP Stream URL *") },
                            placeholder = { Text("rtsp://admin:pass@192.168.1.100:554/live/ch0") },
                            leadingIcon = { Icon(Icons.Filled.Link, contentDescription = null, tint = PrimaryBlue) },
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                            trailingIcon = {
                                IconButton(onClick = { isPasswordVisible = !isPasswordVisible }) {
                                    Icon(
                                        imageVector = if (isPasswordVisible) Icons.Filled.Visibility else Icons.Filled.VisibilityOff,
                                        contentDescription = "Toggle URL password masking",
                                        tint = TextMid
                                    )
                                }
                            },
                            visualTransformation = if (isPasswordVisible) VisualTransformation.None else PasswordVisualTransformation(),
                            modifier = Modifier.fillMaxWidth(),
                            colors = fieldColors
                        )
                    }

                    OutlinedTextField(
                        value = fpsStr,
                        onValueChange = { fpsStr = it },
                        label = { Text("Target Processing Framerate (FPS)") },
                        placeholder = { Text("5") },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        modifier = Modifier.fillMaxWidth(),
                        colors = fieldColors
                    )
                }
            }

            // Validation Error Banner
            if (validationError != null) {
                Surface(
                    shape = RoundedCornerShape(8.dp),
                    color = StatusRedLight,
                    border = BorderStroke(1.dp, StatusRed.copy(alpha = 0.5f)),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Row(
                        modifier = Modifier.padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Icon(Icons.Filled.Error, contentDescription = null, tint = StatusRed)
                        Text(validationError ?: "", color = TextDark, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }

            // Connection Test Result Banner
            if (uiState.cameraTestResult != null) {
                val res = uiState.cameraTestResult!!
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp),
                    color = if (res.success) StatusGreenLight else StatusRedLight,
                    border = BorderStroke(1.dp, if (res.success) StatusGreen else StatusRed)
                ) {
                    Column(
                        modifier = Modifier.padding(14.dp),
                        verticalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            Icon(
                                imageVector = if (res.success) Icons.Filled.CheckCircle else Icons.Filled.Cancel,
                                contentDescription = null,
                                tint = if (res.success) StatusGreen else StatusRed
                            )
                            Text(
                                text = if (res.success) "Probe Succeeded" else "Probe Failed",
                                style = MaterialTheme.typography.titleSmall.copy(fontWeight = FontWeight.Bold),
                                color = if (res.success) StatusGreen else StatusRed
                            )
                        }
                        Text(text = res.message, style = MaterialTheme.typography.bodySmall, color = TextDark)
                        if (res.sourceMasked.isNotBlank()) {
                            Text(
                                text = "Target: ${res.sourceMasked}",
                                style = MaterialTheme.typography.labelSmall,
                                color = TextMid
                            )
                        }
                    }
                }
            }

            // Buttons: Test Connection & Save
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                OutlinedButton(
                    onClick = {
                        val port = portStr.toIntOrNull() ?: 554
                        if (!useFullUrl && ipAddress.isBlank()) { validationError = "Please enter an IP address or hostname."; return@OutlinedButton }
                        if (useFullUrl && fullRtspUrl.isBlank()) { validationError = "Please enter a valid RTSP URL."; return@OutlinedButton }

                        val req = if (useFullUrl) {
                            CameraTestRequest(name = cameraName.ifBlank { "Test Camera" }, cameraType = cameraType, rtspUrl = fullRtspUrl.trim())
                        } else {
                            CameraTestRequest(name = cameraName.ifBlank { "Test Camera" }, cameraType = cameraType, ipAddress = ipAddress.trim(), port = port, username = username.ifBlank { null }, password = password.ifBlank { null }, streamPath = streamPath.trim())
                        }
                        viewModel.testCameraConnection(req)
                    },
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(10.dp),
                    border = BorderStroke(1.dp, PrimaryBlue),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = PrimaryBlue),
                    enabled = !uiState.isTestingCamera && !uiState.isSavingCamera
                ) {
                    if (uiState.isTestingCamera) {
                        CircularProgressIndicator(modifier = Modifier.size(16.dp), color = PrimaryBlue, strokeWidth = 2.dp)
                        Spacer(Modifier.width(6.dp))
                        Text("Probing...")
                    } else {
                        Icon(Icons.Filled.NetworkCheck, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(Modifier.width(6.dp))
                        Text("Test Probe")
                    }
                }

                Button(
                    onClick = {
                        if (cameraName.isBlank()) { validationError = "Camera name is required."; return@Button }
                        if (!useFullUrl && ipAddress.isBlank()) { validationError = "IP address or hostname is required."; return@Button }
                        if (useFullUrl && fullRtspUrl.isBlank()) { validationError = "RTSP stream URL is required."; return@Button }

                        val port = portStr.toIntOrNull() ?: 554
                        val fps  = fpsStr.toDoubleOrNull() ?: 5.0

                        if (isEditMode) {
                            val req = if (useFullUrl) {
                                CameraUpdateRequest(name = cameraName.trim(), cameraType = cameraType, rtspUrl = fullRtspUrl.trim(), location = location.trim(), fps = fps)
                            } else {
                                CameraUpdateRequest(name = cameraName.trim(), cameraType = cameraType, ipAddress = ipAddress.trim(), port = port, username = username.ifBlank { null }, password = password.ifBlank { null }, streamPath = streamPath.trim(), location = location.trim(), fps = fps)
                            }
                            viewModel.updateCamera(cameraId ?: "", req) { success -> if (success) onNavigateBack() }
                        } else {
                            val req = if (useFullUrl) {
                                CameraCreateRequest(name = cameraName.trim(), cameraType = cameraType, rtspUrl = fullRtspUrl.trim(), location = location.trim(), fps = fps)
                            } else {
                                CameraCreateRequest(name = cameraName.trim(), cameraType = cameraType, ipAddress = ipAddress.trim(), port = port, username = username.ifBlank { null }, password = password.ifBlank { null }, streamPath = streamPath.trim(), location = location.trim(), fps = fps)
                            }
                            viewModel.addCamera(req) { success -> if (success) onNavigateBack() }
                        }
                    },
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(10.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = PrimaryBlue, contentColor = Color.White),
                    enabled = !uiState.isTestingCamera && !uiState.isSavingCamera
                ) {
                    if (uiState.isSavingCamera) {
                        CircularProgressIndicator(modifier = Modifier.size(16.dp), color = Color.White, strokeWidth = 2.dp)
                        Spacer(Modifier.width(6.dp))
                        Text("Saving...")
                    } else {
                        Icon(Icons.Filled.Save, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(Modifier.width(6.dp))
                        Text(if (isEditMode) "Save Changes" else "Add Camera")
                    }
                }
            }

            Spacer(Modifier.height(16.dp))
        }
    }
}
