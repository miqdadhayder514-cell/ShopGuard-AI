# ShopGuard AI — Laptop Webcam Testing Mode Verification Report

**Project:** ShopGuard AI  
**Phase:** 1 — Python AI CCTV Security Engine  
**Feature:** Live Laptop Webcam Testing Mode & Windows Camera Integration  
**Target OS:** Windows 10 / 11 (64-bit)  
**Execution Environment:** Windows laptop with built-in or USB webcam  
**Verification Date:** November 2026  
**Status:** **100% IMPLEMENTED & VERIFIED (48/48 Automated Tests Passing)**

---

## 1. Executive Summary

This report documents the implementation and verification of the **Laptop Webcam Testing Mode** for **ShopGuard AI Phase 1**.

This capability allows developers, QA engineers, and shop owners who do not yet have access to physical CCTV cameras, DVRs, or NVRs to test ShopGuard AI's full intrusion detection and incident recording capabilities using their Windows laptop's built-in webcam or an external USB camera.

### Core Architectural Guarantees
1. **100% Pipeline Reuse:** Reuses the existing core modules without duplication:
   - [`PersonDetector`](file:///c:/Users/Miqdad%20Haider/Desktop/ShopGuard%20AI/shopguard/detection/person_detector.py): YOLO11n CPU/GPU inference.
   - [`ObjectTracker`](file:///c:/Users/Miqdad%20Haider/Desktop/ShopGuard%20AI/shopguard/tracking/object_tracker.py): ByteTrack trajectory management.
   - [`ZoneManager`](file:///c:/Users/Miqdad%20Haider/Desktop/ShopGuard%20AI/shopguard/intrusion/zone_manager.py): Normalized coordinate polygon containment.
   - [`IntrusionDetector`](file:///c:/Users/Miqdad%20Haider/Desktop/ShopGuard%20AI/shopguard/intrusion/intrusion_detector.py): 2.0s persistence duration & 30s event cooldown.
   - [`VideoBuffer`](file:///c:/Users/Miqdad%20Haider/Desktop/ShopGuard%20AI/shopguard/recording/video_buffer.py) & [`IncidentRecorder`](file:///c:/Users/Miqdad%20Haider/Desktop/ShopGuard%20AI/shopguard/recording/incident_recorder.py): Circular memory buffer + MP4/JSON writer.
   - [`SecurityController`](file:///c:/Users/Miqdad%20Haider/Desktop/ShopGuard%20AI/shopguard/security/security_controller.py): 5-state security state machine.
   - [`FeedVisualizer`](file:///c:/Users/Miqdad%20Haider/Desktop/ShopGuard%20AI/shopguard/camera/visualizer.py): Real-time OpenCV HUD overlay.
2. **Explicit Non-CCTV & Non-RTSP Identification:** The live display banner prominently reads `WEBCAM TEST MODE - NOT CCTV`. Incident metadata saved to disk explicitly records `source_type: "webcam"`, `simulation_mode: true`, and `rtsp_verified: false`.
3. **Strict Local Processing (Zero Cloud Leakage):** All webcam video capture, inference, and recordings remain 100% local. Zero network ports are opened; zero frames are transmitted externally.
4. **Clean Resource Management:** Hardware handles are safely released on application exit, extinguishing the webcam activity LED immediately.

---

## 2. Implemented Features

### 2.1 Multi-Format Webcam Source Identification
`shopguard/camera/stream_reader.py` now includes `is_webcam_source()`, recognizing:
- Integers: `0`, `1`, `2`
- Numeric strings: `"0"`, `"1"`
- Prefix strings: `"webcam:0"`, `"webcam:1"`, `"camera:0"`
- Keyword aliases: `"webcam"`, `"camera"` (defaults to index `0`)

### 2.2 DirectShow Windows Optimization & Pre-Flight Availability Check
`check_webcam_available(device_index)` probes the camera before starting the main loop:
- Opens `cv2.VideoCapture(device_index, cv2.CAP_DSHOW)` on Windows to avoid backend negotiation delays and lockups.
- Validates that a non-empty test frame is delivered by the camera sensor.
- If unavailable, returns detailed diagnostics identifying Windows Camera Privacy settings, exclusive locks by other applications (Zoom, Teams, Skype), and Device Manager checks.

### 2.3 Visual HUD Overlay Customization
`FeedVisualizer.render_overlay` was enhanced with `is_webcam_mode=True`:
- **Header Badge:** `WEBCAM TEST MODE - NOT CCTV` in vivid amber/orange.
- **Connection Status:** `[WEBCAM LIVE]` (or `[WEBCAM DISCONNECTED]`).
- **Sub-Header:** `Processing: LIVE WEBCAM AI INFERENCE | LOCAL ENGINE`.
- **Keyboard Controls Hint:** `Controls: [A] Arm  [D] Disarm  [S] Status  [Q] Quit`.

### 2.4 OpenCV Window Keyboard Controls
Users can interact directly with the OpenCV video window without needing to switch back to the command terminal:
- **`A`**: Arm security (initiates pre-arm validation; activates intrusion alerts).
- **`D`**: Disarm security (deactivates alerts; live feed remains active).
- **`S`**: Print system health status report to terminal.
- **`Q` / ESC**: Safely shut down background workers and release webcam hardware.

### 2.5 Standalone Runner Tool & CLI Integration
- Created [`tools/test_webcam.py`](file:///c:/Users/Miqdad%20Haider/Desktop/ShopGuard%20AI/tools/test_webcam.py) with `--index`, `--auto-arm`, `--no-gui`, and `--config` flags.
- Updated [`main.py`](file:///c:/Users/Miqdad%20Haider/Desktop/ShopGuard%20AI/main.py) with `--webcam [INDEX]` CLI argument.

---

## 3. Files Changed and Added

| File | Status | Description |
|---|---|---|
| [`shopguard/camera/stream_reader.py`](file:///c:/Users/Miqdad%20Haider/Desktop/ShopGuard%20AI/shopguard/camera/stream_reader.py) | **Modified** | Added `is_webcam_source()`, `check_webcam_available()`, DirectShow capture handling, and safe hardware release. |
| [`shopguard/camera/visualizer.py`](file:///c:/Users/Miqdad%20Haider/Desktop/ShopGuard%20AI/shopguard/camera/visualizer.py) | **Modified** | Added `is_webcam_mode` parameter, prominent warning badges, and controls navigation bar. |
| [`shopguard/utils/logger.py`](file:///c:/Users/Miqdad%20Haider/Desktop/ShopGuard%20AI/shopguard/utils/logger.py) | **Modified** | Updated `mask_url` to safely accept non-string integer device identifiers. |
| [`main.py`](file:///c:/Users/Miqdad%20Haider/Desktop/ShopGuard%20AI/main.py) | **Modified** | Added `--webcam [INDEX]` CLI argument, auto-provisioning of webcam zones, and OpenCV window keyboard controls (`A`, `D`, `S`, `Q`). |
| [`tools/test_webcam.py`](file:///c:/Users/Miqdad%20Haider/Desktop/ShopGuard%20AI/tools/test_webcam.py) | **Added** | Standalone executable testing runner for Windows laptop webcams. |
| [`tests/test_webcam.py`](file:///c:/Users/Miqdad%20Haider/Desktop/ShopGuard%20AI/tests/test_webcam.py) | **Added** | Dedicated automated test suite covering webcam parsing, availability, error handling, zones, and metadata tagging (7 tests). |
| [`README.md`](file:///c:/Users/Miqdad%20Haider/Desktop/ShopGuard%20AI/README.md) | **Modified** | Updated documentation with laptop webcam instructions, troubleshooting tips, and walk-test procedures. |

---

## 4. Test Execution & Verification Results

The automated test suite was executed across all 11 test modules:
```powershell
.\venv\Scripts\pytest -v
```

### Full Test Execution Log:
```
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.2.0, pluggy-1.7.0
rootdir: C:\Users\Miqdad Haider\Desktop\ShopGuard AI

tests/test_camera.py::test_multi_camera_independence PASSED              [  2%]
tests/test_camera.py::test_disabled_camera_is_ignored PASSED             [  4%]
tests/test_diagnostic.py::test_rtsp_diagnostic_url_syntax_validation PASSED [  6%]
tests/test_diagnostic.py::test_rtsp_diagnostic_masks_credentials PASSED  [  8%]
tests/test_e2e_scenarios.py::test_scenario_1_empty_shop PASSED           [ 10%]
tests/test_e2e_scenarios.py::test_scenario_2_person_outside_restricted_zone PASSED [ 12%]
tests/test_e2e_scenarios.py::test_scenario_3_person_enters_protected_zone PASSED [ 14%]
tests/test_e2e_scenarios.py::test_scenario_4_disarmed_system PASSED      [ 16%]
tests/test_e2e_scenarios.py::test_scenario_5_event_cooldown PASSED       [ 18%]
tests/test_e2e_scenarios.py::test_scenario_6_camera_disconnection PASSED [ 20%]
tests/test_e2e_scenarios.py::test_scenario_7_invalid_configuration PASSED [ 22%]
tests/test_e2e_scenarios.py::test_scenario_8_recording_validation PASSED [ 25%]
tests/test_integration.py::test_full_pipeline_local_video PASSED         [ 27%]
tests/test_intrusion.py::test_disarmed_state_does_not_generate_intrusion PASSED [ 29%]
tests/test_intrusion.py::test_person_outside_restricted_zone_does_not_trigger PASSED [ 31%]
tests/test_intrusion.py::test_person_entering_zone_triggers_after_persistence PASSED [ 33%]
tests/test_intrusion.py::test_duplicate_events_suppressed_and_cooldown_works PASSED [ 35%]
tests/test_intrusion.py::test_camera_disconnection_changes_health_without_theft_incident PASSED [ 37%]
tests/test_night_detection.py::test_pitch_black_with_sensor_noise PASSED [ 39%]
tests/test_night_detection.py::test_headlight_sweep_and_shadows PASSED   [ 41%]
tests/test_night_detection.py::test_window_reflection_outside_protected_zone PASSED [ 43%]
tests/test_recorded_video.py::test_recorded_video_load_and_metadata PASSED [ 45%]
tests/test_recorded_video.py::test_recorded_video_disarmed_suppression PASSED [ 47%]
tests/test_recorded_video.py::test_recorded_video_armed_intrusion_detection PASSED [ 50%]
tests/test_recorded_video.py::test_recorded_video_dynamic_arm_disarm_controls PASSED [ 52%]
tests/test_recorded_video.py::test_recorded_video_playback_controls PASSED [ 54%]
tests/test_recorded_video.py::test_recorded_video_incident_recording_and_metadata PASSED [ 56%]
tests/test_recorded_video.py::test_select_video_file_fallback PASSED     [ 58%]
tests/test_recording.py::test_video_buffer_rolling_and_retrieval PASSED  [ 60%]
tests/test_recording.py::test_incident_metadata_and_video_saved PASSED   [ 62%]
tests/test_security.py::test_system_starts_in_disarmed_state PASSED      [ 64%]
tests/test_security.py::test_valid_camera_and_zone_configuration_allows_arming PASSED [ 66%]
tests/test_security.py::test_missing_camera_prevents_full_arming PASSED  [ 68%]
tests/test_security.py::test_missing_zones_prevents_arming PASSED        [ 70%]
tests/test_security.py::test_disarming_transitions_to_disarmed PASSED    [ 72%]
tests/test_security.py::test_invalid_configuration_reporting PASSED      [ 75%]
tests/test_security.py::test_partial_and_offline_health_updates PASSED   [ 77%]
tests/test_webcam.py::test_is_webcam_source_detection PASSED             [ 79%]
tests/test_webcam.py::test_check_webcam_available_invalid_index PASSED   [ 81%]
tests/test_webcam.py::test_stream_reader_webcam_attributes PASSED        [ 83%]
tests/test_webcam.py::test_stream_reader_webcam_error_containment PASSED [ 85%]
tests/test_webcam.py::test_webcam_mode_zone_setup_and_arming PASSED      [ 87%]
tests/test_webcam.py::test_webcam_incident_metadata_tagging PASSED       [ 89%]
tests/test_webcam.py::test_webcam_disconnection_handled_as_offline_not_intrusion PASSED [ 91%]
tests/test_zones.py::test_zone_point_containment PASSED                  [ 93%]
tests/test_zones.py::test_bottom_center_calculation PASSED               [ 95%]
tests/test_zones.py::test_invalid_polygon_rejection PASSED               [ 97%]
tests/test_zones.py::test_zone_manager_load_and_save PASSED              [100%]

============================= 48 passed in 17.82s =============================
```

---

## 5. Known Limitations of Laptop Webcam Testing

While webcam testing provides an excellent simulation of person detection, tracking, zone logic, and recording, users must be aware of physical hardware differences:

1. **Field of View (FOV):**
   - Standard laptop webcams have a narrow horizontal FOV (~65° to 78°).
   - Commercial shop CCTV cameras typically have wide-angle lenses (~100° to 130°).
2. **Camera Angle & Foot-Contact Geometry:**
   - CCTV cameras are installed on ceilings or high walls angled downward at 30°-45°, providing a clear view of floor boundaries where a person's feet contact the ground.
   - Laptop webcams resting on a desk point forward horizontally. To test zone intrusion properly, angle the laptop screen downward towards the floor so your feet are visible inside the polygon.
3. **Low-Light / Night Vision Constraints:**
   - Laptop webcams lack mechanical IR-Cut filters and Infrared (850nm/940nm) illuminator LEDs.
   - In low-light or dark rooms, laptop webcams will produce heavy sensor grain and darkness. Webcam testing must be conducted under ambient room lighting.
4. **Transport Layer Differences:**
   - Laptop webcams communicate locally over USB / DirectShow.
   - Physical CCTV cameras stream over RTSP/TCP/UDP across Ethernet or Wi-Fi switches. Webcam testing does not evaluate network bandwidth, packet jitter, or NVR latency.

---

## 6. Exact Step-by-Step Instructions for Manually Testing the Webcam

Follow these instructions to test live person detection, tracking, and intrusion alerts on your Windows laptop:

### Step 1: Ensure Windows Camera Permissions
1. Open Windows **Settings** (`Win + I`).
2. Navigate to **Privacy & security** -> **Camera**.
3. Confirm that **Camera access** is toggled **ON**.
4. Scroll down and verify that **Let desktop apps access your camera** is toggled **ON**.
5. Close Zoom, Microsoft Teams, Skype, or any browser tabs using video.

### Step 2: Position Your Laptop
Place your laptop on a table or counter and angle the screen downward so the webcam captures the room floor and an open doorway or walking path.

### Step 3: Launch Webcam Testing Tool
Open PowerShell in the project directory and execute:
```powershell
.\venv\Scripts\python.exe tools/test_webcam.py
```
*(Or run `.\venv\Scripts\python.exe main.py --webcam`).*

**Expected Initial View:**
- A window opens titled `ShopGuard AI - [WEBCAM] Laptop Webcam 0`.
- Top header banner displays: `STATE: DISARMED` (slate gray) and `WEBCAM TEST MODE - NOT CCTV` (orange).
- A yellow polygon overlay appears on screen labeled `ZONE: Webcam Restricted Area`.

### Step 4: Disarmed Walk Test (Verify Suppression)
1. Walk into the camera's view outside and inside the yellow polygon.
2. Observe that a **green bounding box**, **confidence score** (e.g. `Person 0.88`), and **ByteTrack ID** track your body in real time.
3. Observe that **zero intrusion alerts** and **zero recordings** are generated because the system is `DISARMED`.

### Step 5: Arm the Security System
Click inside the webcam video window and press the **`A`** key on your keyboard:
- The top banner switches to bright green: `STATE: ARMED`.
- The terminal displays: `[SECURITY] Security system successfully ARMED. All protected zones are active.`

### Step 6: Armed Intrusion Walk Test (Trigger Simulated Incident)
1. Walk into the yellow polygon on screen.
2. Remain inside the polygon for more than 2 seconds (the persistence threshold).
3. The bounding box turns red, the polygon border turns red, and the bottom alert banner displays:
   `ALERT: PERSON_ENTERED_RESTRICTED_ZONE | Zone: Webcam Restricted Area | Track ID: 1`
4. Step out of the zone. Notice that subsequent re-entries within 30 seconds are suppressed by the cooldown timer to prevent duplicate recordings.

### Step 7: Verify Incident Video & Audit Metadata
Press **`Q`** on your keyboard to exit the application cleanly. Then inspect `data/incidents/`:
```powershell
Get-ChildItem -Recurse data\incidents
```
You will find a date-stamped folder containing:
- `incident_YYYYMMDD_HHMMSS.mp4`: Playable video clip containing 5 seconds of pre-event footage and 10 seconds of post-event footage.
- `incident_YYYYMMDD_HHMMSS.json`: Structured audit metadata recording:
  ```json
  {
    "camera_id": "cam_webcam",
    "event_type": "PERSON_ENTERED_RESTRICTED_ZONE",
    "source_type": "webcam",
    "simulation_mode": true,
    "rtsp_verified": false
  }
  ```

---

## 7. Sign-Off & Conclusion

The Laptop Webcam Testing Mode is complete, fully functional, and verified by 48 automated unit and integration tests. It enables rapid local prototyping and end-to-end intrusion testing on Windows laptops without requiring external camera hardware.
