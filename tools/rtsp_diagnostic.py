"""
ShopGuard AI - RTSP Connection Diagnostic Utility
Tests network reachability, RTSP protocol handshake, authentication, and OpenCV decoding.
Usage:
    python tools/rtsp_diagnostic.py --url "rtsp://admin:password@192.168.1.100:554/stream"
    python tools/rtsp_diagnostic.py --config config/config.yaml --camera camera_01
"""

import argparse
import base64
import os
import re
import socket
import sys
import time
from urllib.parse import urlparse
import cv2

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shopguard.utils.helpers import load_config
from shopguard.utils.logger import mask_url


def probe_rtsp_stream(url: str, timeout: float = 5.0) -> dict:
    """
    Performs comprehensive multi-stage diagnostic checks on an RTSP stream:
    1. URL Syntax & Parsing
    2. TCP Socket Connectivity
    3. RTSP Protocol Handshake & Authentication Probe
    4. OpenCV VideoCapture & Frame Decoding
    """
    report = {
        "url_masked": mask_url(url),
        "syntax_valid": False,
        "tcp_reachable": False,
        "rtsp_status_code": None,
        "rtsp_status_msg": None,
        "opencv_opened": False,
        "frame_decoded": False,
        "resolution": None,
        "error_stage": None,
        "error_details": None,
        "recommendation": None,
    }

    # 1. URL Syntax & Parsing
    if not url or not isinstance(url, str):
        report["error_stage"] = "URL Parsing"
        report["error_details"] = "Empty or non-string URL provided."
        report["recommendation"] = "Provide a valid RTSP URL (e.g. rtsp://user:pass@192.168.1.100:554/stream)."
        return report

    if not url.lower().startswith("rtsp://"):
        report["error_stage"] = "URL Protocol"
        report["error_details"] = f"URL scheme is not rtsp://: {report['url_masked']}"
        report["recommendation"] = "Ensure the URL starts with rtsp:// (RTSP streaming protocol)."
        return report

    try:
        parsed = urlparse(url)
        host = parsed.hostname
        port = parsed.port or 554
        username = parsed.username
        password = parsed.password
        path = parsed.path or "/"
    except Exception as e:
        report["error_stage"] = "URL Parsing"
        report["error_details"] = f"Failed to parse RTSP URL: {e}"
        report["recommendation"] = "Check URL format for illegal characters or missing hostname."
        return report

    if not host:
        report["error_stage"] = "URL Parsing"
        report["error_details"] = "No hostname or IP address found in RTSP URL."
        report["recommendation"] = "Include the camera's local IP address (e.g. 192.168.1.100)."
        return report

    report["syntax_valid"] = True

    # 2. TCP Socket Connectivity
    print(f"[*] Step 1: Testing TCP connectivity to {host}:{port} (timeout={timeout}s)...")
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        report["tcp_reachable"] = True
        print("    [+] TCP connection successful.")
    except socket.gaierror as e:
        report["error_stage"] = "DNS / Host Resolution"
        report["error_details"] = f"Could not resolve host '{host}': {e}"
        report["recommendation"] = "Verify camera IP address or hostname. Check local router DHCP assignments."
        return report
    except socket.timeout:
        report["error_stage"] = "Network Timeout"
        report["error_details"] = f"Connection timed out reaching {host}:{port} after {timeout} seconds."
        report["recommendation"] = (
            "1. Verify camera power and Ethernet connection.\n"
            "2. Ensure PC is on the same subnet (e.g., PC 192.168.1.50, Camera 192.168.1.100).\n"
            "3. Check camera firewall or port 554 settings."
        )
        return report
    except ConnectionRefusedError:
        report["error_stage"] = "Connection Refused"
        report["error_details"] = f"Port {port} on {host} is closed or rejected connection."
        report["recommendation"] = (
            f"Port {port} is closed. Check camera NVR web console to confirm RTSP service is enabled and verify RTSP port."
        )
        return report
    except Exception as e:
        report["error_stage"] = "TCP Socket Error"
        report["error_details"] = str(e)
        report["recommendation"] = "Check network cables, switches, and Windows firewall."
        return report

    # 3. RTSP Protocol Handshake & Authentication Probe
    print("[*] Step 2: Probing RTSP protocol (DESCRIBE request)...")
    try:
        auth_header = ""
        if username and password:
            token = base64.b64encode(f"{username}:{password}".encode()).decode()
            auth_header = f"Authorization: Basic {token}\r\n"

        req = (
            f"DESCRIBE rtsp://{host}:{port}{path} RTSP/1.0\r\n"
            f"CSeq: 1\r\n"
            f"User-Agent: ShopGuard-AI-Diagnostic/1.0\r\n"
            f"Accept: application/sdp\r\n"
            f"{auth_header}\r\n"
        )
        sock.sendall(req.encode())
        sock.settimeout(timeout)
        response_bytes = sock.recv(4096)
        sock.close()

        response_text = response_bytes.decode("utf-8", errors="replace")
        status_line = response_text.splitlines()[0] if response_text else ""
        print(f"    [+] RTSP Server response: {status_line}")

        match = re.search(r"RTSP/\d\.\d\s+(\d+)\s+(.*)", status_line)
        if match:
            code = int(match.group(1))
            msg = match.group(2).strip()
            report["rtsp_status_code"] = code
            report["rtsp_status_msg"] = msg

            if code == 401:
                report["error_stage"] = "Authentication Failed (401)"
                report["error_details"] = "RTSP Server rejected credentials (401 Unauthorized)."
                report["recommendation"] = (
                    "Verify camera username and password in .env file. Note that some cameras have separate "
                    "ONVIF/RTSP passwords distinct from web login passwords."
                )
                return report
            elif code == 404:
                report["error_stage"] = "Stream Path Not Found (404)"
                report["error_details"] = f"RTSP stream path '{path}' does not exist on server."
                report["recommendation"] = (
                    "Verify manufacturer RTSP path. Examples:\n"
                    "  - Hikvision: /Streaming/Channels/101\n"
                    "  - Dahua:     /cam/realmonitor?channel=1&subtype=0\n"
                    "  - Generic:   /h264Preview_01_main"
                )
                return report
    except Exception as e:
        print(f"    [!] Warning: Raw RTSP socket probe failed: {e}. Continuing with OpenCV probe.")
    finally:
        try:
            sock.close()
        except Exception:
            pass

    # 4. OpenCV VideoCapture & Frame Decoding
    print("[*] Step 3: Testing OpenCV VideoCapture & FFmpeg decoding...")
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)

    if not cap.isOpened():
        cap = cv2.VideoCapture(url)

    if not cap.isOpened():
        report["error_stage"] = "OpenCV / FFmpeg Init"
        report["error_details"] = "OpenCV could not open stream with CAP_FFMPEG backend."
        report["recommendation"] = (
            "Verify codec compatibility (H.264 is strongly recommended over H.265 for compatibility). "
            "Ensure stream is accessible via VLC Media Player first."
        )
        return report

    report["opencv_opened"] = True

    try:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        ret, frame = cap.read()
        if ret and frame is not None and frame.size > 0:
            h, w = frame.shape[:2]
            report["frame_decoded"] = True
            report["resolution"] = f"{w}x{h}"
            print(f"    [+] Successfully decoded live frame! Resolution: {w}x{h}")
        else:
            report["error_stage"] = "Frame Read Timeout"
            report["error_details"] = "OpenCV connected but read() returned no frame bytes."
            report["recommendation"] = "Camera stream may be frozen or bitrate exceeds network capacity."
    finally:
        cap.release()

    return report


