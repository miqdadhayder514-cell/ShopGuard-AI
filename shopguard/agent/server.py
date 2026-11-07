"""
ShopGuard AI - Phase 2 Local Security Agent REST API
Built with Python FastAPI and Uvicorn.
Provides a secure, local-only interface for status monitoring, camera health,
incident retrieval, and authorized arm/disarm security management.
"""

from contextlib import asynccontextmanager
import asyncio
from datetime import datetime, timezone
import ipaddress
import json
import os
import re
import time
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query, Request, Security, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .api_models import (
    ArmOperationResponse,
    ArmRequest,
    CameraCreateRequest,
    CameraInfoModel,
    CameraOperationResponse,
    CameraTestRequest,
    CameraTestResponse,
    CameraUpdateRequest,
    CamerasResponse,
    DisarmOperationResponse,
    DisarmRequest,
    ErrorResponse,
    HealthResponse,
    IncidentDetailResponse,
    IncidentSummaryModel,
    IncidentsListResponse,
    SecurityStateResponse,
    StatusResponse,
    SystemInfoResponse,
    DeviceTokenRegisterRequest,
    DeviceTokenUnregisterRequest,
    NotificationTestRequest,
    NotificationOperationResponse,
    NotificationStatusResponse,
)
from .security_auth import auth_manager, require_control_auth, optional_read_auth
from .state_store import PersistentStateStore
from .system_info import collect_system_info, get_agent_uptime_seconds
from ..camera.camera_vault import camera_vault, normalize_rtsp_components, parse_rtsp_url
from ..notifications.fcm_notifier import fcm_notifier as default_fcm_notifier, mask_token
from ..security.security_controller import SecurityState
from ..utils.logger import get_logger, mask_url
from ..utils.helpers import load_config

logger = get_logger("agent.api")

INCIDENT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")


