package com.shopguard.ai.ui.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.navArgument
import com.shopguard.ai.ui.screens.alarm.AlarmScreen
import com.shopguard.ai.ui.screens.camera_management.AddEditCameraScreen
import com.shopguard.ai.ui.screens.cameras.CamerasScreen
import com.shopguard.ai.ui.screens.connection.DeviceConnectionScreen
import com.shopguard.ai.ui.screens.dashboard.DashboardScreen
import com.shopguard.ai.ui.screens.incident_detail.IncidentDetailScreen
import com.shopguard.ai.ui.screens.incidents.IncidentsScreen
import com.shopguard.ai.ui.screens.settings.SettingsScreen
import com.shopguard.ai.ui.screens.splash.SplashScreen
import com.shopguard.ai.ui.viewmodel.MainViewModel

@Composable
fun ShopGuardNavGraph(
    navController: NavHostController,
    viewModel: MainViewModel
) {
    val uiState by viewModel.uiState.collectAsState()
    val pendingIncidentId = uiState.pendingIncidentDetailId

    // Navigate to incident detail when notification is tapped
    LaunchedEffect(pendingIncidentId) {
        if (!pendingIncidentId.isNullOrBlank()) {
            navController.navigate(Screen.IncidentDetail.createRoute(pendingIncidentId))
            viewModel.clearPendingIncidentDetailId()
        }
    }

    // Auto-navigate to alarm screen when alarm becomes active (e.g. FCM received while backgrounded)
    val isAlarmActive = uiState.isAlarmActive
    LaunchedEffect(isAlarmActive) {
        if (isAlarmActive &&
            navController.currentDestination?.route != Screen.AlarmActive.route
        ) {
            navController.navigate(Screen.AlarmActive.route)
        }
    }

    NavHost(
        navController = navController,
        startDestination = Screen.Splash.route
    ) {
        composable(Screen.Splash.route) {
            SplashScreen(
                onSplashFinished = {
                    navController.navigate(Screen.Dashboard.route) {
                        popUpTo(Screen.Splash.route) { inclusive = true }
                    }
                }
            )
        }

        composable(Screen.Dashboard.route) {
            DashboardScreen(
                viewModel = viewModel,
                onNavigateToCameras = { navController.navigate(Screen.Cameras.route) },
                onNavigateToIncidents = { navController.navigate(Screen.Incidents.route) },
                onNavigateToIncidentDetail = { id ->
                    navController.navigate(Screen.IncidentDetail.createRoute(id))
                },
                onNavigateToConnection = { navController.navigate(Screen.DeviceConnection.route) }
            )
        }

        composable(Screen.Cameras.route) {
            CamerasScreen(
                viewModel = viewModel,
                onNavigateToDashboard = { navController.navigate(Screen.Dashboard.route) },
                onNavigateToIncidents = { navController.navigate(Screen.Incidents.route) },
                onNavigateToSettings = { navController.navigate(Screen.Settings.route) },
                onNavigateToAddCamera = { navController.navigate(Screen.AddCamera.route) },
                onNavigateToEditCamera = { camId -> navController.navigate(Screen.EditCamera.createRoute(camId)) }
            )
        }

        composable(Screen.AddCamera.route) {
            AddEditCameraScreen(
                viewModel = viewModel,
                onNavigateBack = { navController.popBackStack() }
            )
        }

        composable(
            route = Screen.EditCamera.route,
            arguments = listOf(navArgument("cameraId") { type = NavType.StringType })
        ) { backStackEntry ->
            val cameraId = backStackEntry.arguments?.getString("cameraId") ?: ""
            AddEditCameraScreen(
                viewModel = viewModel,
                cameraId = cameraId,
                onNavigateBack = { navController.popBackStack() }
            )
        }

        composable(Screen.Incidents.route) {
            IncidentsScreen(
                viewModel = viewModel,
                onNavigateToDashboard = { navController.navigate(Screen.Dashboard.route) },
                onNavigateToCameras = { navController.navigate(Screen.Cameras.route) },
                onNavigateToIncidentDetail = { id ->
                    navController.navigate(Screen.IncidentDetail.createRoute(id))
                },
                onNavigateToSettings = { navController.navigate(Screen.Settings.route) }
            )
        }

        composable(
            route = Screen.IncidentDetail.route,
            arguments = listOf(navArgument("incidentId") { type = NavType.StringType })
        ) { backStackEntry ->
            val incidentId = backStackEntry.arguments?.getString("incidentId") ?: ""
            IncidentDetailScreen(
                incidentId = incidentId,
                viewModel = viewModel,
                onNavigateBack = { navController.popBackStack() }
            )
        }

        composable(Screen.Settings.route) {
            SettingsScreen(
                viewModel = viewModel,
                onNavigateToDashboard = { navController.navigate(Screen.Dashboard.route) },
                onNavigateToCameras = { navController.navigate(Screen.Cameras.route) },
                onNavigateToIncidents = { navController.navigate(Screen.Incidents.route) },
                onNavigateToConnection = { navController.navigate(Screen.DeviceConnection.route) }
            )
        }

        composable(Screen.DeviceConnection.route) {
            DeviceConnectionScreen(
                viewModel = viewModel,
                onNavigateBack = { navController.popBackStack() }
            )
        }

        // ── Alarm active screen ───────────────────────────────────────────────
        composable(Screen.AlarmActive.route) {
            AlarmScreen(
                incidentType = uiState.alarmIncidentType,
                cameraName   = uiState.alarmCameraName,
                detectedAt   = uiState.alarmDetectedAt,
                onStopAlarm  = {
                    viewModel.clearAlarmState()
                    navController.popBackStack()
                }
            )
        }
    }
}