def print_diagnostic_summary(rep: dict) -> None:
    print("\n" + "=" * 65)
    print("          SHOPGUARD AI - RTSP DIAGNOSTIC REPORT")
    print("=" * 65)
    print(f"Target URL:         {rep['url_masked']}")
    print(f"URL Syntax:         {'[OK]' if rep['syntax_valid'] else '[FAIL]'}")
    print(f"TCP Reachability:   {'[OK]' if rep['tcp_reachable'] else '[FAIL]'}")
    if rep["rtsp_status_code"]:
        print(f"RTSP Server Reply:  {rep['rtsp_status_code']} {rep['rtsp_status_msg']}")
    print(f"OpenCV Connection:  {'[OK]' if rep['opencv_opened'] else '[FAIL]'}")
    print(f"Frame Decoding:     {'[OK]' if rep['frame_decoded'] else '[FAIL]'}")
    if rep["resolution"]:
        print(f"Stream Resolution:  {rep['resolution']}")
    print("-" * 65)

    if rep["frame_decoded"]:
        print("VERDICT: PASS - Stream is fully compatible and readable by ShopGuard AI.")
    else:
        print(f"VERDICT: FAILED at stage '{rep['error_stage']}'")
        print(f"Details: {rep['error_details']}")
        if rep["recommendation"]:
            print("\nRecommended Actions:")
            for line in rep["recommendation"].splitlines():
                print(f"  * {line}")
    print("=" * 65 + "\n")


def main():
    parser = argparse.ArgumentParser(description="ShopGuard AI RTSP Diagnostic Utility")
    parser.add_argument("--url", help="RTSP URL to test (e.g. rtsp://user:pass@192.168.1.100:554/stream)")
    parser.add_argument("--config", default="config/config.yaml", help="Path to config.yaml")
    parser.add_argument("--camera", default="camera_01", help="Camera ID to read from config")
    parser.add_argument("--timeout", type=float, default=5.0, help="Connection timeout in seconds")
    args = parser.parse_args()

    url = args.url
    if not url:
        cfg = load_config(args.config)
        cams = cfg.get("cameras", [])
        selected = next((c for c in cams if c.get("id") == args.camera), None)
        if selected:
            url = selected.get("source", "")
        else:
            print(f"Error: Camera '{args.camera}' not found in {args.config}")
            sys.exit(1)

    rep = probe_rtsp_stream(url, timeout=args.timeout)
    print_diagnostic_summary(rep)

    if not rep["frame_decoded"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
