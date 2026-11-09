# ShopGuard AI – Android Mobile Security Application Report

## Executive Summary

The native Android mobile client for **ShopGuard AI** has been successfully developed and integrated into the project workspace using **Kotlin**, **Jetpack Compose**, and **Material 3**. The mobile application operates as a companion client to the ShopGuard AI Windows Security Agent, providing real-time system monitoring, camera telemetry, incident management, device configuration, and functional security arm/disarm controls.

The application incorporates a robust **Model-View-ViewModel (MVVM)** architecture, an integrated **Demo Mode** featuring simulated CCTV feeds and realistic security incidents with interactive controls, and full support for direct local connections to the Windows security agent REST API.

---

## 1. Architectural Overview

### 1.1 Technology Stack
- **Language**: Kotlin 2.2.10
- **UI Framework**: Jetpack Compose (Compose BOM 2026.02.01) with Material 3 Design
- **Architecture**: MVVM (Model-View-ViewModel) + Repository Pattern + Clean Architecture
- **Navigation**: Jetpack Navigation Compose (`NavHost`, `composable`, deep routes)
- **Networking**: OkHttp 4.12.0 + Gson 2.11.0 (Direct HTTP/REST communication with ShopGuard Local Security Agent)
- **State Management**: Kotlin StateFlow (`StateFlow<SecurityUiState>`) with lifecycle-aware Compose collection
- **Persistence**: Android `SharedPreferences` for device configuration and demo mode toggle

### 1.2 Package Structure
```
app/src/main/java/com/shopguard/ai/
├── data/
│   ├── local/
│   │   └── PreferencesManager.kt         # Secure storage for host, port, API key, and demo state
│   ├── model/
│   │   └── SecurityModels.kt             # Data models, DTOs, and state representations
│   ├── network/
│   │   └── ApiClient.kt                  # REST client with headers, timeout handling, error parsing
│   └── repository/
│       ├── DemoDataProvider.kt          # Interactive in-memory simulation engine for Demo Mode
│       └── ShopGuardRepository.kt       # Dual-mode repository orchestrating Live Agent vs Demo Mode
├── ui/
│   ├── components/
│   │   ├── CardComponents.kt             # Reusable CameraCard and IncidentCard components
│   │   └── SecurityComponents.kt         # SecurityStatusBadge, DemoBanner, TopBar, BottomBar, Dialogs
│   ├── navigation/
│   │   ├── NavGraph.kt                   # NavHost route declarations and screen transitions
│   │   └── Screen.kt                     # Type-safe navigation routes
│   ├── screens/
│   │   ├── cameras/CamerasScreen.kt      # Multi-camera grid with connection status & telemetry
│   │   ├── connection/DeviceConnectionScreen.kt # Windows agent IP/Port/Key configuration & ping test
│   │   ├── dashboard/DashboardScreen.kt  # Dark navy executive dashboard with hero shield indicator
│   │   ├── incident_detail/IncidentDetailScreen.kt # Clip player viewport & forensic metadata
│   │   ├── incidents/IncidentsScreen.kt  # Filterable incident log (All, Unreviewed, Reviewed)
│   │   ├── settings/SettingsScreen.kt    # System diagnostics, Demo Mode toggle, connection summary
│   │   └── splash/SplashScreen.kt        # Animated shield branding splash screen
│   ├── theme/
│   │   ├── Color.kt                      # Modern Dark Navy palette with security accent colors
│   │   ├── Theme.kt                      # ShopGuardTheme implementing Material 3 DarkColorScheme
│   │   └── Type.kt                       # Material 3 typography definitions
│   └── viewmodel/
│       └── MainViewModel.kt              # Central ViewModel managing state, actions, and network flows
├── MainActivity.kt                       # Entry Activity setting content and ViewModel
└── test/java/com/shopguard/ai/
    └── ShopGuardUnitTest.kt              # Unit tests for state machine, demo provider, and repo logic
```

---

## 2. Implemented Screens & UI Components

### 2.1 Splash Screen (`SplashScreen.kt`)
- **Branding**: Prominent glowing ShopGuard AI security shield emblem with animated pulsing glow effect.
- **Visuals**: Displays version `v2.0 (Mobile Client)`, security engine subtitle, and a non-blocking 1.8-second transition to the Dashboard.

### 2.2 Security Dashboard (`DashboardScreen.kt`)
- **Hero Status Indicator**: Circular security shield visual displaying current state:
  - **ARMED**: Emerald green glowing border, active shield icon, and "SYSTEM ARMED & SECURE" status.
  - **DISARMED**: Amber warning border, open lock icon, and "SYSTEM DISARMED — INTRUSION DETECTION INACTIVE" status.
- **Controls & Safety**:
  - High-visibility "ARM SECURITY" and "DISARM SECURITY" action buttons.
  - Mandatory **confirmation dialogs** before initiating state transitions (`ArmConfirmationDialog` and `DisarmConfirmationDialog`) to prevent accidental clicks.
