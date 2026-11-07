"""
ShopGuard AI - Live Laptop Webcam Testing Tool
Test and evaluate ShopGuard AI intrusion detection on a Windows laptop built-in or USB webcam.
"""

import argparse
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shopguard.camera.stream_reader import check_webcam_available
from main import ShopGuardEngine


def main():
    parser = argparse.ArgumentParser(
        description="ShopGuard AI - Laptop Webcam Testing Runner (Windows Simulation)"
    )
    parser.add_argument(
        "--index",
        type=int,
        default=0,
        help="Webcam camera device index (default: 0). Use 1 or 2 if multiple webcams are connected.",
    )
    parser.add_argument(
        "--auto-arm",
        action="store_true",
        help="Automatically arm the security system at startup.",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=0.25,
        help="YOLO person detection confidence threshold (default: 0.25 for distant & room webcam detection).",
    )
    parser.add_argument(
        "--persistence",
        type=float,
        default=1.5,
        help="Minimum seconds person must stay inside zone before triggering alert (default: 1.5s).",
    )
    parser.add_argument(
        "--full-zone",
        action="store_true",
        help="Create a single room zone covering the full webcam view (recommended for room/laptop testing).",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=None,
        help="YOLO inference resolution (e.g. 640, 960, 1280).",
    )
    parser.add_argument(
        "--tiled",
        action="store_true",
        help="Enable tiled / sliced inference for high-res stream processing.",
    )
    parser.add_argument(
        "--min-height",
        type=int,
        default=None,
        help="Minimum bounding box height in pixels to accept as person candidate.",
    )
    parser.add_argument(
        "--diagnostics",
        action="store_true",
        help="Display realtime inference metrics and rejected candidates on visualizer HUD.",
    )
    parser.add_argument(
        "--no-gui",
        action="store_true",
        help="Run without displaying OpenCV visualizer windows (headless test mode).",
    )
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="Path to configuration YAML file.",
    )

    args = parser.parse_args()

    print("=" * 72)
    print("           SHOPGUARD AI — LAPTOP WEBCAM TESTING MODE")
    print("=" * 72)
    print("  * Evaluates live AI person detection, ByteTrack tracking, and zone intrusion")
    print("  * Completely local execution; ZERO cloud upload or external transmission")
    print("  * IMPORTANT: Webcam testing simulates intrusion detection but does NOT")
    print("    prove physical RTSP or CCTV compatibility.")
    print("=" * 72)
    print(f"\nActive Configuration:")
    print(f"  * Detection Confidence : {args.conf} (YOLO person threshold)")
    print(f"  * Persistence Time     : {args.persistence}s inside zone to trigger alert")
    print(f"  * Zone Setup           : {'FULL ROOM ZONE (covers entire camera view)' if args.full_zone else 'Default dual zones (Entrance left, Cash Counter right)'}")
    print(f"  * Security Initial     : {'ARMED' if args.auto_arm else 'DISARMED'}")
    print("\nHow to Test Intrusion:")
    print("  1. Press [A] to ARM the security system (or use --auto-arm).")
    print("  2. Step into the blue zone on screen.")
    print("  3. A green bounding box appears around you with your Track ID.")
    print("  4. Look above your box: you will see the live countdown timer:")
    print("     e.g., [Inside Zone: 0.8s / 1.5s]")
    print("  5. Stay in the zone until the countdown completes:")
    print("     -> Screen flashes RED, bottom ALERT banner displays, and MP4 is saved!")
    print("  TIP: If your webcam view doesn't match the default dual boxes, run:")
    print("       python tools/test_webcam.py --full-zone --auto-arm\n")
    print("=" * 72)

    # 1. Probe webcam availability upfront
    print(f"\n[PROBE] Checking availability of webcam device index {args.index}...")
    is_available, status_msg, resolution = check_webcam_available(args.index)

    if not is_available:
        print(f"\n[ERROR] {status_msg}")
        print("\nTroubleshooting tips for Windows laptop webcams:")
        print("  1. Windows Camera Privacy:")
        print("     Open Windows Settings -> Privacy & security -> Camera.")
        print("     Ensure 'Camera access' and 'Let desktop apps access your camera' are turned ON.")
        print("  2. Camera in Use by Another Application:")
        print("     Ensure Zoom, Microsoft Teams, Skype, Discord, OBS, or browser tabs are closed.")
        print("  3. Hardware Shutter / Privacy Switch:")
        print("     Check if your laptop has a physical camera slider or Fn privacy switch.")
        print("  4. Device Index:")
        print(f"     If you have external USB webcams, try index 1: python tools/test_webcam.py --index 1\n")
        sys.exit(1)

    res_str = f"{resolution[0]}x{resolution[1]}" if resolution else "Unknown"
    print(f"[OK] Webcam index {args.index} is available and verified (Resolution: {res_str}).")
    print("\nInteractive Controls:")
    print("  [A]       : Arm security system (activates intrusion alerts and recording)")
    print("  [D]       : Disarm security system (live monitoring without alerts)")
    print("  [S]       : Print diagnostic health status in console")
    print("  [Q] / ESC : Safely exit application and release webcam hardware\n")

    # 2. Launch engine with webcam override
    try:
        engine = ShopGuardEngine(
            config_path=args.config,
            webcam_override=args.index,
            show_gui=not args.no_gui,
            confidence_override=args.conf,
            persistence_override=args.persistence,
            zone_preset="full" if args.full_zone else None,
            imgsz_override=args.imgsz,
            tiled_override=args.tiled,
            min_box_height_override=args.min_height,
            show_diagnostics=args.diagnostics,
        )

        if args.auto_arm:
            success, msg, _ = engine.security_controller.arm()
            if success:
                print(f"[SECURITY] System automatically ARMED: {msg}")
            else:
                print(f"[WARNING] Auto-arm rejected: {msg}")

        engine.run_cli()

    except Exception as e:
        print(f"\n[FATAL] Error running webcam testing engine: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
