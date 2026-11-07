from typing import Any, Dict, List, Optional
from .stream_reader import CameraStatus, StreamReader
from ..utils.logger import get_logger, mask_url

logger = get_logger("camera.manager")


class CameraManager:
    """
    Coordinates multiple video camera streams for ShopGuard AI.
    Handles startup, shutdown, status aggregation, and frame dispatch.
    """

    def __init__(self):
        self._cameras: Dict[str, StreamReader] = {}
        self._camera_configs: Dict[str, Dict[str, Any]] = {}
        self._camera_metadata: Dict[str, Dict[str, Any]] = {}

    def add_camera(
        self,
        camera_id: str,
        name: str,
        source: Any,
        fps: float = 5.0,
        reconnect_interval: float = 5.0,
        connection_timeout: float = 10.0,
        start_now: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StreamReader:
        """
        Dynamically registers and optionally starts a camera stream reader.
        Thread-safe for runtime camera addition without restarting the engine.
        """
        # If camera already exists, stop previous reader before replacing
        if camera_id in self._cameras:
            logger.info(f"Camera '{camera_id}' already registered. Stopping and updating reader.")
            self._cameras[camera_id].stop()

        reader = StreamReader(
            camera_id=camera_id,
            name=name,
            source=source,
            fps=fps,
            reconnect_interval=reconnect_interval,
            connection_timeout=connection_timeout,
        )

        cfg = {
            "id": camera_id,
            "name": name,
            "source": source,
            "fps": fps,
            "reconnect_interval_seconds": reconnect_interval,
            "connection_timeout_seconds": connection_timeout,
            "enabled": True,
        }
        self._cameras[camera_id] = reader
        self._camera_configs[camera_id] = cfg
        self._camera_metadata[camera_id] = metadata or {}

        if start_now:
            reader.start()

        logger.info(
            f"Successfully added camera '{name}' (ID: {camera_id}, Type: {self._camera_metadata[camera_id].get('camera_type', 'cctv')}) -> {mask_url(source)}"
        )
        return reader

    def remove_camera(self, camera_id: str) -> bool:
        """
        Stops and unregisters a camera from the manager.
        Returns True if camera was found and removed, False otherwise.
        """
        if camera_id not in self._cameras:
            return False

        reader = self._cameras[camera_id]
        reader.stop()
        del self._cameras[camera_id]
        self._camera_configs.pop(camera_id, None)
        self._camera_metadata.pop(camera_id, None)
        logger.info(f"Removed and stopped camera '{camera_id}' from CameraManager.")
        return True

    def update_camera(
        self,
        camera_id: str,
        name: Optional[str] = None,
        source: Optional[Any] = None,
        fps: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        restart: bool = True,
        start_now: bool = True,
    ) -> Optional[StreamReader]:
        """
        Updates configuration/metadata for an existing camera.
        If source or FPS changed and restart is True, safely restarts the reader.
        """
        if camera_id not in self._cameras:
            return None

        reader = self._cameras[camera_id]
        cfg = self._camera_configs.get(camera_id, {})
        meta = self._camera_metadata.get(camera_id, {})

        new_name = name if name is not None else reader.name
        new_source = source if source is not None else reader.source
        new_fps = fps if fps is not None else float(getattr(reader, "target_fps", 5.0))

        if metadata:
            meta.update(metadata)
            self._camera_metadata[camera_id] = meta

        source_changed = (str(new_source) != str(reader.source))
        fps_changed = (abs(new_fps - getattr(reader, "target_fps", 5.0)) > 0.01)

        if (source_changed or fps_changed) and restart:
            reader.stop()
            new_reader = StreamReader(
                camera_id=camera_id,
                name=new_name,
                source=new_source,
                fps=new_fps,
                reconnect_interval=cfg.get("reconnect_interval_seconds", 5.0),
                connection_timeout=cfg.get("connection_timeout_seconds", 10.0),
            )
            self._cameras[camera_id] = new_reader
            if start_now:
                new_reader.start()
            reader = new_reader
        else:
            reader.name = new_name

        cfg["name"] = new_name
        cfg["source"] = new_source
        cfg["fps"] = new_fps
        self._camera_configs[camera_id] = cfg
        return reader

    def get_camera_metadata(self, camera_id: str) -> Dict[str, Any]:
        """Returns metadata (e.g. camera_type, location, ip) for a camera."""
        return dict(self._camera_metadata.get(camera_id, {}))

    def load_from_vault(self, vault: Any, start_now: bool = False) -> None:
        """Loads all managed cameras from CameraVault into the manager."""
        cameras = vault.get_all(include_credentials=True)
        for cam in cameras:
            cam_id = cam.get("id")
            if not cam_id or not cam.get("enabled", True):
                continue
            self.add_camera(
                camera_id=cam_id,
                name=cam.get("name", cam_id),
                source=cam.get("source", ""),
                fps=cam.get("fps", 5.0),
                reconnect_interval=cam.get("reconnect_interval_seconds", 5.0),
                connection_timeout=cam.get("connection_timeout_seconds", 10.0),
                start_now=start_now,
                metadata={
                    "camera_type": cam.get("camera_type", "IP Camera"),
                    "location": cam.get("location", ""),
                    "ip_address": cam.get("ip_address", ""),
                    "port": cam.get("port", 554),
                    "username": cam.get("username", ""),
                    "stream_path": cam.get("stream_path", ""),
                    "source_masked": cam.get("source_masked", ""),
                },
            )

    def add_camera_from_config(self, camera_cfg: Dict[str, Any]) -> Optional[StreamReader]:
        """Registers a camera from a configuration dictionary."""
        cam_id = camera_cfg.get("id")
        if not cam_id:
            logger.error("Cannot add camera without an 'id'.")
            return None

        enabled = camera_cfg.get("enabled", True)
        if not enabled:
            logger.info(f"Camera '{cam_id}' is disabled in configuration. Skipping.")
            return None

        name = camera_cfg.get("name", cam_id)
        source = camera_cfg.get("source", "")
        fps = camera_cfg.get("fps", 5.0)
        reconnect_interval = camera_cfg.get("reconnect_interval_seconds", 5.0)
        connection_timeout = camera_cfg.get("connection_timeout_seconds", 10.0)

        reader = StreamReader(
            camera_id=cam_id,
            name=name,
            source=source,
            fps=fps,
            reconnect_interval=reconnect_interval,
            connection_timeout=connection_timeout,
        )

        self._cameras[cam_id] = reader
        self._camera_configs[cam_id] = camera_cfg
        logger.info(f"Registered camera '{name}' ({cam_id}) -> Source: {mask_url(source)}")
        return reader

    def load_from_config(self, config: Dict[str, Any]) -> None:
        """Loads all enabled cameras defined in the application config."""
        cameras_list = config.get("cameras", [])
        for cam_cfg in cameras_list:
            self.add_camera_from_config(cam_cfg)

    def start_all(self) -> None:
        """Starts background frame readers for all registered cameras."""
        logger.info(f"Starting {len(self._cameras)} camera stream reader(s)...")
        for cam_id, reader in self._cameras.items():
            reader.start()

    def stop_all(self) -> None:
        """Stops all camera stream readers gracefully."""
        logger.info("Stopping all camera stream readers...")
        for cam_id, reader in self._cameras.items():
            reader.stop()

    def get_camera(self, camera_id: str) -> Optional[StreamReader]:
        """Retrieves a StreamReader instance by camera ID."""
        return self._cameras.get(camera_id)

    def get_all_cameras(self) -> Dict[str, StreamReader]:
        """Returns map of camera_id -> StreamReader."""
        return self._cameras

    def get_statuses(self) -> Dict[str, Dict[str, Any]]:
        """
        Returns health and connectivity information for each registered camera.
        """
        statuses = {}
        for cam_id, reader in self._cameras.items():
            statuses[cam_id] = {
                "name": reader.name,
                "status": reader.status.value,
                "is_connected": reader.is_connected,
                "is_ready": reader.is_ready,
                "last_frame_time": reader.last_frame_time,
                "source_masked": mask_url(reader.source),
            }
        return statuses

    def count_connected(self) -> int:
        """Returns the number of currently connected cameras."""
        return sum(1 for r in self._cameras.values() if r.is_connected)

    def count_ready(self) -> int:
        """Returns the number of cameras with a live worker and a fresh frame."""
        return sum(1 for r in self._cameras.values() if r.is_ready)

    def count_total(self) -> int:
        """Returns the total number of registered (enabled) cameras."""
        return len(self._cameras)

    def all_connected(self) -> bool:
        """Returns True if every enabled camera is currently connected."""
        if not self._cameras:
            return False
        return all(r.is_connected for r in self._cameras.values())

    def all_ready(self) -> bool:
        """Returns True only when every enabled camera is producing fresh frames."""
        if not self._cameras:
            return False
        return all(r.is_ready for r in self._cameras.values())

    def any_connected(self) -> bool:
        """Returns True if at least one enabled camera is connected."""
        return any(r.is_connected for r in self._cameras.values())
