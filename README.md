# ShopGuard AI — Phase 1 & 2: CCTV Intrusion Detection & Local Security Agent

ShopGuard AI is a commercial, modular, and reliable CCTV-based intrusion detection engine and headless local security agent engineered for Windows 10/11 shop computers. It connects to the shop's existing CCTV cameras (IP cameras or DVR/NVR RTSP feeds), detects human presence within protected restricted areas during armed periods, and automatically records video incidents accompanied by structured JSON audit metadata.

Phase 2 adds a production-oriented **Local Security Agent** exposing a secure, authenticated local FastAPI REST API (`127.0.0.1:8000`) for headless background execution, state persistence, camera health monitoring, and future mobile app integration.

---

## Key Features

- **Local Security Agent (Phase 2)**: Headless background service with FastAPI REST API for status, cameras, health, incidents, and authorized arm/disarm control.
- **Strict Localhost Security & Auth**: Bound strictly to `127.0.0.1` with constant-time API key and Bearer token verification; zero public exposure without a dedicated encrypted tunnel.
- **Safe Startup & Crash Recovery**: Always initializes in `DISARMED` state; persistent disk store (`data/security_state.json`) tracks state history and audits abnormal shutdowns.
- **Existing CCTV Integration**: Connects via OpenCV and RTSP over local network, or tests offline via webcam or local video file simulation.
- **Laptop Webcam Testing Mode**: Test live person detection, tracking, zone intrusions, and recording on your Windows laptop's built-in webcam without physical CCTV hardware.
- **Recorded Video Testing Mode**: Interactive test player with frame-by-frame analysis, pause/resume, playback speed controls, and dynamic arm/disarm.
- **Independent Stream Processing**: Each camera runs on an isolated background thread with fast TCP pre-probing to ensure a disconnected camera never blocks or degrades healthy cameras.
- **RTSP Connection Diagnostic Tool**: Built-in CLI utility (`tools/rtsp_diagnostic.py`) testing TCP reachability, RTSP DESCRIBE authentication, and OpenCV frame decoding.
- **AI Person Detection & Tracking**: Ultralytics YOLO with ByteTrack object tracking. Configurable confidence and CPU-first design (no NVIDIA GPU required; GPU auto-detected if available).
- **Normalized Restricted Zones**: Normalized polygon coordinates `[0.0, 1.0]` ensure zones remain accurate across any camera resolution changes. Includes an interactive installer GUI tool.
- **False-Positive Reduction**:
  - Foot-contact bottom-center coordinate filtering (prevents alerts caused by partial upper-body overlap or shadows).
  - Configurable entry duration persistence (default 2 seconds).
  - Consistent observation frame threshold.
  - Event cooldown timer (default 30 seconds) to prevent duplicate alerts.
  - Cautious event classification (`PERSON_ENTERED_RESTRICTED_ZONE`, `PERSON_PRESENT_IN_RESTRICTED_ZONE`, `POSSIBLE_SUSPICIOUS_ACTIVITY`).
- **Pre & Post Incident Recording**: Continuous in-memory ring buffer saves footage prior to an event and after an event in `.mp4` format along with audit `.json` metadata.
- **Manual Security Controller**: Multi-state state machine (`DISARMED`, `ARMING`, `ARMED`, `PARTIAL`, `OFFLINE`) with 8-point pre-arm verification.
- **Live Visual Monitor**: Professional OpenCV overlay showing live camera feeds, bounding boxes, tracking IDs, motion trails, protected zones, real-time FPS, and security status.

---

## Architecture Overview

```
ShopGuard AI Engine & Local Agent
│
├── Local Security Agent (FastAPI)  ──► 127.0.0.1:8000 REST API (Auth Guard & State Store)
│
├── Camera Manager & Stream Readers ──► Threaded RTSP & Webcam Capture (Auto-reconnect & TCP probe)
│
├── Person Detector & Tracker       ──► YOLO11n + ByteTrack (CPU-optimized, class 0: person)
│
├── Zone Manager & Intrusion Engine ──► Normalized Polygons & Bottom-Center Contact Filter
│                                       (Persistence & Cooldown Gating)
│
├── Incident Recorder               ──► Rolling Memory Buffer (Pre/Post-event .mp4 + .json)
│
├── Security Controller             ──► Thread-Safe State Machine (DISARMED ◄► ARMED / PARTIAL)
│
└── Health Monitor & Visualizer     ──► Headless Diagnostics & Optional OpenCV Live HUD
```