- **Quick Metrics**: 3-column status overview displaying Active Cameras, Monitored Zones, and Incident Count.
- **Recent Activity Feed**: Quick preview of the most recent security events with direct tap-through to details.

### 2.3 Camera Screen (`CamerasScreen.kt`)
- **Camera Feeds Grid**: Real-time status list for all connected cameras.
- **Telemetry Display**:
  - Camera identifier and friendly zone name (e.g., `camera_01 — Front Entrance`).
  - Connection pill (`CONNECTED` with live green dot or `OFFLINE` with warning red).
  - Stream type badge (`RTSP H.264 Stream` or `Local USB Webcam`).
  - Performance metrics: FPS counter (e.g., `15.0 FPS`) and resolution spec (e.g., `1920x1080` or `1280x720`).
  - Last frame timestamp.

### 2.4 Incident History Screen (`IncidentsScreen.kt`)
- **Filter Chips**: Interactive filtering between `All`, `Unreviewed`, and `Reviewed` security events.
- **Incident Cards**:
  - Alert icon with severity indicator (`High Alert` red badge for unauthorized intrusions).
  - Trigger time, camera ID, and human-readable event description.
  - Review status badge (`UNREVIEWED` with notification dot vs `REVIEWED`).
  - Tap-to-navigate directly into incident forensic details.

### 2.5 Incident Details Screen (`IncidentDetailScreen.kt`)
- **Simulation Viewport**: High-contrast clip playback viewport with bounding box overlay mockup and timestamp overlay.
- **Forensic Telemetry**:
  - Incident ID, camera identifier, and capture timestamp.
  - Detection confidence rating (e.g., `87.4%`).
  - Event classification (e.g., `Person Intrusion Detected`).
  - Local clip file path reference (retained locally on Windows host, never uploaded to cloud).
- **Interactive Review**: Functional "Mark as Reviewed" action button which updates incident status in real-time.

### 2.6 Settings Screen (`SettingsScreen.kt`)
- **Connection Summary Card**: Displays current target agent (`10.0.2.2:8000` or custom IP), authorization status, and quick link to Device Connection settings.
- **Interactive Demo Mode Switch**: Seamlessly toggles between Live Agent mode and Demo Mode. Instant UI state refresh.
- **Full-Volume Security Alarm**: Settings provides a link to Android's Do Not Disturb access screen and shows whether ShopGuard has that access. For an active incident only, the alarm stream is temporarily raised to maximum and, when authorized, Do Not Disturb is temporarily disabled; the saved settings are restored when the alarm stops.
- **Architecture & System Information**: Displays mobile client version, agent API compatibility, and security notices regarding local network isolation.

Android requires the shopkeeper to grant Do Not Disturb access in **Settings → App Settings → Full-Volume Security Alarm → Enable Full-Volume Alarm**. The app persists the original alarm volume and interruption filter for recovery if the alarm service restarts. Android/OEM policies, hardware mute controls, connected audio devices, a powered-off phone, or a force-stopped app can still prevent audible alert delivery; this is a best-effort alarm feature, not a guarantee that every phone sound restriction can be bypassed.

### 2.7 Device Connection Screen (`DeviceConnectionScreen.kt`)
- **Agent Endpoint Inputs**:
  - Host IP address input with validation (supports `10.0.2.2` for Android Emulator, `127.0.0.1` for local, and LAN IP `192.168.x.x` for physical device testing).
  - Port number input (default `8000`).
  - API Key input with secure password masking and toggleable eye icon.
- **Test Ping Engine**: Interactive "Test Ping" button executing a health check against `/api/health`, measuring latency in milliseconds and reporting connection diagnostics before saving.
- **Save & Apply**: Writes parameters to persistent `SharedPreferences` and prompts a refresh of active data feeds.

### 2.8 Bottom Navigation (`ShopGuardBottomNavBar.kt`)
- Material 3 Navigation Bar seamlessly switching between:
  1. **Dashboard** (`Icons.Default.Security`)
  2. **Cameras** (`Icons.Default.Videocam`)
  3. **Incidents** (`Icons.Default.History`)
  4. **Settings** (`Icons.Default.Settings`)
- Persistent demo mode notification banner above the navigation bar when Demo Mode is active.

---

## 3. Demo Mode Implementation

Per the requirements, Demo Mode is **functional, interactive, and transparently simulated**:
- **Explicit Labeling**: Every screen clearly renders a high-visibility `[DEMO MODE — SIMULATED DATA]` banner and `DEMO` badge. The application never misrepresents demo feeds as real CCTV surveillance.
- **Interactive Arm / Disarm**: Users can press Arm and Disarm buttons, confirm in the security dialog, and watch the state machine switch between `ARMED` and `DISARMED`.
- **Preloaded Feeds**:
  - `camera_01`: Front Entrance (RTSP, 1080p, 15 FPS, Connected)
  - `camera_02`: Cash Register Counter (Webcam, 720p, 30 FPS, Connected)
  - `camera_03`: Rear Stockroom & Alley (RTSP, 1080p, Offline simulation)
