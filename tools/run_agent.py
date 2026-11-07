"""
ShopGuard AI - Local Security Agent Runner (Phase 2)
Starts the headless AI security engine and local FastAPI REST API server on 127.0.0.1.
"""

import argparse
import ipaddress
import os
import sys

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

import uvicorn

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shopguard.agent.server import create_app
from shopguard.agent.security_auth import auth_manager
from shopguard.utils.helpers import load_config


def main():
    parser = argparse.ArgumentParser(
        description="ShopGuard AI - Phase 2 Local Security Agent Runner"
    )
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="Path to configuration YAML file.",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Host interface to bind (default: 127.0.0.1 from config).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port number to bind (default: 8000 from config).",
    )
    parser.add_argument(
        "--webcam",
        nargs="?",
        const=0,
        type=int,
        default=None,
        help="Enable laptop webcam testing mode (default camera index 0, or specify --webcam 1).",
    )
    parser.add_argument(
        "--webcam-index",
        type=int,
        default=None,
        help="Explicit webcam device index to use (e.g. 0, 1). Overrides --webcam value.",
    )
    parser.add_argument(
        "--log-level",
        default="info",
        choices=["debug", "info", "warning", "error"],
        help="Uvicorn server log level.",
    )

    args = parser.parse_args()

    # Determine webcam testing mode
    webcam_idx = args.webcam_index if args.webcam_index is not None else args.webcam
    if webcam_idx is not None:
        from shopguard.camera.stream_reader import check_webcam_available
        is_avail, msg, res = check_webcam_available(webcam_idx)
        if not is_avail:
            print("\n" + "=" * 76)
            print(f"  [ERROR] Laptop webcam index {webcam_idx} could not be opened:")
            print(f"    {msg}")
            print("=" * 76)
            print("  Tips for Windows laptop webcam testing:")
            print("    1. Verify the webcam is not disabled (check physical privacy shutter / Fn key).")
            print("    2. Open Windows Settings -> Privacy & security -> Camera, and turn on 'Camera access'.")
            print("    3. Ensure no other application (Zoom, Teams, Skype, Browser) is currently using the camera.")
            print("    4. If multiple cameras exist, try another index (e.g. --webcam 1).\n")
            sys.exit(1)

        w_res, h_res = res if res else (640, 480)

    # Load configuration
    config = load_config(args.config) if os.path.isfile(args.config) else {}
    agent_cfg = config.get("agent", {})
    host = args.host or agent_cfg.get("host", "127.0.0.1")
    port = args.port or int(agent_cfg.get("port", 8000))

    # Refuse non-loopback interfaces instead of merely warning about exposure.
    try:
        is_loopback = host.strip().lower() == "localhost" or ipaddress.ip_address(
            host.split("%", 1)[0]
        ).is_loopback
    except ValueError:
        is_loopback = False
    if not is_loopback:
        parser.error(
            f"Refusing to expose the ShopGuard agent API on '{host}'. "
            "Use localhost or a loopback IP; remote access requires a separately secured relay."
        )

    print("=" * 76)
    print("      SHOPGUARD AI — PHASE 2: LOCAL SECURITY AGENT (WINDOWS)")
    print("=" * 76)
    if webcam_idx is not None:
        print("  ******************************************************************")
        print("  ***                 WEBCAM TEST MODE — NOT CCTV                ***")
        print(f"  ***  Active Webcam Device Index : {webcam_idx:<30}***")
        print(f"  ***  Webcam Sensor Resolution   : {f'{w_res}x{h_res}':<30}***")
        print("  ***  RTSP / Physical CCTV       : NOT REQUIRED (Simulation Mode)  ***")
        print("  ******************************************************************")
    print("  * Local REST API for CCTV monitoring, health checks, and security arm/disarm")
    print(f"  * Binding Address     : http://{host}:{port}")
    print(f"  * Interactive Docs    : http://{host}:{port}/docs")
    print(f"  * Configuration File  : {args.config}")
    print(f"  * Authentication      : Header 'X-API-Key' or 'Authorization: Bearer <key>'")
    print(f"  * Active Secret Key   : [STORED IN {auth_manager.secret_path}]")
    print("  * Execution Mode      : HEADLESS (Zero OpenCV display windows)")
    print("  * Safe Startup State  : DISARMED")
    print("=" * 76 + "\n")

    # Create app
    app = create_app(config_path=args.config, webcam_index=webcam_idx)

    # Run Uvicorn
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=args.log_level,
        access_log=True,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        from shopguard.utils.logger import get_logger

        get_logger("agent.runner").exception(
            "Unhandled failure while starting or running the agent."
        )
        raise