---

## Directory Structure

```
ShopGuard-AI/
├── main.py                          # Main application entry point & CLI
├── run.bat                          # Windows batch launcher
├── requirements.txt                 # Python dependencies
├── README.md                        # Complete documentation
├── PHASE_2_IMPLEMENTATION_REPORT.md # Phase 2 engineering implementation report
├── API_DOCUMENTATION.md             # REST API specifications for future Android integration
├── LOCAL_AGENT_SETUP.md             # Windows service & setup instructions
├── FINAL_DEPLOYMENT_READINESS.md    # Pre-deployment audit report
├── RECORDED_VIDEO_TEST_REPORT.md    # Recorded video testing verification report
├── WEBCAM_TEST_REPORT.md            # Webcam testing verification report
├── SMALL_PERSON_DETECTION_REPORT.md # Small & distant person detection report
├── .env.example                     # Template for RTSP credentials & API key
├── .gitignore                       # Git ignore rules
│
├── config/
│   ├── config.yaml                  # Main system configuration (includes agent & multi-res)
│   └── zones.example.json           # Camera restricted zone definitions
│
├── models/
│   ├── README.md                    # Model download & air-gapped instructions
│   └── yolo11n.pt                   # Pre-downloaded YOLO11n weights
│
├── tools/
│   ├── run_agent.py                 # Standalone Local Security Agent runner
│   ├── benchmark_small_detection.py # Multi-resolution & distant detection benchmark utility
│   ├── rtsp_diagnostic.py           # Multi-stage RTSP connection diagnostic tool
│   ├── test_webcam.py               # Live laptop webcam testing runner with interactive arm/disarm
│   ├── test_recorded_video.py       # Interactive recorded-video testing runner with keyboard controls
│   ├── zone_editor.py               # Interactive point-and-click zone configuration tool
│   ├── generate_test_video.py       # Configurable synthetic CCTV test video generator
│   ├── install_windows_task.ps1     # Windows Task Scheduler auto-start installer (DISARMED mode)
│   └── uninstall_windows_task.ps1   # Windows Task Scheduler removal script
│
├── shopguard/
│   ├── agent/                       # Phase 2 Local Security Agent REST API, auth & state store
│   ├── camera/                      # Stream capture, multithreaded reader, OpenCV visualizer
│   ├── detection/                   # YOLO person detector, coordinate calculators, tiled inference
│   ├── tracking/                    # Object tracker and trajectory manager
│   ├── intrusion/                   # Polygon zones and intrusion event logic
│   ├── recording/                   # Ring buffer and MP4/JSON incident recorder
│   ├── security/                    # Manual arm/disarm controller and state machine
│   ├── monitoring/                  # System health and camera status monitor
│   ├── testing/                     # Recorded video testing player & simulation harness
│   └── utils/                       # Credential-masked logger and config helpers
│
├── data/
│   ├── incidents/                   # Saved incident MP4 videos and JSON metadata
│   ├── logs/                        # Application logs (shopguard.log)
│   ├── security_state.json          # Persistent security agent state & transition log
│   └── temporary/                   # Temporary scratch data
│
└── tests/                           # 68 comprehensive automated tests (100% passing)
```

---

## Prerequisites (Windows 10/11)

