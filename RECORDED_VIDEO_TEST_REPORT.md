# ShopGuard AI — Recorded Video Testing Mode Verification Report

**Project:** ShopGuard AI  
**Phase:** 1 — Python AI CCTV Security Engine  
**Feature:** Complete Recorded-Video Testing Mode & Simulation Harness  
**Target OS:** Windows 10 / 11 (64-bit)  
**Execution Environment:** Shop local Windows PC (CPU execution primary; optional CUDA GPU)  
**Verification Date:** November 2026  
**Status:** **100% IMPLEMENTED & VERIFIED (41/41 Automated Tests Passing)**

---

## 1. Executive Summary

This report documents the design, implementation, and automated test verification of the **Recorded Video Testing Mode** for **ShopGuard AI Phase 1**.

The testing mode enables shop owners, security technicians, and QA engineers to thoroughly evaluate AI person detection, ByteTrack object tracking, restricted-zone containment geometry, armed-state gating, event cooldowns, and pre/post-event incident video recording on pre-recorded CCTV shop footage (`.mp4`, `.avi`, `.mkv`, etc.) without requiring physical IP camera hardware on-site.

### Core Architectural Guarantees
1. **100% Module Reuse:** Built entirely by reusing existing core modules (`PersonDetector`, `ObjectTracker`, `ZoneManager`, `IntrusionDetector`, `VideoBuffer`, `IncidentRecorder`, `SecurityController`, `FeedVisualizer`). No duplicate detection or tracking logic was created.
2. **Explicit Non-RTSP Identification:** The video stream, visual overlay, console logs, and incident JSON metadata explicitly identify the source as `RECORDED VIDEO (NOT LIVE CCTV)` and clearly document `rtsp_verified: false`.
3. **Zero Breakage of Live RTSP Functionality:** All existing RTSP camera streaming, multi-camera thread isolation, TCP reachability pre-probing, and state machine controls remain 100% intact.
4. **Test Suite Expansion:** The automated test suite was expanded from 34 to **41 tests**, with all 41 tests passing cleanly in **17.05 seconds**.

---

## 2. Requirement Compliance Matrix

| # | Requirement | Implementation Details | Status |
|---|---|---|:---:|
| 1 | **Video File Selection** | Supports `.mp4`, `.avi`, `.mkv`, `.mov`, `.wmv`. Provides native Windows GUI file picker dialog via `tkinter.filedialog`, CLI parameter `--video <path>`, and interactive terminal prompt fallback. | **PASS** |
| 2 | **Frame-by-Frame Processing** | Reads frames sequentially at native video FPS. Simulated timestamps (`start_time + frame_idx / fps`) ensure deterministic persistence and cooldown behavior regardless of CPU inference speed. | **PASS** |
| 3 | **Zone Configuration Reuse** | Directly utilizes `ZoneManager` and normalized polygon definitions (`config/zones.json` or `config/zones.example.json`). Automatically adapts active zones for recorded camera evaluation. | **PASS** |
| 4 | **Interactive Arm / Disarm** | Real-time keyboard controls in OpenCV window: Press `A` to run prerequisites check and switch to `ARMED`; press `D` to switch to `DISARMED`. Also accessible via programmatic API. | **PASS** |
| 5 | **Armed-State Gating** | When `DISARMED`, intrusion detection is suppressed (0 incidents generated). When `ARMED`, bottom-center foot contact points crossing zone boundaries trigger incidents. | **PASS** |
| 6 | **Persistence & Cooldown Reuse** | Reuses `IntrusionDetector` logic: requires configurable entry persistence (default 2.0s) and enforces 30-second event cooldown per `(camera_id, zone_id, track_id)` key. | **PASS** |
| 7 | **Incident Clip & Metadata Saving** | In-memory circular `VideoBuffer` extracts 5s pre-event frames; asynchronous `IncidentRecorder` captures 10s post-event frames, writing playable MP4 videos and structured JSON metadata. | **PASS** |
| 8 | **Visual Monitoring Overlay** | Enhanced `FeedVisualizer` renders green bounding boxes, ByteTrack IDs, motion trajectory trails, yellow/red restricted zone polygons, top status banner, and bottom alert banner. | **PASS** |
| 9 | **Interactive Playback Controls** | Spacebar (Pause/Resume), `R` (Restart from frame 0), `+`/`-` (Playback speed: 0.25x to 4.0x), `N` (Step forward 1 frame when paused), `Q`/ESC (Exit). | **PASS** |
| 10 | **Clear Source Identification** | Prominent purple HUD banner `[RECORDED VIDEO TEST - NOT LIVE CCTV]`, stream tag `[RECORDED FILE]`, and incident JSON metadata field `source_type: "recorded_video"`. | **PASS** |
| 11 | **No False RTSP Claims** | Explicit console warnings and metadata flags: `rtsp_verified: false` and `simulation_mode: true`. Never claims RTSP connectivity was tested. | **PASS** |
| 12 | **Existing RTSP Integrity** | All live RTSP classes (`StreamReader`, `CameraManager`) and existing 34 unit/integration tests remain untouched and functional. | **PASS** |
| 13 | **Automated Tests Added** | Added `tests/test_recorded_video.py` containing 7 dedicated unit and end-to-end tests covering loading, disarmed suppression, armed detection, controls, and recording. | **PASS** |
| 14 | **README Documentation** | Updated `README.md` with complete usage instructions, CLI arguments, and keyboard shortcuts for Windows. | **PASS** |

