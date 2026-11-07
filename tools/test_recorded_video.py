"""
ShopGuard AI - Recorded Video Testing Tool
Run and evaluate ShopGuard AI intrusion detection on pre-recorded CCTV shop footage.
"""

import argparse
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shopguard.testing.recorded_video_tester import RecordedVideoTester, select_video_file
from shopguard.security.security_controller import SecurityState


def main():
    parser = argparse.ArgumentParser(
        description="ShopGuard AI - Recorded Video Testing Runner (Windows CCTV Simulation)"
    )
    parser.add_argument(
        "--video",
        default=None,
        help="Path to recorded video file (.mp4, .avi, etc.). If omitted, opens a file selection dialog.",
    )
    parser.add_argument(
        "--no-gui",
        action="store_true",
        help="Run without displaying OpenCV visualizer windows (headless test mode).",
    )
    parser.add_argument(
        "--auto-arm",
        action="store_true",
        help="Automatically arm the security system at the start of video playback.",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Continuously loop the video playback.",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Initial playback speed multiplier (e.g. 0.5, 1.0, 2.0).",
    )
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="Path to configuration YAML file.",
    )
    parser.add_argument(
        "--zones",
        default=None,
        help="Optional path to custom zones JSON file.",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Maximum number of frames to process before terminating.",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=None,
        help="Override YOLO person detection confidence threshold (e.g. 0.25).",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=None,
        help="Inference image size (e.g. 640, 960, 1280).",
    )
    parser.add_argument(
        "--tiled",
        action="store_true",
        help="Enable tiled / sliced inference for high-res video footage.",
    )
    parser.add_argument(
        "--min-height",
        type=int,
        default=None,
        help="Minimum person bounding box height in pixels to accept.",
    )
    parser.add_argument(
        "--diagnostics",
        action="store_true",
        help="Render real-time inference diagnostics and rejection HUD.",
    )

    args = parser.parse_args()

    print("=" * 70)
    print("      SHOPGUARD AI — RECORDED VIDEO TESTING MODE")
    print("=" * 70)
    print("  * Evaluates AI person detection, ByteTrack tracking, and zone intrusion")
    print("  * Completely local offline execution; zero cloud transmission")
    print("  * IMPORTANT: RTSP connectivity is NOT tested in this mode")
    print("=" * 70)

    # 1. Resolve video file path
    video_path = select_video_file(args.video)
    if not os.path.isfile(video_path):
        print(f"\n[ERROR] Video file not found: {video_path}")
        sys.exit(1)

    print(f"\n[TARGET] Selected video file: {video_path}")
    print(f"[MODE] GUI: {'DISABLED' if args.no_gui else 'ENABLED'}")
    print(f"[SECURITY] Initial State: {'ARMED' if args.auto_arm else 'DISARMED'}")
    print("\nKeyboard Controls during playback (focus on the video window):")
    print("  [Space]   : Pause / Resume playback")
    print("  [A]       : Arm security system (activates intrusion alerts)")
    print("  [D]       : Disarm security system (monitors without alerts)")
    print("  [R]       : Restart playback from frame 0")
    print("  [+] / [-] : Speed up / Slow down playback")
    print("  [N]       : Step forward 1 frame (when paused)")
    print("  [Q] / ESC : Exit test runner\n")

    # 2. Initialize and run tester
    initial_state = SecurityState.ARMED if args.auto_arm else SecurityState.DISARMED
    tester = RecordedVideoTester(
        video_path=video_path,
        config_path=args.config,
        zone_file=args.zones,
        initial_state=initial_state,
        show_gui=not args.no_gui,
        auto_arm=args.auto_arm,
        loop=args.loop,
        confidence_override=args.conf,
        imgsz_override=args.imgsz,
        tiled_override=args.tiled,
        min_box_height_override=args.min_height,
        show_diagnostics=args.diagnostics,
    )
    tester.set_speed(args.speed)

    results = tester.run(max_frames=args.max_frames)

    print("\n" + "=" * 70)
    print("               TEST EXECUTION SUMMARY")
    print("=" * 70)
    print(f"  Video Processed       : {results['video_path']}")
    print(f"  Total Frames Analyzed : {results['total_frames_analyzed']}")
    print(f"  Total Detections      : {results['total_detections']}")
    print(f"  Incidents Triggered   : {results['incidents_count']}")
    print(f"  Final Security State  : {results['final_security_state']}")
    print("=" * 70)

    if results["incidents_count"] > 0:
        print("\nRecorded Incidents:")
        for idx, inc in enumerate(results["incidents"], 1):
            print(
                f"  {idx}. [{inc.event_type.value}] Zone: {inc.zone_name} | "
                f"Track ID: {inc.track_id} | Conf: {inc.confidence:.2f} | Time: {inc.timestamp:.1f}s"
            )
        print("\nIncident video clips and JSON metadata saved in 'data/incidents/'.")
    else:
        print("\nNo incidents recorded (system was either DISARMED or no protected zone entries occurred).")

    print("\n[OK] Recorded video test completed.\n")


if __name__ == "__main__":
    main()