1. **Python**: Python 3.11 or higher installed on your Windows computer.
   - When installing Python from [python.org](https://www.python.org/), make sure to check **"Add python.exe to PATH"**.

---

## Quick Start Installation (PowerShell)

Open Windows PowerShell in the `ShopGuard AI` project folder:

### 1. Create Virtual Environment
```powershell
python -m venv venv
```

### 2. Activate the Virtual Environment
```powershell
.\venv\Scripts\Activate.ps1
```
*(If PowerShell displays an execution policy restriction, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` and then run the command above).*

### 3. Install Dependencies
```powershell
.\venv\Scripts\pip install -r requirements.txt
```

---

## Configuration & CCTV Stream Setup

### 1. Secure Credentials with `.env`
Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```
Open `.env` in Notepad and insert your camera's RTSP stream URL:
```env
CAMERA_01_URL=rtsp://admin:ShopPassword123@192.168.1.100:554/h264Preview_01_main
```
> **Security Notice**: Never commit `.env` to GitHub or version control. ShopGuard AI automatically masks stream credentials in all logs (`rtsp://admin:***@192.168.1.100...`).

### 2. Configure `config/config.yaml`
Edit `config/config.yaml` to adjust settings:
```yaml
security:
  initial_state: DISARMED
  confidence_threshold: 0.45
  minimum_persistence_seconds: 2
  event_cooldown_seconds: 30

recording:
  enabled: true
  pre_event_seconds: 10
  post_event_seconds: 15
  output_directory: data/incidents

ai:
  model: models/yolo11n.pt
  device: cpu                    # 'cpu' or 'cuda' (auto-detects GPU)
  processing_fps: 5

cameras:
  - id: camera_01
    name: Main Entrance
    enabled: true
    source: "ENV:CAMERA_01_URL"   # Resolves to CAMERA_01_URL in .env
    fps: 5

zones:
  configuration_file: config/zones.example.json
```

### 3. Verify RTSP Stream Reachability (Diagnostic Tool)
Before starting the main engine, test your CCTV stream connection:
```powershell
.\venv\Scripts\python.exe tools/rtsp_diagnostic.py --camera camera_01
```
Or test an arbitrary RTSP URL directly:
```powershell
.\venv\Scripts\python.exe tools/rtsp_diagnostic.py --url "rtsp://admin:ShopPass@192.168.1.100:554/h264Preview_01_main"
```

---

## Live Laptop Webcam Testing Mode (Windows)

If you do not have physical CCTV cameras or an RTSP NVR/DVR on hand, you can test ShopGuard AI live using your Windows laptop's built-in webcam or an external USB webcam.

### 1. Launching Live Webcam Testing
Run the dedicated webcam testing tool:
```powershell
.\venv\Scripts\python.exe tools/test_webcam.py
```
Or launch through the main application:
```powershell
.\venv\Scripts\python.exe main.py --webcam
```
If you have multiple webcams connected (e.g. built-in laptop camera + external USB webcam):
```powershell
.\venv\Scripts\python.exe tools/test_webcam.py --index 1
```

### 2. Interactive Webcam Controls
While the webcam visualizer window is open, click the window to use the following keyboard controls:

| Key | Action | Description |
|---|---|---|
| **`A`** | **Arm Security** | Runs system checks and activates intrusion detection on the webcam feed. |
| **`D`** | **Disarm Security** | Deactivates intrusion alerts; live camera feed and tracking remain visible. |
| **`S`** | **Health Status** | Prints real-time system diagnostics to the terminal. |
| **`Q` / ESC** | **Exit** | Releases the webcam hardware handle safely and closes the application. |

### 3. Step-by-Step Live Intrusion Walk Test
1. **Position Camera**: Angle your laptop so the webcam captures the room floor and an entrance or walkway.
2. **Launch Application**: Run `.\venv\Scripts\python.exe tools/test_webcam.py`. The window will open displaying `STATE: DISARMED` and `WEBCAM TEST MODE - NOT CCTV`.
3. **Disarmed Walk Test**: Walk in front of the camera. Notice that the green bounding box, confidence score, and ByteTrack ID track your body in real time, but **no incident is created**.
4. **Arm the System**: Press `A` on your keyboard (or type `arm` in the terminal). The banner will turn green: `STATE: ARMED`.
5. **Simulate Intrusion**: Walk into the restricted polygon area on screen and stay inside for at least 2 seconds (persistence threshold). The bounding box turns red, and the bottom banner updates to `ALERT: PERSON_ENTERED_RESTRICTED_ZONE`.
6. **Verify Recordings**: Press `Q` to quit. Check `data/incidents/` to verify that an `.mp4` video clip (including pre-event and post-event footage) and a `.json` metadata file were created with `source_type: "webcam"` and `simulation_mode: true`.

### 4. Troubleshooting Windows Webcam Permissions
If the webcam fails to open:
1. **Windows Camera Privacy**: Open Windows Settings -> **Privacy & security** -> **Camera**, and ensure **"Camera access"** and **"Let desktop apps access your camera"** are switched **ON**.
2. **Exclusive App Locks**: Close any running applications that may hold an exclusive lock on the camera (e.g., Microsoft Teams, Zoom, Skype, Discord, OBS, or browser video calls).
3. **Hardware Privacy Shutter**: Check whether your laptop has a physical sliding camera shutter or a keyboard function key (e.g. `Fn + F10`) that disables the camera sensor.

---

## Recorded Video Testing Mode (Windows CCTV Simulation)

ShopGuard AI includes a complete recorded-video testing mode designed for evaluating AI detection, ByteTrack tracking, zone containment, and incident clip generation using pre-recorded CCTV footage (`.mp4`, `.avi`, `.mkv`, etc.) without requiring physical cameras.

### 1. Launching Recorded Video Tests
To launch interactive testing with a Windows file selection dialog:
```powershell
.\venv\Scripts\python.exe tools/test_recorded_video.py
```
Or specify a video file directly:
```powershell
.\venv\Scripts\python.exe tools/test_recorded_video.py --video "data/temporary/test_feed.mp4"
```
Or use the main application entry point:
```powershell
.\venv\Scripts\python.exe main.py --test-video "data/temporary/test_feed.mp4"
```

### 2. Interactive Keyboard Controls (OpenCV Window)
During playback, click on the video window to use real-time interactive controls:

| Key | Action | Description |
|---|---|---|
| **Spacebar** | Pause / Resume | Freezes frame analysis and video playback. |
| **`A`** | **Arm Security** | Runs system prerequisite checks and activates intrusion detection. |
| **`D`** | **Disarm Security** | Deactivates alerts; video continues playing without triggering incidents. |
| **`R`** | Restart Playback | Rewinds video to frame 0 and resets tracking/buffer states. |
| **`+` / `]`** | Speed Up | Cycles playback speed: 0.25x -> 0.5x -> 1.0x -> 1.5x -> 2.0x -> 4.0x. |
| **`-` / `[`** | Slow Down | Decreases playback speed. |
| **`N` / `.`** | Step Frame | Advances playback by exactly 1 frame when paused. |
| **`Q` / ESC** | Exit | Shuts down the test runner and prints execution summary. |

### 3. Clear Identification & Safety Guardrails
- **Visual Distinction**: The top HUD displays a distinctive purple banner `[RECORDED VIDEO TEST - NOT LIVE CCTV]` and labels the stream `[RECORDED FILE]`.
- **RTSP Disclaimer**: Does not simulate or claim RTSP reachability.
- **Incident Audit Trail**: All recorded incidents generated during video testing are tagged with `source_type: "recorded_video"`, `simulation_mode: true`, and `rtsp_verified: false` in their `.json` metadata files.

### 4. Headless Automated Testing
For automated evaluation or CI benchmarks without GUI windows:
```powershell
.\venv\Scripts\python.exe tools/test_recorded_video.py --video "data/temporary/test_feed.mp4" --no-gui --auto-arm
```

---

## Interactive Zone Configuration Tool

To configure restricted zones visually on your camera feed:

```powershell
.\venv\Scripts\python.exe tools/zone_editor.py --camera camera_01
```

**Controls**:
- **Left Click**: Place polygon points on the camera frame.
- **Right Click**: Undo the last point.
- **'s'**: Save the zone (prompts for zone name and ID).
- **'c'**: Clear points.
- **'q'**: Quit without saving.

Coordinates are saved normalized to `[0.0, 1.0]` inside `config/zones.example.json`.

---

## Running ShopGuard AI

You can start the engine using the Windows launcher:
```cmd
run.bat
```
Or directly from PowerShell:
```powershell
.\venv\Scripts\python.exe main.py
```

### Manual Security Controls (Terminal CLI)
While the engine is running, you can enter the following commands into the terminal:

| Command | Action |
|---|---|
| `arm` | Initiates 8-point verification (camera connectivity, AI model readiness, zones, processing pipeline) and activates night protection. |
| `disarm` | Deactivates night security. Camera feeds and health monitoring remain live, but no intrusion alerts or recordings are generated. |
| `status` | Displays full system diagnostic health (cameras, AI device, storage free space). |
| `exit` | Shuts down background workers, flushes ongoing recordings, and cleanly closes the application. |

---

## Windows Startup Automation (Reboot Reliability)

To ensure ShopGuard AI automatically launches after a Windows reboot:

### 1. Install Startup Task
Open PowerShell as Administrator:
```powershell
powershell -ExecutionPolicy Bypass -File tools/install_windows_task.ps1
```
*Safety Guarantee*: The startup task launches the engine strictly in **DISARMED** mode. This ensures stream connection and health monitoring begin immediately, while ensuring intrusion incident generation remains inactive until the shop owner explicitly arms night security.

### 2. Remove Startup Task
```powershell
powershell -ExecutionPolicy Bypass -File tools/uninstall_windows_task.ps1
```

---

## Incident Video & Metadata Storage

When an intrusion event occurs while armed, files are saved under `data/incidents/`:

```
data/incidents/
└── 2026-11-04/
    └── camera_01/
        ├── incident_20261104_223000.mp4
        └── incident_20261104_223000.json
```

---

## Phase 2: Local Security Agent (Windows REST API)

ShopGuard AI Phase 2 includes a production-oriented headless **Local Security Agent** running as an asynchronous FastAPI REST service. It enables complete programmatic control and status monitoring without requiring an OpenCV display window.

### 1. Launching the Local Security Agent
To run the agent with your laptop's built-in webcam (no CCTV hardware or RTSP URL needed):
```powershell
.\venv\Scripts\python.exe tools/run_agent.py --webcam
```
Or run with configured physical CCTV RTSP cameras:
```powershell
.\venv\Scripts\python.exe tools/run_agent.py
```
Or specify a custom host and port:
```powershell
.\venv\Scripts\python.exe tools/run_agent.py --host 127.0.0.1 --port 8000
```

### 2. Available Endpoints
- `GET /api/status`: High-level summary of service status, security state, camera counts, and active incidents.
- `GET /api/cameras`: Camera connection status, framerate, resolution, and masked stream URLs.
- `GET /api/security/state`: Current arm state, prerequisites check, active zone count, and rejection reasons.
- `POST /api/security/arm`: Authenticated command to arm the system.
- `POST /api/security/disarm`: Authenticated command to disarm the system.
- `GET /api/incidents`: Paginated list of recorded intrusion incidents.
- `GET /api/incidents/{incident_id}`: Detailed metadata JSON for a specific incident.
- `GET /api/health`: Hardware, storage, stream health, and AI detector diagnostic metrics.
- `GET /api/system/info`: Host operating system and hardware resource statistics.

### 3. Interactive Documentation
With the agent running, open your web browser to:
```
http://127.0.0.1:8000/docs
```
Explore the interactive Swagger UI and test REST endpoints directly.

For comprehensive setup details and Android client integration specifications, consult:
- [`PHASE_2_IMPLEMENTATION_REPORT.md`](file:///c:/Users/Miqdad%20Haider/Desktop/ShopGuard%20AI/PHASE_2_IMPLEMENTATION_REPORT.md)
- [`API_DOCUMENTATION.md`](file:///c:/Users/Miqdad%20Haider/Desktop/ShopGuard%20AI/API_DOCUMENTATION.md)
- [`LOCAL_AGENT_SETUP.md`](file:///c:/Users/Miqdad%20Haider/Desktop/ShopGuard%20AI/LOCAL_AGENT_SETUP.md)

---

## Running the Automated Test Suite

Run pytest inside the virtual environment:
```powershell
.\venv\Scripts\pytest -v
```

All 73 automated unit, integration, night-time false-positive, recorded-video, laptop webcam, and Phase 2 Local Security Agent REST API tests execute locally without needing internet or real CCTV hardware.