---

## 3. Architecture & Module Reuse

The recorded video testing mode is packaged cleanly under `shopguard/testing/` and exposed via two primary interfaces:
1. **Interactive CLI Tool:** [`tools/test_recorded_video.py`](file:///c:/Users/Miqdad%20Haider/Desktop/ShopGuard%20AI/tools/test_recorded_video.py)
2. **Main Application Entry Point:** [`main.py --test-video [path]`](file:///c:/Users/Miqdad%20Haider/Desktop/ShopGuard%20AI/main.py)

```
RecordedVideoTester (shopguard/testing/recorded_video_tester.py)
│
├── Input Resolution:
│   ├── Windows File Picker Dialog (Tkinter)
│   ├── CLI Argument (--video / --test-video)
│   └── Terminal Prompt & Synthetic Fallback
│
├── Frame-by-Frame Execution:
│   ├── cv2.VideoCapture(video_path) -> (w, h, total_frames, fps)
│   ├── Frame Pacing & Deterministic Simulated Time (frame_idx / fps)
│   └── Keyboard Input Dispatcher (OpenCV waitKey)
│
└── Reused Core Modules:
    ├── PersonDetector       ──► YOLO11n CPU Inference (Class 0: person)
    ├── ObjectTracker        ──► ByteTrack Trajectory Tracking & Track IDs
    ├── ZoneManager          ──► Normalized Polygons & Ray-Casting Inclusion
    ├── IntrusionDetector    ──► Foot-Contact Calculation, Persistence & Cooldown
    ├── VideoBuffer          ──► Circular In-Memory Pre-Event Frame Buffer
    ├── IncidentRecorder     ──► Asynchronous MP4 Video & JSON Metadata Writer
    ├── SecurityController   ──► 5-State Machine (DISARMED ◄► ARMED) & Validation
    └── FeedVisualizer       ──► HUD Overlay with Recorded Video Warning Banners
```

---

## 4. Playback Controls & HUD UX Specification

### 4.1 Interactive Keyboard Shortcuts
When running with GUI enabled (`show_gui=True`), focus on the OpenCV video window to use the following controls:

| Key | Function | Description |
|---|---|---|
| **`Space`** | **Pause / Resume** | Halts or resumes frame processing. While paused, current frame and annotations remain visible. |
| **`A`** | **Arm System** | Executes pre-arm validation checks and transitions state to `ARMED`. Intrusion detection becomes active. |
| **`D`** | **Disarm System** | Transitions state to `DISARMED`. Video continues playing; intrusion alerts and recordings are suppressed. |
| **`R`** | **Restart** | Rewinds video capture to frame 0, clears rolling buffer, and resets tracking/persistence states. |
| **`+` / `=` / `]`** | **Speed Up** | Cycles through speed presets: `0.25x` -> `0.5x` -> `1.0x` -> `1.5x` -> `2.0x` -> `4.0x`. |
| **`-` / `_` / `[`** | **Slow Down** | Decreases playback speed preset. |
| **`N` / `.`** | **Step Frame** | When paused, advances playback by exactly 1 frame for precise spatial inspection. |
| **`Q` / `ESC`** | **Quit** | Gracefully flushes active recording sessions, closes OpenCV windows, and prints execution summary. |

### 4.2 Visual HUD Display Elements
- **Top Header Bar:**
  - `STATE: ARMED` / `STATE: DISARMED` (Color-coded badge: Green for Armed, Slate Gray for Disarmed).
  - `RECORDED: <filename> [RECORDED FILE]` (Distinct amber connection badge).
  - `[RECORDED VIDEO TEST - NOT LIVE CCTV]` (Prominent purple security warning tag).
  - `FPS: <effective_fps>` (Measured rendering throughput).
- **Sub-Header Playback Status:**
  - `PLAYING` / `PAUSED` | `SPEED: 1.00x` | `FRAME: 45/300 (4.5s/30.0s)`.
- **Bottom Navigation Hint:**
  - `Controls: [Space] Pause/Play | [A] Arm | [D] Disarm | [R] Restart | [+/-] Speed | [N] Step | [Q] Quit`.
- **Bottom Alert Banner (on intrusion):**
  - `ALERT: PERSON_ENTERED_RESTRICTED_ZONE | Zone: Cash Counter | Track ID: 1`.

---

## 5. Automated Test Results

The test suite was executed across all 10 test modules in the repository:
```powershell
.\venv\Scripts\pytest -v
```

### Complete Test Execution Log:
```
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.2.0, pluggy-1.7.0
rootdir: C:\Users\Miqdad Haider\Desktop\ShopGuard AI

tests/test_camera.py::test_multi_camera_independence PASSED              [  2%]
tests/test_camera.py::test_disabled_camera_is_ignored PASSED             [  4%]
tests/test_diagnostic.py::test_rtsp_diagnostic_url_syntax_validation PASSED [  7%]
tests/test_diagnostic.py::test_rtsp_diagnostic_masks_credentials PASSED  [  9%]
tests/test_e2e_scenarios.py::test_scenario_1_empty_shop PASSED           [ 12%]
tests/test_e2e_scenarios.py::test_scenario_2_person_outside_restricted_zone PASSED [ 14%]
tests/test_e2e_scenarios.py::test_scenario_3_person_enters_protected_zone PASSED [ 17%]
tests/test_e2e_scenarios.py::test_scenario_4_disarmed_system PASSED      [ 19%]
tests/test_e2e_scenarios.py::test_scenario_5_event_cooldown PASSED       [ 21%]
tests/test_e2e_scenarios.py::test_scenario_6_camera_disconnection PASSED [ 24%]
tests/test_e2e_scenarios.py::test_scenario_7_invalid_configuration PASSED [ 26%]
tests/test_e2e_scenarios.py::test_scenario_8_recording_validation PASSED [ 29%]
tests/test_integration.py::test_full_pipeline_local_video PASSED         [ 31%]
tests/test_intrusion.py::test_disarmed_state_does_not_generate_intrusion PASSED [ 34%]
tests/test_intrusion.py::test_person_outside_restricted_zone_does_not_trigger PASSED [ 36%]
tests/test_intrusion.py::test_person_entering_zone_triggers_after_persistence PASSED [ 39%]
tests/test_intrusion.py::test_duplicate_events_suppressed_and_cooldown_works PASSED [ 41%]
tests/test_intrusion.py::test_camera_disconnection_changes_health_without_theft_incident PASSED [ 43%]
tests/test_night_detection.py::test_pitch_black_with_sensor_noise PASSED [ 46%]
tests/test_night_detection.py::test_headlight_sweep_and_shadows PASSED   [ 48%]
tests/test_night_detection.py::test_window_reflection_outside_protected_zone PASSED [ 51%]
tests/test_recorded_video.py::test_recorded_video_load_and_metadata PASSED [ 53%]
tests/test_recorded_video.py::test_recorded_video_disarmed_suppression PASSED [ 56%]
tests/test_recorded_video.py::test_recorded_video_armed_intrusion_detection PASSED [ 58%]
tests/test_recorded_video.py::test_recorded_video_dynamic_arm_disarm_controls PASSED [ 60%]
tests/test_recorded_video.py::test_recorded_video_playback_controls PASSED [ 63%]
tests/test_recorded_video.py::test_recorded_video_incident_recording_and_metadata PASSED [ 65%]
tests/test_recorded_video.py::test_select_video_file_fallback PASSED     [ 68%]
tests/test_recording.py::test_video_buffer_rolling_and_retrieval PASSED  [ 70%]
tests/test_recording.py::test_incident_metadata_and_video_saved PASSED   [ 73%]
tests/test_security.py::test_system_starts_in_disarmed_state PASSED      [ 75%]
tests/test_security.py::test_valid_camera_and_zone_configuration_allows_arming PASSED [ 78%]
tests/test_security.py::test_missing_camera_prevents_full_arming PASSED  [ 80%]
tests/test_security.py::test_missing_zones_prevents_arming PASSED        [ 82%]
tests/test_security.py::test_disarming_transitions_to_disarmed PASSED    [ 85%]
tests/test_security.py::test_invalid_configuration_reporting PASSED      [ 87%]
tests/test_security.py::test_partial_and_offline_health_updates PASSED   [ 90%]
tests/test_zones.py::test_zone_point_containment PASSED                  [ 92%]
tests/test_zones.py::test_bottom_center_calculation PASSED               [ 95%]
tests/test_zones.py::test_invalid_polygon_rejection PASSED               [ 97%]
tests/test_zones.py::test_zone_manager_load_and_save PASSED              [100%]

============================= 41 passed in 17.05s =============================
```

### Dedicated Recorded Video Test Suite Details (`tests/test_recorded_video.py`):
1. **`test_recorded_video_load_and_metadata`**: Validates resolution extraction (320x240), frame count (30), FPS (10.0), and duration (3.0s).
2. **`test_recorded_video_disarmed_suppression`**: Confirms that in `DISARMED` mode, zero incidents are generated even when a person is present inside the protected zone.
3. **`test_recorded_video_armed_intrusion_detection`**: Confirms that in `ARMED` mode, a person persisting in the zone generates an incident event with proper zone name and confidence.
4. **`test_recorded_video_dynamic_arm_disarm_controls`**: Confirms dynamic runtime transitions `DISARMED` -> `ARMING` -> `ARMED` -> `DISARMED`.
5. **`test_recorded_video_playback_controls`**: Confirms pause, resume, speed adjustment (0.5x, 2.0x), restart to frame 0, and single-frame step.
6. **`test_recorded_video_incident_recording_and_metadata`**: Confirms that incident videos (`.mp4`) and audit metadata (`.json`) are written with `source_type: "recorded_video"`, `simulation_mode: true`, and `rtsp_verified: false`.
7. **`test_select_video_file_fallback`**: Confirms video file path resolution and fallback mechanics.

---

## 6. Generated Incident Artifact Audit

During recorded video simulation, incidents are recorded to `data/incidents/<date>/<camera_id>/`. Below is an audited JSON metadata sample generated during test execution:

```json
{
  "incident_id": "0ac2f41b-ba52-4411-a8ce-138472911b30",
  "camera_id": "cam_recorded",
  "camera_name": "Recorded: recorded_sample.mp4",
  "event_type": "PERSON_ENTERED_RESTRICTED_ZONE",
  "event_timestamp": "2026-11-05T17:43:26.120400",
  "track_id": 3,
  "detection_confidence": 0.92,
  "confidence": 0.92,
  "zone_id": "zone_counter",
  "zone_name": "Cash Counter",
  "video_filename": "incident_20261105_174326.mp4",
  "review_status": "UNREVIEWED",
  "duration_seconds": 2.9,
  "total_frames": 30,
  "source_type": "recorded_video",
  "simulation_mode": true,
  "rtsp_verified": false
}
```

The accompanying `.mp4` file was verified using OpenCV `cv2.VideoCapture` and confirmed to be openable, readable, and properly encoded with standard `mp4v` codec parameters.

---

## 7. Windows Operational Guide

### 7.1 Interactive Run with File Dialog
To launch testing with a Windows GUI file picker:
```powershell
.\venv\Scripts\python.exe tools/test_recorded_video.py
```

### 7.2 Run with Direct File Path
```powershell
.\venv\Scripts\python.exe tools/test_recorded_video.py --video "C:\CCTV_Clips\checkout_night.mp4"
```

### 7.3 Start in Armed Mode with 2x Playback Speed
```powershell
.\venv\Scripts\python.exe tools/test_recorded_video.py --video "C:\CCTV_Clips\checkout_night.mp4" --auto-arm --speed 2.0
```

### 7.4 Headless Benchmarking
```powershell
.\venv\Scripts\python.exe tools/test_recorded_video.py --video "C:\CCTV_Clips\checkout_night.mp4" --no-gui --auto-arm
```

---

## 8. Conclusion

The Recorded Video Testing Mode is fully implemented, strictly adheres to all safety and architectural constraints, reuses 100% of the existing Phase 1 detection and tracking pipeline, and passes all 41 automated tests. The system is verified and ready for commercial testing on Windows shop environments.