def create_app(
    engine: Optional[Any] = None,
    config_path: str = "config/config.yaml",
    state_file: str = "data/security_state.json",
    webcam_index: Optional[int] = None,
    fcm_notifier: Optional[Any] = None,
) -> FastAPI:
    """
    Factory function initializing the ShopGuard AI Local Security Agent FastAPI application.
    Supports dependency injection for testing and service orchestration.
    """
    config = load_config(config_path) if os.path.isfile(config_path) else {}
    agent_cfg = config.get("agent", {})
    host = agent_cfg.get("host", "127.0.0.1")
    port = int(agent_cfg.get("port", 8000))
    try:
        is_loopback_host = host.strip().lower() == "localhost" or ipaddress.ip_address(
            host.split("%", 1)[0]
        ).is_loopback
    except (AttributeError, ValueError):
        is_loopback_host = False
    if not is_loopback_host:
        raise ValueError(
            f"Agent API host '{host}' is not a loopback address; public/network binding is refused."
        )
    arm_readiness_timeout = max(
        0.0,
        float(agent_cfg.get("arm_readiness_timeout_seconds", 15.0)),
    )
    require_read_auth = bool(agent_cfg.get("require_auth_for_read", False))

    state_store = PersistentStateStore(file_path=state_file)

    def _is_webcam_mode(eng: Any) -> bool:
        if webcam_index is not None:
            return True
        if eng is None:
            return False
        if getattr(eng, "is_webcam_mode", False):
            return True
        if hasattr(eng, "camera_manager"):
            return any(getattr(r, "is_webcam", False) for r in eng.camera_manager.get_all_cameras().values())
        return False

    # Lifespan context manager for graceful background startup & shutdown
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info(f"Starting ShopGuard AI Local Security Agent on {host}:{port}...")

        # If engine was not pre-injected, instantiate headless engine
        if app.state.engine is None:
            from main import ShopGuardEngine
            logger.info("Initializing headless ShopGuardEngine for Local Security Agent...")
            if webcam_index is not None:
                logger.info(
                    f"*** WEBCAM TEST MODE — NOT CCTV *** Initializing with webcam device index {webcam_index}"
                )
            app.state.engine = ShopGuardEngine(
                config_path=config_path,
                webcam_override=webcam_index,
                show_gui=False,
            )
            app.state.engine_was_created = True

        # Never recover an ARMED state from disk or an injected engine after restart.
        app.state.engine.security_controller.disarm()

        # A previous/injected engine must not resume camera processing on API startup.
        stop_monitoring = getattr(app.state.engine, "stop_monitoring", None)
        if callable(stop_monitoring):
            stop_monitoring()

        # Load managed cameras without starting capture workers. They start only on ARM.
        if getattr(app.state, "engine_was_created", False) and hasattr(app.state.engine, "camera_manager"):
            try:
                app.state.engine.camera_manager.load_from_vault(camera_vault, start_now=False)
            except Exception as exc:
                logger.error(f"Failed to load managed cameras from vault: {exc}")

        if not app.state.state_listener_registered:
            def _on_state_change(old_s: SecurityState, new_s: SecurityState):
                state_store.record_transition(new_s, reason=f"Transition from {old_s.value}")

            app.state.engine.security_controller.add_state_listener(_on_state_change)
            app.state.state_listener_registered = True

        logger.info(
            "ShopGuard API is available in DISARMED state; camera and inference workers "
            "will start only after an authenticated ARM request."
        )
        yield

        # Graceful shutdown
        logger.info("Shutting down ShopGuard AI Local Security Agent...")
        eng = app.state.engine
        if eng is not None:
            eng.security_controller.disarm()
            state_store.record_clean_shutdown(eng.security_controller.state)
            eng.stop()
            logger.info("ShopGuard AI Engine and cameras stopped cleanly.")

    app = FastAPI(
        title="ShopGuard AI - Local Security Agent",
        description="Local REST API for monitoring CCTV camera feeds, health, incidents, and security arm/disarm.",
        version="2.0.0",
        lifespan=lifespan,
    )

    # Pre-populate state so endpoints have immediate access in all execution environments
    app.state.engine = engine
    app.state.state_store = state_store
    app.state.config = config
    app.state.webcam_index = webcam_index
    app.state.fcm_notifier = fcm_notifier or getattr(engine, "fcm_notifier", None) or default_fcm_notifier
    app.state.arm_readiness_timeout = arm_readiness_timeout
    app.state.engine_was_created = False
    app.state.state_listener_registered = False

    if engine is not None and hasattr(engine, "security_controller"):
        def _on_state_change(old_s: SecurityState, new_s: SecurityState):
            state_store.record_transition(new_s, reason=f"Transition from {old_s.value}")
        engine.security_controller.add_state_listener(_on_state_change)
        app.state.state_listener_registered = True

    # Restrict CORS to localhost only
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1", "http://localhost"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # Dependency for optional or mandatory read auth
    async def verify_read_access(
        request: Request,
        token: Optional[str] = Security(optional_read_auth),
    ) -> Optional[str]:
        if require_read_auth:
            return await require_control_auth(request)
        return token

    # =========================================================================
    # ENDPOINTS
    # =========================================================================

    @app.get(
        "/api/status",
        response_model=StatusResponse,
        tags=["System"],
        summary="Retrieve overall service and security status",
    )
    async def get_status(_: Optional[str] = Security(verify_read_access)):
        eng = app.state.engine
        eng.security_controller.update_camera_health()
        now = time.time()
        iso_str = datetime.now(timezone.utc).isoformat()

        # Count incidents recorded today
        today_prefix = datetime.now(timezone.utc).strftime("%Y%m%d")
        incidents_dir = eng.incident_recorder.output_directory
        today_count = 0
        if os.path.isdir(incidents_dir):
            for root, _, files in os.walk(incidents_dir):
                for f in files:
                    if f.endswith(".json") and today_prefix in f:
                        today_count += 1

        cam_total = eng.camera_manager.count_total()
        cam_conn = eng.camera_manager.count_connected()

        is_webcam = _is_webcam_mode(eng)
        mode_str = "WEBCAM_TEST" if is_webcam else "CCTV"
        notice_str = "WEBCAM TEST MODE — NOT CCTV" if is_webcam else None

        return StatusResponse(
            service_status="RUNNING",
            security_state=eng.security_controller.state.value,
            is_armed=eng.security_controller.is_armed,
            timestamp=now,
            timestamp_iso=iso_str,
            cameras_total=cam_total,
            cameras_connected=cam_conn,
            active_incidents_today=today_count,
            uptime_seconds=round(get_agent_uptime_seconds(), 1),
            mode=mode_str,
            notice=notice_str,
        )

    @app.get(
        "/api/cameras",
        response_model=CamerasResponse,
        tags=["Cameras"],
        summary="Retrieve list of registered cameras and connection health",
    )
    async def get_cameras(_: Optional[str] = Security(verify_read_access)):
        eng = app.state.engine
        cam_list: List[CameraInfoModel] = []
        cameras = eng.camera_manager.get_all_cameras()
        iso_now = datetime.now(timezone.utc).isoformat()

        for cam_id, reader in cameras.items():
            # Retrieve resolution safely if a frame has been received
            res = None
            if hasattr(reader, "_last_frame") and reader._last_frame is not None:
                h, w = reader._last_frame.shape[:2]
                res = (w, h)

            meta = eng.camera_manager.get_camera_metadata(cam_id)
            vault_rec = camera_vault.get(cam_id) or {}

            cam_type = meta.get("camera_type") or vault_rec.get("camera_type") or (
                "Webcam" if getattr(reader, "is_webcam", False) else "IP Camera"
            )
            location = meta.get("location") or vault_rec.get("location")
            ip_addr = meta.get("ip_address") or vault_rec.get("ip_address")
            port = meta.get("port") or vault_rec.get("port")
            stream_path = meta.get("stream_path") or vault_rec.get("stream_path")

            cam_list.append(
                CameraInfoModel(
                    id=reader.camera_id,
                    name=reader.name,
                    source_masked=mask_url(reader.source),
                    is_connected=reader.is_connected,
                    status=reader.status.value,
                    fps=round(float(getattr(reader, "target_fps", getattr(reader, "fps", 5.0))), 1),
                    resolution=res,
                    consecutive_failures=int(getattr(reader, "_consecutive_failures", getattr(reader, "consecutive_failures", 0))),
                    last_frame_timestamp=float(getattr(reader, "last_frame_time", 0.0)),
                    is_webcam=bool(getattr(reader, "is_webcam", False)),
                    camera_type=cam_type,
                    location=location,
                    ip_address=ip_addr,
                    port=port,
                    stream_path=stream_path,
                    last_status_update=iso_now,
                )
            )

        return CamerasResponse(
            total=len(cam_list),
            connected=eng.camera_manager.count_connected(),
            cameras=cam_list,
        )

    @app.post(
        "/api/cameras/test",
        response_model=CameraTestResponse,
        tags=["Cameras"],
        summary="Test RTSP stream connectivity and decode ability without saving (Strictly Authenticated)",
    )
    async def test_camera_connection(
        req: CameraTestRequest,
        _: str = Security(require_control_auth),
    ):
        """
        Validates connection parameters and tests actual network reachability
        and frame decoding against a physical CCTV/DVR/NVR RTSP endpoint.
        Never exposes RTSP passwords or sensitive credentials in response or logs.
        """
        # 1. Resolve and validate connection parameters
        try:
            if req.rtsp_url and req.rtsp_url.strip():
                parsed = parse_rtsp_url(req.rtsp_url.strip())
                host = parsed["ip_address"]
                port = parsed["port"]
                user = parsed["username"]
                pwd = parsed["password"]
                path = parsed["stream_path"]
                full_url, masked_url = normalize_rtsp_components(host, port, user, pwd, path)
            else:
                if not req.ip_address or not req.ip_address.strip():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={"error": "INVALID_HOST", "message": "IP address or hostname is required."},
                    )
                host = req.ip_address.strip()
                port = req.port
                user = req.username
                pwd = req.password
                path = req.stream_path or ""
                full_url, masked_url = normalize_rtsp_components(host, port, user, pwd, path)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "INVALID_RTSP_URL", "message": str(e)},
            )

        logger.info(f"Initiating stream probe for {masked_url} (Type: {req.camera_type})...")

        # 2. Network socket reachability test
        t0 = time.time()
        import socket
        try:
            sock = socket.create_connection((host, port), timeout=min(2.5, req.timeout_seconds))
            sock.close()
        except socket.timeout:
            latency = (time.time() - t0) * 1000.0
            logger.warning(f"Stream probe failed: socket timeout reaching {host}:{port}")
            return CameraTestResponse(
                success=False,
                message=f"Connection timed out reaching {host}:{port}. Verify camera power, IP address, and network routing.",
                latency_ms=round(latency, 1),
                source_masked=masked_url,
                details="Socket connect timeout (device unreachable on LAN).",
            )
        except Exception as e:
            latency = (time.time() - t0) * 1000.0
            logger.warning(f"Stream probe failed: socket error reaching {host}:{port}: {e}")
            return CameraTestResponse(
                success=False,
                message=f"Network unreachable for {host}:{port}: {type(e).__name__}. Check IP address and RTSP port.",
                latency_ms=round(latency, 1),
                source_masked=masked_url,
                details=f"Socket error: {str(e)}",
            )

        # 3. OpenCV RTSP stream decode test
        import cv2
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
        cap = None
        try:
            cap = cv2.VideoCapture(full_url, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                cap = cv2.VideoCapture(full_url)

            if not cap.isOpened():
                latency = (time.time() - t0) * 1000.0
                logger.warning(f"Stream probe failed: OpenCV VideoCapture could not open {masked_url}")
                return CameraTestResponse(
                    success=False,
                    message="Network port open, but RTSP stream handshake failed. Check authentication credentials or stream path.",
                    latency_ms=round(latency, 1),
                    source_masked=masked_url,
                    details="OpenCV VideoCapture failed to open RTSP transport.",
                )

            # Set short timeouts on probe
            timeout_ms = int(req.timeout_seconds * 1000)
            try:
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_ms)
                cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout_ms)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass

            ret, frame = cap.read()
            latency = (time.time() - t0) * 1000.0

            if not ret or frame is None or frame.size == 0:
                cap.release()
                logger.warning(f"Stream probe failed: cap.read() returned no frame for {masked_url}")
                return CameraTestResponse(
                    success=False,
                    message="RTSP stream opened, but frame decoding failed. Stream may be inactive or format unsupported.",
                    latency_ms=round(latency, 1),
                    source_masked=masked_url,
                    details="cap.read() returned empty frame.",
                )

            h, w = frame.shape[:2]
            fps_val = cap.get(cv2.CAP_PROP_FPS)
            fps = float(fps_val) if fps_val and fps_val > 0 else 15.0
            cap.release()

            logger.info(f"Stream probe successful for {masked_url}: {w}x{h} @ {fps:.1f} FPS")
            return CameraTestResponse(
                success=True,
                message=f"Camera connection verified successfully ({w}x{h} @ {fps:.1f} FPS, {latency:.0f}ms latency).",
                resolution=(w, h),
                fps=round(fps, 1),
                latency_ms=round(latency, 1),
                source_masked=masked_url,
            )
        except Exception as e:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
            latency = (time.time() - t0) * 1000.0
            logger.error(f"Stream probe exception for {masked_url}: {e}")
            return CameraTestResponse(
                success=False,
                message=f"Stream probe exception: {type(e).__name__}",
                latency_ms=round(latency, 1),
                source_masked=masked_url,
                details=str(e),
            )

    @app.post(
        "/api/cameras",
        response_model=CameraOperationResponse,
        tags=["Cameras"],
        summary="Register and activate a new CCTV camera (Strictly Authenticated)",
        status_code=status.HTTP_201_CREATED,
    )
    async def add_camera(
        req: CameraCreateRequest,
        _: str = Security(require_control_auth),
    ):
        """
        Validates camera configuration, securely encrypts credentials in the camera vault,
        and starts video acquisition dynamically without restarting the agent.
        """
        eng = app.state.engine
        # 1. Resolve connection parameters
        try:
            if req.rtsp_url and req.rtsp_url.strip():
                parsed = parse_rtsp_url(req.rtsp_url.strip())
                host = parsed["ip_address"]
                port = parsed["port"]
                user = parsed["username"]
                pwd = parsed["password"]
                path = parsed["stream_path"]
                full_url, masked_url = normalize_rtsp_components(host, port, user, pwd, path)
            else:
                if not req.ip_address or not req.ip_address.strip():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={"error": "INVALID_INPUT", "message": "Either 'ip_address' or 'rtsp_url' must be specified."},
                    )
                host = req.ip_address.strip()
                port = req.port
                user = req.username
                pwd = req.password
                path = req.stream_path or ""
                full_url, masked_url = normalize_rtsp_components(host, port, user, pwd, path)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "INVALID_RTSP_URL", "message": str(e)},
            )

        # 2. Determine or generate Camera ID
        if req.id and req.id.strip():
            cam_id = req.id.strip()
        else:
            clean_name = re.sub(r"[^a-zA-Z0-9]+", "_", req.name).strip("_").lower()
            cam_id = f"cam_{clean_name}_{int(time.time()) % 10000}"

        # 3. Prevent duplicate camera configurations
        dup_reason = camera_vault.check_duplicate(cam_id, host, port, path)
        if dup_reason:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "DUPLICATE_CAMERA", "message": dup_reason},
            )
        if hasattr(eng, "camera_manager") and eng.camera_manager.get_camera(cam_id) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "DUPLICATE_CAMERA", "message": f"Camera with ID '{cam_id}' is already registered in active manager."},
            )

        # 4. Store encrypted in vault
        camera_vault.put(
            camera_id=cam_id,
            name=req.name,
            camera_type=req.camera_type,
            full_source=full_url,
            source_masked=masked_url,
            ip_address=host,
            port=port,
            username=user,
            password=pwd,
            stream_path=path,
            location=req.location,
            fps=req.fps,
            enabled=req.enabled,
        )

        # 5. Add to active CameraManager and start stream safely
        metadata = {
            "camera_type": req.camera_type,
            "location": req.location or "",
            "ip_address": host,
            "port": port,
            "username": user or "",
            "stream_path": path,
            "source_masked": masked_url,
        }
        should_start_stream = req.enabled and eng.security_controller.is_armed
        reader = None
        if req.enabled:
            reader = eng.camera_manager.add_camera(
                camera_id=cam_id,
                name=req.name,
                source=full_url,
                fps=req.fps,
                start_now=should_start_stream,
                metadata=metadata,
            )

        # Ensure rolling pre-event buffer and tracker exist in engine
        if hasattr(eng, "video_buffers") and cam_id not in eng.video_buffers:
            from ..recording.video_buffer import VideoBuffer
            pre_sec = getattr(eng.incident_recorder, "pre_event_seconds", 10.0) if hasattr(eng, "incident_recorder") else 10.0
            eng.video_buffers[cam_id] = VideoBuffer(buffer_seconds=pre_sec + 2.0, fps=req.fps)
        if hasattr(eng, "trackers") and cam_id not in eng.trackers:
            from ..tracking.object_tracker import ObjectTracker
            eng.trackers[cam_id] = ObjectTracker()

        iso_now = datetime.now(timezone.utc).isoformat()
        info = CameraInfoModel(
            id=cam_id,
            name=req.name,
            source_masked=masked_url,
            is_connected=reader.is_connected if reader else False,
            status=reader.status.value if reader else "DISCONNECTED",
            fps=req.fps,
            resolution=None,
            consecutive_failures=0,
            last_frame_timestamp=0.0,
            is_webcam=False,
            camera_type=req.camera_type,
            location=req.location,
            ip_address=host,
            port=port,
            stream_path=path,
            last_status_update=iso_now,
        )

        return CameraOperationResponse(
            success=True,
            camera_id=cam_id,
            message=(
                f"Camera '{req.name}' ({cam_id}) successfully registered and activated."
                if should_start_stream
                else f"Camera '{req.name}' ({cam_id}) registered; its stream will start when the system is ARMED."
            ),
            camera=info,
        )

    @app.put(
        "/api/cameras/{camera_id}",
        response_model=CameraOperationResponse,
        tags=["Cameras"],
        summary="Update an existing camera configuration (Strictly Authenticated)",
    )
    async def update_camera(
        camera_id: str,
        req: CameraUpdateRequest,
        _: str = Security(require_control_auth),
    ):
        """
        Updates an existing camera configuration. Preserves existing passwords when left blank.
        Re-applies changes to the active stream reader without restarting the entire agent.
        """
        eng = app.state.engine
        existing = camera_vault.get(camera_id, include_credentials=True)
        reader = eng.camera_manager.get_camera(camera_id)

        if not existing and not reader:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "CAMERA_NOT_FOUND", "message": f"Camera '{camera_id}' not found."},
            )

        name = req.name if req.name is not None else (existing.get("name") if existing else reader.name)
        cam_type = req.camera_type if req.camera_type is not None else (existing.get("camera_type") if existing else "IP Camera")
        location = req.location if req.location is not None else (existing.get("location") if existing else "")
        fps = req.fps if req.fps is not None else (existing.get("fps") if existing else float(getattr(reader, "target_fps", 5.0)))
        enabled = req.enabled if req.enabled is not None else (existing.get("enabled", True) if existing else True)

        host = req.ip_address if req.ip_address is not None else (existing.get("ip_address") if existing else "")
        port = req.port if req.port is not None else (existing.get("port", 554) if existing else 554)
        user = req.username if req.username is not None else (existing.get("username") if existing else "")
        pwd = req.password if req.password is not None else (existing.get("password") if existing else "")
        path = req.stream_path if req.stream_path is not None else (existing.get("stream_path") if existing else "")

        if req.rtsp_url and req.rtsp_url.strip():
            try:
                parsed = parse_rtsp_url(req.rtsp_url.strip())
                host = parsed["ip_address"]
                port = parsed["port"]
                user = parsed["username"]
                pwd = parsed["password"] or pwd
                path = parsed["stream_path"]
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": "INVALID_RTSP_URL", "message": str(e)},
                )

        full_url, masked_url = normalize_rtsp_components(host, port, user, pwd, path)

        # Check duplicate against other cameras
        dup = camera_vault.check_duplicate(camera_id, host, port, path, exclude_id=camera_id)
        if dup:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "DUPLICATE_CAMERA", "message": dup},
            )

        # Save updated camera to vault
        camera_vault.put(
            camera_id=camera_id,
            name=name,
            camera_type=cam_type,
            full_source=full_url,
            source_masked=masked_url,
            ip_address=host,
            port=port,
            username=user,
            password=pwd,
            stream_path=path,
            location=location,
            fps=fps,
            enabled=enabled,
        )

        metadata = {
            "camera_type": cam_type,
            "location": location,
            "ip_address": host,
            "port": port,
            "username": user,
            "stream_path": path,
            "source_masked": masked_url,
        }

        if not enabled:
            eng.camera_manager.remove_camera(camera_id)
            updated_reader = None
        elif reader:
            updated_reader = eng.camera_manager.update_camera(
                camera_id=camera_id,
                name=name,
                source=full_url,
                fps=fps,
                metadata=metadata,
                restart=True,
                start_now=eng.security_controller.is_armed,
            )
        else:
            updated_reader = eng.camera_manager.add_camera(
                camera_id=camera_id,
                name=name,
                source=full_url,
                fps=fps,
                start_now=eng.security_controller.is_armed,
                metadata=metadata,
            )

        iso_now = datetime.now(timezone.utc).isoformat()
        info = CameraInfoModel(
            id=camera_id,
            name=name,
            source_masked=masked_url,
            is_connected=updated_reader.is_connected if updated_reader else False,
            status=updated_reader.status.value if updated_reader else "DISCONNECTED",
            fps=fps,
            resolution=None,
            consecutive_failures=0,
            last_frame_timestamp=updated_reader.last_frame_time if updated_reader else 0.0,
            is_webcam=bool(getattr(updated_reader, "is_webcam", False)),
            camera_type=cam_type,
            location=location,
            ip_address=host,
            port=port,
            stream_path=path,
            last_status_update=iso_now,
        )

        return CameraOperationResponse(
            success=True,
            camera_id=camera_id,
            message=f"Camera '{name}' ({camera_id}) configuration updated.",
            camera=info,
        )

    @app.delete(
        "/api/cameras/{camera_id}",
        response_model=CameraOperationResponse,
        tags=["Cameras"],
        summary="Unregister and remove a CCTV camera (Strictly Authenticated)",
    )
    async def remove_camera(
        camera_id: str,
        _: str = Security(require_control_auth),
    ):
        """
        Gracefully terminates stream decoding for the specified camera and removes it
        from persistent vault storage and active manager.
        """
        eng = app.state.engine
        reader = eng.camera_manager.get_camera(camera_id)
        in_vault = camera_vault.get(camera_id)

        if not reader and not in_vault:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "CAMERA_NOT_FOUND", "message": f"Camera '{camera_id}' not found."},
            )

        # Stop and remove from active manager
        eng.camera_manager.remove_camera(camera_id)

        # Clean up buffers and trackers in engine
        if hasattr(eng, "video_buffers"):
            eng.video_buffers.pop(camera_id, None)
        if hasattr(eng, "trackers"):
            eng.trackers.pop(camera_id, None)

        # Remove from vault storage
        camera_vault.delete(camera_id)

        logger.info(f"Camera '{camera_id}' unmounted and removed via API.")
        return CameraOperationResponse(
            success=True,
            camera_id=camera_id,
            message=f"Camera '{camera_id}' was successfully unmounted and removed.",
            camera=None,
        )

    @app.get(
        "/api/security/state",
        response_model=SecurityStateResponse,
        tags=["Security Management"],
        summary="Retrieve current security arm state and pre-arm prerequisites",
    )
    async def get_security_state(_: Optional[str] = Security(verify_read_access)):
        eng = app.state.engine
        eng.security_controller.update_camera_health()
        check_res = eng.security_controller.verify_arming_prerequisites()

        active_zones_count = 0
        all_zones = eng.zone_manager.get_all_zones()
        for zones_in_cam in all_zones.values():
            active_zones_count += sum(1 for z in zones_in_cam if z.enabled)

        store_summary = app.state.state_store.get_state_summary()

        return SecurityStateResponse(
            state=eng.security_controller.state.value,
            is_armed=eng.security_controller.is_armed,
            can_arm=check_res.can_arm,
            active_zones_count=active_zones_count,
            connected_cameras=eng.camera_manager.count_connected(),
            total_cameras=eng.camera_manager.count_total(),
            last_state_change=store_summary.get("timestamp_iso"),
            rejection_reasons=check_res.reasons,
        )

    @app.post(
        "/api/security/arm",
        response_model=ArmOperationResponse,
        tags=["Security Management"],
        summary="Arm the security system (Strictly Authenticated)",
    )
    async def arm_security(
        request: Request,
        req: Optional[ArmRequest] = None,
        _: str = Security(require_control_auth),
    ):
        client_ip = request.client.host if request.client else "unknown"
        if req is None:
            req = ArmRequest()
        eng = app.state.engine
        eng.security_controller.update_camera_health()
        now = time.time()
        iso_str = datetime.now(timezone.utc).isoformat()
        current_state = eng.security_controller.state

        logger.info(
            f"[ARM_REQUEST] Incoming arm command from {client_ip}. Reason: '{req.reason}'. "
            f"Current state: {current_state.value}"
        )

        # Duplicate arm prevention
        if current_state in (SecurityState.ARMED, SecurityState.PARTIAL, SecurityState.ARMING):
            logger.info(f"[ARM_REQUEST] Arm rejected: System is already ARMED (client: {client_ip}).")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "ALREADY_ARMED",
                    "message": "Security system is already in ARMED state.",
                    "state": current_state.value,
                },
            )

        start_monitoring = getattr(eng, "start", None)
        if callable(start_monitoring):
            await asyncio.to_thread(start_monitoring)

        wait_for_ready = getattr(eng, "wait_until_monitoring_ready", None)
        if callable(wait_for_ready):
            await asyncio.to_thread(wait_for_ready, app.state.arm_readiness_timeout)

        success, msg, check_result = eng.security_controller.arm()

        if success:
            app.state.state_store.record_transition(
                eng.security_controller.state, reason=f"API Arm ({client_ip}): {req.reason}"
            )
            logger.info(
                f"[ARM_SUCCESS] System successfully transitioned to {eng.security_controller.state.value} "
                f"via authenticated command from {client_ip}."
            )
            return ArmOperationResponse(
                success=True,
                state=eng.security_controller.state.value,
                message=msg,
                timestamp=now,
                timestamp_iso=iso_str,
            )
        else:
            if eng.security_controller.state in (
                SecurityState.ARMED,
                SecurityState.PARTIAL,
                SecurityState.ARMING,
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": "ALREADY_ARMED",
                        "message": f"Security system is already {eng.security_controller.state.value}.",
                        "state": eng.security_controller.state.value,
                    },
                )
            stop_monitoring = getattr(eng, "stop_monitoring", None)
            if callable(stop_monitoring):
                await asyncio.to_thread(stop_monitoring)
            reasons = check_result.reasons if check_result else [msg]
            logger.warning(
                f"[ARM_REJECTED] Prerequisites check failed for arm command from {client_ip}. "
                f"Reasons: {reasons}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "ARMING_REJECTED",
                    "message": msg,
                    "state": eng.security_controller.state.value,
                    "reasons": reasons,
                },
            )

    @app.post(
        "/api/security/disarm",
        response_model=DisarmOperationResponse,
        tags=["Security Management"],
        summary="Disarm the security system (Strictly Authenticated)",
    )
    async def disarm_security(
        request: Request,
        req: Optional[DisarmRequest] = None,
        _: str = Security(require_control_auth),
    ):
        client_ip = request.client.host if request.client else "unknown"
        if req is None:
            req = DisarmRequest()
        eng = app.state.engine
        now = time.time()
        iso_str = datetime.now(timezone.utc).isoformat()
        current_state = eng.security_controller.state

        logger.info(
            f"[DISARM_REQUEST] Incoming disarm command from {client_ip}. Reason: '{req.reason}'. "
            f"Current state: {current_state.value}"
        )

        # Duplicate disarm prevention
        if current_state == SecurityState.DISARMED:
            logger.info(f"[DISARM_REQUEST] Disarm rejected: System is already DISARMED (client: {client_ip}).")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "ALREADY_DISARMED",
                    "message": "Security system is already in DISARMED state.",
                    "state": current_state.value,
                },
            )

        success, msg = eng.security_controller.disarm()
        stop_monitoring = getattr(eng, "stop_monitoring", None)
        if callable(stop_monitoring):
            await asyncio.to_thread(stop_monitoring)

        app.state.state_store.record_transition(
            SecurityState.DISARMED, reason=f"API Disarm ({client_ip}): {req.reason}"
        )
        logger.info(
            f"[DISARM_SUCCESS] System successfully transitioned to DISARMED via authenticated command from {client_ip}."
        )

        return DisarmOperationResponse(
            success=True,
            state=SecurityState.DISARMED.value,
            message=msg,
            timestamp=now,
            timestamp_iso=iso_str,
        )

    @app.get(
        "/api/incidents",
        response_model=IncidentsListResponse,
        tags=["Incidents"],
        summary="List recorded incident history",
    )
    async def list_incidents(
        limit: int = Query(default=50, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
        camera_id: Optional[str] = Query(default=None),
        _: Optional[str] = Security(verify_read_access),
    ):
        eng = app.state.engine
        incidents_dir = eng.incident_recorder.output_directory
        all_incidents: List[IncidentSummaryModel] = []

        if os.path.isdir(incidents_dir):
            for root, _, files in os.walk(incidents_dir):
                for f in files:
                    if not f.endswith(".json"):
                        continue
                    file_path = os.path.join(root, f)
                    try:
                        with open(file_path, "r", encoding="utf-8") as jf:
                            data = json.load(jf)

                        cid = data.get("camera_id", "")
                        if camera_id and cid != camera_id:
                            continue

                        # Check if video file exists on disk
                        vid_filename = data.get("video_filename", "")
                        has_vid = False
                        if vid_filename:
                            vid_path = os.path.join(root, vid_filename)
                            has_vid = os.path.isfile(vid_path)

                        # Extract timestamp
                        iso_ts = data.get("event_timestamp", "")
                        epoch_ts = 0.0
                        try:
                            epoch_ts = datetime.fromisoformat(iso_ts).timestamp()
                        except Exception:
                            epoch_ts = os.path.getmtime(file_path)

                        all_incidents.append(
                            IncidentSummaryModel(
                                incident_id=data.get("incident_id", f.replace(".json", "")),
                                camera_id=cid,
                                camera_name=data.get("camera_name", cid),
                                event_type=data.get("event_type", "UNKNOWN"),
                                event_timestamp=iso_ts,
                                timestamp=epoch_ts,
                                track_id=data.get("track_id"),
                                confidence=float(data.get("confidence", 0.0)),
                                zone_name=data.get("zone_name", "Protected Zone"),
                                video_filename=vid_filename,
                                has_video=has_vid,
                                duration_seconds=float(data.get("duration_seconds", 0.0)),
                                review_status=data.get("review_status", "UNREVIEWED"),
                            )
                        )
                    except Exception as err:
                        logger.warning(f"Error reading incident file '{file_path}': {err}")

        # Sort descending by timestamp (newest first)
        all_incidents.sort(key=lambda x: x.timestamp, reverse=True)
        total = len(all_incidents)
        paginated = all_incidents[offset : offset + limit]

        return IncidentsListResponse(
            total=total,
            limit=limit,
            offset=offset,
            incidents=paginated,
        )

    @app.get(
        "/api/incidents/{incident_id}",
        response_model=IncidentDetailResponse,
        tags=["Incidents"],
        summary="Retrieve metadata for a specific incident",
    )
    async def get_incident(
        incident_id: str,
        _: Optional[str] = Security(verify_read_access),
    ):
        # Strict input validation preventing path traversal
        if not INCIDENT_ID_PATTERN.match(incident_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "INVALID_INCIDENT_ID",
                    "message": "Incident ID contains invalid characters. Only alphanumeric, dashes, and underscores are permitted.",
                },
            )

        eng = app.state.engine
        incidents_dir = eng.incident_recorder.output_directory
        target_json = None
        target_dir = None

        if os.path.isdir(incidents_dir):
            for root, _, files in os.walk(incidents_dir):
                candidate_name = f"{incident_id}.json"
                if candidate_name in files:
                    target_json = os.path.join(root, candidate_name)
                    target_dir = root
                    break
                # Also check file content for matching incident_id
                for fname in files:
                    if fname.endswith(".json"):
                        fpath = os.path.join(root, fname)
                        try:
                            with open(fpath, "r", encoding="utf-8") as jf:
                                jdata = json.load(jf)
                                if jdata.get("incident_id") == incident_id:
                                    target_json = fpath
                                    target_dir = root
                                    break
                        except Exception:
                            continue
                if target_json:
                    break

        if not target_json or not os.path.isfile(target_json):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "INCIDENT_NOT_FOUND",
                    "message": f"Incident with ID '{incident_id}' was not found in local storage.",
                },
            )

        try:
            with open(target_json, "r", encoding="utf-8") as f:
                data = json.load(f)

            vid_filename = data.get("video_filename", "")
            video_exists = False
            video_bytes = 0
            if vid_filename and target_dir:
                vid_path = os.path.join(target_dir, vid_filename)
                if os.path.isfile(vid_path):
                    video_exists = True
                    video_bytes = os.path.getsize(vid_path)

            return IncidentDetailResponse(
                incident_id=data.get("incident_id", incident_id),
                camera_id=data.get("camera_id", ""),
                camera_name=data.get("camera_name", ""),
                event_type=data.get("event_type", ""),
                event_timestamp=data.get("event_timestamp", ""),
                track_id=data.get("track_id"),
                detection_confidence=float(data.get("detection_confidence", 0.0)),
                confidence=float(data.get("confidence", 0.0)),
                zone_id=data.get("zone_id", ""),
                zone_name=data.get("zone_name", ""),
                video_filename=vid_filename,
                video_exists=video_exists,
                video_size_bytes=video_bytes,
                review_status=data.get("review_status", "UNREVIEWED"),
                duration_seconds=float(data.get("duration_seconds", 0.0)),
                total_frames=int(data.get("total_frames", 0)),
                source_type=data.get("source_type", "live_cctv"),
                simulation_mode=bool(data.get("simulation_mode", False)),
                rtsp_verified=bool(data.get("rtsp_verified", False)),
            )

        except Exception as e:
            logger.error(f"Error reading incident file '{target_json}': {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "SERVER_ERROR", "message": f"Could not parse incident metadata: {e}"},
            )

    @app.get(
        "/api/health",
        response_model=HealthResponse,
        tags=["System"],
        summary="Comprehensive system health and storage diagnostic",
    )
    async def get_health(_: Optional[str] = Security(verify_read_access)):
        eng = app.state.engine
        eng.security_controller.update_camera_health()
        snapshot = eng.health_monitor.get_health_report()

        cams_info = []
        for c in snapshot.cameras:
            cams_info.append({
                "camera_id": c.camera_id,
                "camera_name": c.camera_name,
                "is_connected": c.is_connected,
                "status": c.status,
                "last_frame_age_seconds": round(c.last_frame_age_seconds, 1),
                "total_frames_read": c.total_frames_read,
                "stream_source_masked": mask_url(c.stream_source_masked),
            })

        is_webcam = _is_webcam_mode(eng)
        mode_str = "WEBCAM_TEST" if is_webcam else "CCTV"
        notice_str = "WEBCAM TEST MODE — NOT CCTV" if is_webcam else None

        return HealthResponse(
            healthy=(snapshot.overall_health == "HEALTHY"),
            overall_health=snapshot.overall_health,
            security_state=snapshot.security_state,
            ai_model_loaded=snapshot.ai_model_loaded,
            ai_model_path=snapshot.ai_model_path,
            ai_device=snapshot.ai_device,
            disk_free_gb=round(snapshot.disk_free_gb, 2),
            disk_total_gb=round(snapshot.disk_total_gb, 2),
            cameras=cams_info,
            timestamp=snapshot.timestamp,
            mode=mode_str,
            notice=notice_str,
        )

    @app.get(
        "/api/system/info",
        response_model=SystemInfoResponse,
        tags=["System"],
        summary="Host environment, memory, and runtime metadata",
    )
    async def get_system_info(_: Optional[str] = Security(verify_read_access)):
        info = collect_system_info(api_host=host, api_port=port, auth_enabled=True)
        return SystemInfoResponse(**info)

    # =========================================================================
    # NOTIFICATION MANAGEMENT ENDPOINTS (FCM)
    # =========================================================================

    @app.post(
        "/api/notifications/register-token",
        response_model=NotificationOperationResponse,
        tags=["Notifications"],
        summary="Register an FCM device token for mobile push notifications",
    )
    async def register_device_token(
        req: DeviceTokenRegisterRequest,
        _: str = Security(require_control_auth),
    ):
        notifier = app.state.fcm_notifier
        if notifier is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="FCM notification service is unavailable.",
            )

        try:
            total_count = notifier.register_token(
                token=req.token,
                device_name=req.device_name or "Android Device",
                app_version=req.app_version or "1.0.0",
            )
        except ValueError as ve:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(ve),
            )
        except Exception as e:
            logger.error(f"Error registering device token: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to register device token.",
            )

        now = time.time()
        return NotificationOperationResponse(
            success=True,
            message="Device token registered successfully.",
            tokens_count=total_count,
            timestamp=now,
            timestamp_iso=datetime.now(timezone.utc).isoformat(),
        )

    @app.post(
        "/api/notifications/unregister-token",
        response_model=NotificationOperationResponse,
        tags=["Notifications"],
        summary="Unregister an FCM device token",
    )
    async def unregister_device_token(
        req: DeviceTokenUnregisterRequest,
        _: str = Security(require_control_auth),
    ):
        notifier = app.state.fcm_notifier
        if notifier is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="FCM notification service is unavailable.",
            )

        removed = notifier.unregister_token(req.token)
        now = time.time()
        msg = "Device token unregistered." if removed else "Device token not found."
        return NotificationOperationResponse(
            success=True,
            message=msg,
            tokens_count=notifier.get_token_count(),
            timestamp=now,
            timestamp_iso=datetime.now(timezone.utc).isoformat(),
        )

    @app.post(
        "/api/notifications/test",
        response_model=NotificationOperationResponse,
        tags=["Notifications"],
        summary="Send a test push notification to registered devices",
    )
    async def send_test_notification(
        req: Optional[NotificationTestRequest] = None,
        _: str = Security(require_control_auth),
    ):
        notifier = app.state.fcm_notifier
        if notifier is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="FCM notification service is unavailable.",
            )

        title = req.title if req and req.title else "ShopGuard AI Test Alert"
        body = req.body if req and req.body else "This is a test notification from ShopGuard AI."

        result = notifier.send_test_notification(title=title, body=body)
        now = time.time()
        status_label = result.get("status", "unknown")
        if status_label == "unconfigured":
            return NotificationOperationResponse(
                success=False,
                message="Firebase Admin credentials not configured on agent host.",
                tokens_count=notifier.get_token_count(),
                timestamp=now,
                timestamp_iso=datetime.now(timezone.utc).isoformat(),
            )

        sent_count = result.get("sent", 0)
        return NotificationOperationResponse(
            success=(sent_count > 0 or result.get("total_targets", 0) == 0),
            message=f"Test notification dispatched to {sent_count} device(s).",
            tokens_count=notifier.get_token_count(),
            timestamp=now,
            timestamp_iso=datetime.now(timezone.utc).isoformat(),
        )

    @app.get(
        "/api/notifications/status",
        response_model=NotificationStatusResponse,
        tags=["Notifications"],
        summary="Retrieve FCM notification configuration and registration status",
    )
    async def get_notification_status(_: Optional[str] = Security(verify_read_access)):
        notifier = app.state.fcm_notifier
        status_data = notifier.get_status() if notifier else {
            "configured": False,
            "credentials_present": False,
            "tokens_count": 0,
        }
        now = time.time()
        return NotificationStatusResponse(
            configured=status_data.get("configured", False),
            credentials_present=status_data.get("credentials_present", False),
            tokens_count=status_data.get("tokens_count", 0),
            timestamp=now,
            timestamp_iso=datetime.now(timezone.utc).isoformat(),
        )

    return app
