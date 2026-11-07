package com.shopguard.ai.ui.navigation

sealed class Screen(val route: String) {
    object Splash : Screen("splash")
    object Dashboard : Screen("dashboard")
    object Cameras : Screen("cameras")
    object Incidents : Screen("incidents")
    object IncidentDetail : Screen("incident_detail/{incidentId}") {
        fun createRoute(incidentId: String) = "incident_detail/$incidentId"
    }
    object Settings : Screen("settings")
    object DeviceConnection : Screen("connection")
    object AddCamera : Screen("add_camera")
    object EditCamera : Screen("edit_camera/{cameraId}") {
        fun createRoute(cameraId: String) = "edit_camera/$cameraId"
    }
    object AlarmActive : Screen("alarm_active")
}
