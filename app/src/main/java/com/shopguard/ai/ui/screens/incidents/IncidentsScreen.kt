package com.shopguard.ai.ui.screens.incidents

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircleOutline
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.shopguard.ai.ui.components.*
import com.shopguard.ai.ui.theme.*
import com.shopguard.ai.ui.viewmodel.MainViewModel

@Composable
fun IncidentsScreen(
    viewModel: MainViewModel,
    onNavigateToDashboard: () -> Unit,
    onNavigateToCameras: () -> Unit,
    onNavigateToIncidentDetail: (String) -> Unit,
    onNavigateToSettings: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    var selectedFilter by remember { mutableStateOf("ALL") }

    val filteredIncidents = remember(uiState.incidents, selectedFilter) {
        when (selectedFilter) {
            "UNREVIEWED" -> uiState.incidents.filter { it.reviewStatus == "UNREVIEWED" }
            "REVIEWED"   -> uiState.incidents.filter { it.reviewStatus == "REVIEWED" }
            else         -> uiState.incidents
        }
    }

    Scaffold(
        topBar = {
            ShopGuardTopBar(
                title = "Incident History",
                isDemoMode = uiState.isDemoMode,
                onSyncClick = { viewModel.refreshAll() },
                onDeviceClick = onNavigateToSettings
            )
        },
        bottomBar = {
            ShopGuardBottomNavBar(
                currentRoute = "incidents",
                onNavigate = { route ->
                    when (route) {
                        "dashboard" -> onNavigateToDashboard()
                        "cameras"   -> onNavigateToCameras()
                        "settings"  -> onNavigateToSettings()
                    }
                }
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

                // Filter chips row
                LazyRow(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    val filters = listOf(
                        "ALL"        to "All (${uiState.incidents.size})",
                        "UNREVIEWED" to "Unreviewed (${uiState.incidents.count { it.reviewStatus == "UNREVIEWED" }})",
                        "REVIEWED"   to "Reviewed (${uiState.incidents.count { it.reviewStatus == "REVIEWED" }})"
                    )

                    items(filters) { (key, label) ->
                        FilterChip(
                            selected = selectedFilter == key,
                            onClick  = { selectedFilter = key },
                            label    = { Text(label) },
                            colors = FilterChipDefaults.filterChipColors(
                                selectedContainerColor = PrimaryBlue,
                                selectedLabelColor     = androidx.compose.ui.graphics.Color.White,
                                containerColor         = BgCard,
                                labelColor             = TextMid
                            ),
                            border = FilterChipDefaults.filterChipBorder(
                                enabled  = true,
                                selected = selectedFilter == key,
                                borderColor = if (selectedFilter == key) PrimaryBlue else BorderLight
                            )
                        )
                    }
                }
            }

            if (filteredIncidents.isEmpty()) {
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
                                .padding(36.dp),
                            horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.spacedBy(10.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Filled.CheckCircleOutline,
                                contentDescription = null,
                                tint = StatusGreen,
                                modifier = Modifier.size(48.dp)
                            )
                            Text("No Incidents Found", style = MaterialTheme.typography.titleMedium, color = TextDark)
                            Text(
                                "No intrusion events match the selected filter.",
                                style = MaterialTheme.typography.bodySmall,
                                color = TextMid
                            )
                        }
                    }
                }
            } else {
                items(filteredIncidents) { incident ->
                    IncidentCard(
                        incident = incident,
                        onClick  = { onNavigateToIncidentDetail(incident.incidentId) }
                    )
                }
            }

            item {
                Spacer(modifier = Modifier.height(16.dp))
            }
        }
    }
}