- **Preloaded Incidents**: Realistic simulated events with full forensic metadata and interactive review marking.
- **Zero Network Requirement**: Demo Mode functions completely offline without requiring the Python agent to be running.

---

## 4. Live Windows Agent Integration

When Demo Mode is toggled off in Settings:
- Connects directly to the ShopGuard AI Windows Local Security Agent (Phase 2 FastAPI server).
- **Default Endpoints Targeted**:
  - `GET /api/status`: Master system state, arm status, uptime.
  - `GET /api/security/state`: Real-time arming state verification.
  - `POST /api/security/arm`: Issues arm command with JSON payload.
  - `POST /api/security/disarm`: Issues disarm command with JSON payload.
  - `GET /api/cameras`: Camera health, FPS, and connection state.
  - `GET /api/incidents`: Incident history list.
  - `GET /api/health`: Health probe and ping test.
- **Authentication**:
  - Injects `X-API-Key: <key>` header on every request (matching the agent's authentication middleware).
  - Stores credentials exclusively in private app-level `SharedPreferences` (never hardcoded in source code).
- **Security & Privacy**:
  - Local network / loopback only; no external cloud servers or public internet endpoints.
  - Cleartext HTTP allowed solely for LAN development/local agent addresses (`android:usesCleartextTraffic="true"`).

---

## 5. How to Run in Android Studio

### Step 1: Open the Project in Android Studio
1. Launch **Android Studio Ladybug (or newer)**.
2. Select **Open** and navigate to:
   ```
   C:\Users\Miqdad Haider\Desktop\ShopGuard AI
   ```
3. Android Studio will automatically recognize the root project and the `:app` module using the existing Gradle wrapper.

### Step 2: Sync Gradle
- Android Studio will invoke Gradle sync using the embedded JDK (JDK 21 or JDK 25).
- Ensure that the project JDK is set to **Android Studio JBR** (`File -> Settings -> Build, Execution, Deployment -> Build Tools -> Gradle -> Gradle JDK`).

### Step 3: Run the Application
1. Connect an Android device (via USB with USB Debugging enabled) or start an Android Virtual Device (AVD Emulator running API 26+).
2. Select `app` in the run configuration dropdown.
3. Click the green **Run ('app')** button (or press `Shift + F10`).
4. The app launches immediately into the **ShopGuard AI Splash Screen**, transitioning into the **Dashboard**.

### Step 4: Testing with Live Windows Security Agent
If you want to connect the Android app to your running Python agent instead of Demo Mode:
1. In the Python project, start the local security agent:
   ```powershell
   python tools/run_agent.py --webcam
   ```
2. In the Android App:
   - Navigate to **Settings** -> **Device Connection**.
   - If using the **Android Emulator**, set Host to `10.0.2.2` (this maps to your Windows host machine's `127.0.0.1`).
   - If using a **Physical Android phone** on the same Wi-Fi, set Host to your PC's LAN IP (e.g., `192.168.1.15`).
   - Set Port to `8000`.
   - Enter your `API_KEY` (from your `.env` or agent configuration).
   - Tap **Test Ping** to verify connectivity.
   - Tap **Save Configuration**.
   - Return to **Settings** and toggle **Demo Mode OFF**.
   - Return to the **Dashboard** to view live webcam telemetry and control real Arm/Disarm states.

---

## 6. Automated Unit Tests

A comprehensive unit test suite was implemented in `app/src/test/java/com/shopguard/ai/ShopGuardUnitTest.kt` covering:
- Safe startup in `DISARMED` state.
- Demo mode arm and disarm state transitions.
- Duplicate arming rejection.
- Camera listing and connection state reporting.
- Incident review status mutation.
- Device configuration URL formation.

---

## 7. Compliance Checklist

| Requirement | Status | Details |
| :--- | :---: | :--- |
| Professional splash screen | Verified | Animated shield emblem, branding, auto-transition |
| Dark navy security dashboard | Verified | Custom high-contrast theme (`#090D1A`, `#141C33`, `#00E5FF`) |
| Prominent ARMED / DISARMED indicator | Verified | Glowing hero status shield badge |
| Arm / Disarm confirmation dialogs | Verified | Prevents inadvertent state triggers |
| Camera connection status screen | Verified | Feeds grid with connection pill, stream type, FPS, resolution |
| Incident history screen | Verified | Interactive filters (All, Unreviewed, Reviewed) with time & camera IDs |
| Incident details screen | Verified | Viewport mockup, forensic metadata, "Mark as Reviewed" action |
| Settings screen | Verified | Demo mode switch, connection summary, architecture specs |
| Device connection configuration | Verified | Host, port, masked API key, and live ping test |
| Material 3 Bottom Navigation | Verified | Dashboard, Cameras, Incidents, Settings with persistence |
| Functional Demo Mode | Verified | Complete interactive simulation with explicit `[DEMO MODE]` badges |
| No hardcoded credentials | Verified | Encapsulated in `PreferencesManager` |
| Zero changes to Python Phase 1/2 | Verified | Python backend files left completely untouched |
