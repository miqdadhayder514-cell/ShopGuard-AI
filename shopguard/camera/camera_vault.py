"""
ShopGuard AI - Secure Camera Vault & Configuration Storage
Provides encrypted storage for CCTV/RTSP camera credentials and configurations.
Uses Fernet (AES-128-CBC + HMAC-SHA256) authenticated symmetric encryption.
Passwords and full credential-bearing URLs are never written to plaintext JSON or logs.
"""

import json
import os
import re
import threading
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, urlunparse

from cryptography.fernet import Fernet
from ..utils.logger import get_logger, mask_url

logger = get_logger("camera.vault")

DEFAULT_KEY_FILE = "config/camera_vault.key"
DEFAULT_STORE_FILE = "config/cameras_managed.json"


def normalize_rtsp_components(
    ip_or_host: str,
    port: int = 554,
    username: Optional[str] = None,
    password: Optional[str] = None,
    stream_path: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Constructs:
      1. Full connection URL with credentials (for internal stream reader).
      2. Sanitized/masked URL for logging and UI display.
    """
    host_clean = ip_or_host.strip()
    # Strip scheme if accidentally included in host
    if host_clean.lower().startswith("rtsp://"):
        host_clean = host_clean[7:]
    elif host_clean.lower().startswith("rtsps://"):
        host_clean = host_clean[8:]

    # Remove trailing colons or slashes from host
    host_clean = host_clean.rstrip("/:")

    path_clean = (stream_path or "").strip()
    if path_clean and not path_clean.startswith("/"):
        path_clean = "/" + path_clean

    port_str = f":{port}" if port and port != 554 else ""
    if port and port == 554:
        port_str = ":554"

    user_clean = (username or "").strip()
    pass_clean = (password or "").strip()

    if user_clean and pass_clean:
        auth_part = f"{user_clean}:{pass_clean}@"
        auth_masked = f"{user_clean}:***@"
    elif user_clean:
        auth_part = f"{user_clean}@"
        auth_masked = f"{user_clean}@"
    else:
        auth_part = ""
        auth_masked = ""

    full_url = f"rtsp://{auth_part}{host_clean}{port_str}{path_clean}"
    masked_url = f"rtsp://{auth_masked}{host_clean}{port_str}{path_clean}"
    return full_url, masked_url


def parse_rtsp_url(url: str) -> Dict[str, Any]:
    """
    Parses an RTSP URL into discrete connection components.
    """
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in ("rtsp", "rtsps", "http", "https"):
        raise ValueError(f"Unsupported stream scheme '{scheme}'. Must start with rtsp:// or rtsps://")

    host = parsed.hostname or ""
    port = parsed.port or (554 if "rtsp" in scheme else 80)
    user = parsed.username or ""
    passwd = parsed.password or ""
    path = parsed.path or ""
    if parsed.query:
        path = f"{path}?{parsed.query}"

    return {
        "ip_address": host,
        "port": port,
        "username": user,
        "password": passwd,
        "stream_path": path,
    }


class CameraVault:
    """
    Encrypted persistent store for camera configurations.
    Protects camera passwords and full URLs at rest using AES-128-CBC encryption.
    """

    def __init__(
        self,
        store_path: str = DEFAULT_STORE_FILE,
        key_path: str = DEFAULT_KEY_FILE,
    ):
        self.store_path = os.path.abspath(store_path)
        self.key_path = os.path.abspath(key_path)
        self._lock = threading.RLock()
        self._cipher = self._init_cipher()
        self._cameras: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _init_cipher(self) -> Fernet:
        """Loads or creates the 256-bit Fernet key for encrypting camera credentials."""
        os.makedirs(os.path.dirname(self.key_path), exist_ok=True)
        if os.path.isfile(self.key_path):
            try:
                with open(self.key_path, "rb") as f:
                    key = f.read().strip()
                if key:
                    return Fernet(key)
            except Exception as e:
                logger.warning(f"Could not read existing vault key from '{self.key_path}': {e}. Generating new key.")

        new_key = Fernet.generate_key()
        try:
            with open(self.key_path, "wb") as f:
                f.write(new_key)
            logger.info(f"Initialized new Camera Vault encryption key at {self.key_path}")
        except Exception as e:
            logger.error(f"Failed to write vault key to '{self.key_path}': {e}")
        return Fernet(new_key)

    def _encrypt(self, text: str) -> str:
        """Encrypts sensitive plaintext into an ASCII armored ciphertext string."""
        if not text:
            return ""
        return self._cipher.encrypt(text.encode("utf-8")).decode("ascii")

    def _decrypt(self, token: str) -> str:
        """Decrypts ciphertext token into plaintext."""
        if not token:
            return ""
        try:
            return self._cipher.decrypt(token.encode("ascii")).decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to decrypt camera credential: {e}")
            return ""

    def _load(self) -> None:
        """Loads cameras from disk into memory."""
        with self._lock:
            self._cameras = {}
            if not os.path.isfile(self.store_path):
                return
            try:
                with open(self.store_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        cam_id = item.get("id")
                        if cam_id:
                            self._cameras[cam_id] = item
                logger.info(f"Loaded {len(self._cameras)} managed camera(s) from {self.store_path}")
            except Exception as e:
                logger.error(f"Failed to load camera vault store from '{self.store_path}': {e}")

    def _save(self) -> None:
        """Writes current managed cameras to disk securely."""
        with self._lock:
            os.makedirs(os.path.dirname(self.store_path), exist_ok=True)
            try:
                items = list(self._cameras.values())
                # Write to temp file then atomic replace
                tmp_file = self.store_path + ".tmp"
                with open(tmp_file, "w", encoding="utf-8") as f:
                    json.dump(items, f, indent=2)
                os.replace(tmp_file, self.store_path)
            except Exception as e:
                logger.error(f"Failed to persist managed cameras to '{self.store_path}': {e}")

    def get_all(self, include_credentials: bool = False) -> List[Dict[str, Any]]:
        """
        Returns list of all stored camera configurations.
        If include_credentials is False, passwords are removed and full sources are masked.
        """
        with self._lock:
            result = []
            for cam in self._cameras.values():
                item = dict(cam)
                # Decrypt full source and password if requested
                enc_pass = item.pop("encrypted_password", None)
                enc_source = item.pop("encrypted_source", None)

                if include_credentials:
                    item["password"] = self._decrypt(enc_pass) if enc_pass else ""
                    item["source"] = self._decrypt(enc_source) if enc_source else item.get("source_masked", "")
                else:
                    item.pop("password", None)
                    # Provide masked source only
                    item["source"] = item.get("source_masked", "")

                result.append(item)
            return result

    def get(self, camera_id: str, include_credentials: bool = False) -> Optional[Dict[str, Any]]:
        """Retrieves a single camera config by ID."""
        with self._lock:
            cam = self._cameras.get(camera_id)
            if not cam:
                return None
            item = dict(cam)
            enc_pass = item.pop("encrypted_password", None)
            enc_source = item.pop("encrypted_source", None)

            if include_credentials:
                item["password"] = self._decrypt(enc_pass) if enc_pass else ""
                item["source"] = self._decrypt(enc_source) if enc_source else item.get("source_masked", "")
            else:
                item.pop("password", None)
                item["source"] = item.get("source_masked", "")
            return item

    def check_duplicate(
        self,
        camera_id: str,
        host: str,
        port: int,
        stream_path: str,
        exclude_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Checks whether a camera with the same ID or same endpoint (host, port, path)
        already exists.
        Returns: duplicate reason string if duplicate, or None.
        """
        with self._lock:
            for cid, cam in self._cameras.items():
                if exclude_id and cid == exclude_id:
                    continue
                if cid.lower() == camera_id.lower():
                    return f"Camera with ID '{camera_id}' already exists."

                c_host = str(cam.get("ip_address", "")).strip().lower()
                c_port = int(cam.get("port", 554))
                c_path = str(cam.get("stream_path", "")).strip().lower()

                if c_host and c_host == host.strip().lower() and c_port == port and c_path == stream_path.strip().lower():
                    return f"A camera pointing to '{host}:{port}{stream_path}' already exists (ID: '{cid}')."
            return None

    def put(
        self,
        camera_id: str,
        name: str,
        camera_type: str,
        full_source: str,
        source_masked: str,
        ip_address: str,
        port: int,
        username: Optional[str] = None,
        password: Optional[str] = None,
        stream_path: Optional[str] = None,
        location: Optional[str] = None,
        fps: float = 5.0,
        reconnect_interval_seconds: float = 5.0,
        connection_timeout_seconds: float = 10.0,
        enabled: bool = True,
    ) -> Dict[str, Any]:
        """
        Stores or updates an encrypted camera record.
        """
        with self._lock:
            # Preserve existing password if new password is None or empty in update
            enc_password = ""
            if password is not None and password != "":
                enc_password = self._encrypt(password)
            elif camera_id in self._cameras:
                enc_password = self._cameras[camera_id].get("encrypted_password", "")

            enc_source = self._encrypt(full_source)

            record = {
                "id": camera_id,
                "name": name.strip(),
                "camera_type": camera_type.strip(),
                "ip_address": ip_address.strip(),
                "port": port,
                "username": (username or "").strip(),
                "stream_path": (stream_path or "").strip(),
                "location": (location or "").strip(),
                "source_masked": source_masked,
                "fps": float(fps),
                "reconnect_interval_seconds": float(reconnect_interval_seconds),
                "connection_timeout_seconds": float(connection_timeout_seconds),
                "enabled": bool(enabled),
                "encrypted_password": enc_password,
                "encrypted_source": enc_source,
            }

            self._cameras[camera_id] = record
            self._save()
            logger.info(f"Securely saved camera '{name}' ({camera_id}) to Camera Vault.")

            # Return sanitized copy
            res = dict(record)
            res.pop("encrypted_password", None)
            res.pop("encrypted_source", None)
            res["source"] = source_masked
            return res

    def delete(self, camera_id: str) -> bool:
        """Deletes a camera configuration from the vault."""
        with self._lock:
            if camera_id in self._cameras:
                del self._cameras[camera_id]
                self._save()
                logger.info(f"Removed camera '{camera_id}' from Camera Vault.")
                return True
            return False


# Global singleton instance
camera_vault = CameraVault()
