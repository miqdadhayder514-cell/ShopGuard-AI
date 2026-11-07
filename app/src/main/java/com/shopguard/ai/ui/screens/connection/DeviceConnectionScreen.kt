package com.shopguard.ai.ui.screens.connection

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
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.shopguard.ai.data.model.DeviceConfig
import com.shopguard.ai.data.network.UrlBuilder
import com.shopguard.ai.ui.theme.*
import com.shopguard.ai.ui.viewmodel.MainViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DeviceConnectionScreen(
    viewModel: MainViewModel,
    onNavigateBack: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    val config = uiState.deviceConfig

    var host          by remember(config.host)      { mutableStateOf(config.host) }
    var portStr       by remember(config.port)      { mutableStateOf(config.port.toString()) }
    var apiKey        by remember(config.apiKey)    { mutableStateOf(config.apiKey) }
    var isApiKeyVisible by remember              { mutableStateOf(false) }
    var isDemoMode    by remember(config.isDemoMode){ mutableStateOf(config.isDemoMode) }
    var useHttps      by remember(config.useHttps) { mutableStateOf(config.useHttps) }

    // Auto-detect Tailscale HTTPS
    LaunchedEffect(host) {
        if (host.contains(".ts.net", ignoreCase = true) || host.startsWith("https://", ignoreCase = true)) {
            if (!useHttps) {
                useHttps = true
                if (portStr == "8000" || portStr.isBlank()) portStr = "443"
            }
        }
    }

    // Auto-disable Demo Mode on successful connection test
    LaunchedEffect(uiState.connectionTestResult) {
        val result = uiState.connectionTestResult
        if (result != null && result.isSuccess) isDemoMode = false
    }

    val computedBaseUrl = remember(host, portStr, useHttps) {
        val p = portStr.toIntOrNull()
        UrlBuilder.buildBaseUrl(host, p, useHttps)
    }

    val scrollState = rememberScrollState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        "Agent Connection Setup",
                        style = MaterialTheme.typography.titleLarge,
                        color = TextDark
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back", tint = TextDark)
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
                .verticalScroll(scrollState)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Mode Selector Card
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(14.dp),
                color = BgCard,
                shadowElevation = 2.dp,
                border = BorderStroke(1.dp, if (isDemoMode) DemoPurple.copy(alpha = 0.5f) else BorderLight)
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = if (isDemoMode) "Demo Simulation Mode Enabled" else "Live Agent Connection Mode",
                            style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold),
                            color = if (isDemoMode) DemoPurple else PrimaryBlue
                        )
                        Text(
                            text = if (isDemoMode)
                                "Using mock security data for instant UI testing."
                            else
                                "Connecting to your Windows ShopGuard AI Agent.",
                            style = MaterialTheme.typography.bodySmall,
                            color = TextMid
                        )
                    }
                    Switch(
                        checked = isDemoMode,
                        onCheckedChange = { isDemoMode = it },
                        colors = SwitchDefaults.colors(
                            checkedThumbColor   = Color.White,
                            checkedTrackColor   = DemoPurple,
                            uncheckedThumbColor = TextMuted,
                            uncheckedTrackColor = BgMuted
                        )
                    )
                }
            }

            // Connection Parameter Inputs
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(14.dp),
                color = BgCard,
                shadowElevation = 2.dp,
                border = BorderStroke(1.dp, BorderLight)
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(14.dp)
                ) {
                    Text(
                        text = "Windows Agent Connection Parameters",
                        style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold),
                        color = TextDark
                    )

                    // Protocol Selection Chips
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        FilterChip(
                            selected = useHttps,
                            onClick = {
                                useHttps = true
                                if (portStr == "8000" || portStr.isBlank()) portStr = "443"
                            },
                            label = { Text("🔒 HTTPS (Tailscale / SSL)", fontSize = 12.sp) },
                            colors = FilterChipDefaults.filterChipColors(
                                selectedContainerColor = PrimaryBlueLight,
                                selectedLabelColor     = PrimaryBlue
                            ),
                            border = FilterChipDefaults.filterChipBorder(
                                enabled  = true,
                                selected = useHttps,
                                borderColor = if (useHttps) PrimaryBlue else BorderLight
                            ),
                            modifier = Modifier.weight(1f)
                        )

                        FilterChip(
                            selected = !useHttps,
                            onClick = {
                                useHttps = false
                                if (portStr == "443" || portStr.isBlank()) portStr = "8000"
                            },
                            label = { Text("🌐 HTTP (Android Emulator)", fontSize = 12.sp) },
                            colors = FilterChipDefaults.filterChipColors(
                                selectedContainerColor = PrimaryBlueLight,
                                selectedLabelColor     = PrimaryBlue
                            ),
                            border = FilterChipDefaults.filterChipBorder(
                                enabled  = true,
                                selected = !useHttps,
                                borderColor = if (!useHttps) PrimaryBlue else BorderLight
                            ),
                            modifier = Modifier.weight(1f)
                        )
                    }

                    OutlinedTextField(
                        value = host,
                        onValueChange = { host = it },
                        label = { Text("Loopback relay host or emulator alias") },
                        placeholder = { Text(if (useHttps) "your-machine.tailscale.net" else "10.0.2.2") },
                        leadingIcon = { Icon(Icons.Filled.Dns, contentDescription = null, tint = PrimaryBlue) },
                        modifier = Modifier.fillMaxWidth(),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor   = PrimaryBlue,
                            unfocusedBorderColor = BorderLight,
                            focusedTextColor     = TextDark,
                            unfocusedTextColor   = TextDark,
                            focusedLabelColor    = PrimaryBlue,
                            unfocusedLabelColor  = TextMid,
                            focusedContainerColor   = BgCard,
                            unfocusedContainerColor = BgCard
                        )
                    )

                    OutlinedTextField(
                        value = portStr,
                        onValueChange = { portStr = it },
                        label = { Text("Port Number") },
                        placeholder = { Text(if (useHttps) "443" else "8000") },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        leadingIcon = { Icon(Icons.Filled.Numbers, contentDescription = null, tint = PrimaryBlue) },
                        modifier = Modifier.fillMaxWidth(),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor   = PrimaryBlue,
                            unfocusedBorderColor = BorderLight,
                            focusedTextColor     = TextDark,
                            unfocusedTextColor   = TextDark,
                            focusedLabelColor    = PrimaryBlue,
                            unfocusedLabelColor  = TextMid,
                            focusedContainerColor   = BgCard,
                            unfocusedContainerColor = BgCard
                        )
                    )

                    OutlinedTextField(
                        value = apiKey,
                        onValueChange = { apiKey = it },
                        label = { Text("Agent Secret API Key (Optional for Health)") },
                        placeholder = { Text("Token from config/agent_api_key.secret") },
                        leadingIcon = { Icon(Icons.Filled.VpnKey, contentDescription = null, tint = PrimaryBlue) },
                        trailingIcon = {
                            IconButton(onClick = { isApiKeyVisible = !isApiKeyVisible }) {
                                Icon(
                                    imageVector = if (isApiKeyVisible) Icons.Filled.VisibilityOff else Icons.Filled.Visibility,
                                    contentDescription = "Toggle visibility",
                                    tint = TextMid
                                )
                            }
                        },
                        visualTransformation = if (isApiKeyVisible) VisualTransformation.None else PasswordVisualTransformation(),
                        modifier = Modifier.fillMaxWidth(),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor   = PrimaryBlue,
                            unfocusedBorderColor = BorderLight,
                            focusedTextColor     = TextDark,
                            unfocusedTextColor   = TextDark,
                            focusedLabelColor    = PrimaryBlue,
                            unfocusedLabelColor  = TextMid,
                            focusedContainerColor   = BgCard,
                            unfocusedContainerColor = BgCard
                        )
                    )

                    // Live Computed Target URL Preview
                    Surface(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(8.dp),
                        color = BgMuted,
                        border = BorderStroke(1.dp, BorderLight)
                    ) {
                        Column(modifier = Modifier.padding(10.dp)) {
                            Text(
                                text = "RESOLVED BASE URL:",
                                style = MaterialTheme.typography.labelSmall.copy(fontWeight = FontWeight.Bold),
                                color = PrimaryBlue
                            )
                            Text(
                                text = computedBaseUrl,
                                style = MaterialTheme.typography.bodySmall.copy(fontFamily = FontFamily.Monospace),
                                color = TextDark
                            )
                            Spacer(Modifier.height(4.dp))
                            Text(
                                text = "Probe endpoint: ${UrlBuilder.buildEndpointUrl(computedBaseUrl, "/api/health")}",
                                style = MaterialTheme.typography.bodySmall.copy(fontSize = 11.sp),
                                color = TextMid
                            )
                        }
                    }
                }
            }

            // Connection Test Result Card
            if (uiState.connectionTestResult != null) {
                val res = uiState.connectionTestResult!!
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp),
                    color = if (res.isSuccess) StatusGreenLight else StatusRedLight,
                    border = BorderStroke(1.dp, if (res.isSuccess) StatusGreen else StatusRed)
                ) {
                    Column(
                        modifier = Modifier.padding(14.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(10.dp)
                        ) {
                            Icon(
                                imageVector = if (res.isSuccess) Icons.Filled.CheckCircle else Icons.Filled.Error,
                                contentDescription = null,
                                tint = if (res.isSuccess) StatusGreen else StatusRed
                            )
                            Column(modifier = Modifier.weight(1f)) {
                                Text(
                                    text = if (res.isSuccess) "Agent Reachable (${res.latencyMs}ms)" else "Connection Failed (HTTP ${if (res.statusCode > 0) res.statusCode else "Error"})",
                                    style = MaterialTheme.typography.titleSmall.copy(fontWeight = FontWeight.Bold),
                                    color = if (res.isSuccess) StatusGreen else StatusRed
                                )
                                Text(
                                    text = res.message,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = TextDark
                                )
                                if (res.isSuccess) {
                                    Text(
                                        text = "✓ Live Agent verified. Demo Simulation Mode automatically switched OFF.",
                                        style = MaterialTheme.typography.labelSmall.copy(fontWeight = FontWeight.Bold),
                                        color = PrimaryBlue
                                    )
                                }
                            }
                        }

                        // Detailed telemetry on success
                        if (res.isSuccess && res.healthResponse != null) {
                            val h = res.healthResponse
                            HorizontalDivider(color = StatusGreen.copy(alpha = 0.3f))
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text("Health: ${h.overallHealth}", style = MaterialTheme.typography.labelSmall, color = TextDark)
                                Text("State: ${h.securityState}",  style = MaterialTheme.typography.labelSmall, color = PrimaryBlue)
                                Text("Mode: ${h.mode}",            style = MaterialTheme.typography.labelSmall, color = TextMid)
                            }
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text("AI Model: ${if (h.aiModelLoaded) "Loaded" else "Offline"}", style = MaterialTheme.typography.labelSmall, color = TextDark)
                                Text("Cameras: ${h.cameras.size}",                                style = MaterialTheme.typography.labelSmall, color = TextDark)
                                Text("Disk: ${h.diskFreeGb} GB free",                             style = MaterialTheme.typography.labelSmall, color = TextMid)
                            }
                        }

                        // Response body preview on failure
                        if (!res.isSuccess && !res.rawResponseBody.isNullOrBlank()) {
                            HorizontalDivider(color = StatusRed.copy(alpha = 0.3f))
                            Text(
                                text = "RAW SERVER RESPONSE / ERROR:",
                                style = MaterialTheme.typography.labelSmall.copy(fontWeight = FontWeight.Bold),
                                color = StatusRed
                            )
                            Surface(
                                modifier = Modifier.fillMaxWidth(),
                                shape = RoundedCornerShape(6.dp),
                                color = BgMuted
                            ) {
                                Text(
                                    text = res.rawResponseBody.take(400),
                                    style = MaterialTheme.typography.bodySmall.copy(
                                        fontFamily = FontFamily.Monospace,
                                        fontSize = 11.sp
                                    ),
                                    color = TextMid,
                                    modifier = Modifier.padding(8.dp)
                                )
                            }
                        }
                    }
                }
            }

            // Action Buttons
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                OutlinedButton(
                    onClick = {
                        val port = portStr.toIntOrNull() ?: if (useHttps) 443 else 8000
                        viewModel.testConnection(host.trim(), port, apiKey.trim(), useHttps)
                    },
                    enabled = !uiState.isTestingConnection,
                    modifier = Modifier
                        .weight(1f)
                        .height(48.dp),
                    border = BorderStroke(1.dp, PrimaryBlue)
                ) {
                    if (uiState.isTestingConnection) {
                        CircularProgressIndicator(modifier = Modifier.size(20.dp), color = PrimaryBlue)
                    } else {
                        Icon(Icons.Filled.NetworkCheck, contentDescription = null, tint = PrimaryBlue, modifier = Modifier.size(18.dp))
                        Spacer(Modifier.width(6.dp))
                        Text("Test Connection", color = PrimaryBlue)
                    }
                }

                Button(
                    onClick = {
                        val port = portStr.toIntOrNull() ?: if (useHttps) 443 else 8000
                        viewModel.saveDeviceConfig(
                            DeviceConfig(
                                host      = host.trim(),
                                port      = port,
                                apiKey    = apiKey.trim(),
                                isDemoMode = isDemoMode,
                                useHttps  = useHttps
                            )
                        )
                        onNavigateBack()
                    },
                    modifier = Modifier
                        .weight(1f)
                        .height(48.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = PrimaryBlue,
                        contentColor   = Color.White
                    )
                ) {
                    Icon(Icons.Filled.Save, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(6.dp))
                    Text("Save & Apply", fontWeight = FontWeight.Bold)
                }
            }

            // Architecture Security Notice
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(12.dp),
                color = BgSubtle,
                border = BorderStroke(1.dp, PrimaryBlue.copy(alpha = 0.2f))
            ) {
                Column(
                    modifier = Modifier.padding(14.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    Text(
                        text = "SECURE NETWORK ARCHITECTURE NOTE",
                        style = MaterialTheme.typography.labelSmall.copy(fontWeight = FontWeight.Bold),
                        color = PrimaryBlue
                    )
                    Text(
                        text = "• Tailscale HTTPS: Enter your Tailscale domain (e.g. machine-name.tailscale.net) with port 443 and select HTTPS.\n" +
                                "• Configure Tailscale Serve (or another authenticated TLS relay) to proxy to the Windows agent at 127.0.0.1:8000.\n" +
                                "• Android Studio Emulator: use host '10.0.2.2' with port 8000 and select HTTP.\n" +
                                "• Direct LAN/public binding is refused; physical phones must use the encrypted relay.\n" +
                                "• TLS verification remains active for encrypted remote connections.",
                        style = MaterialTheme.typography.bodySmall,
                        color = TextMid
                    )
                }
            }
        }
    }
}
