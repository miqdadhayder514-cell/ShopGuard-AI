"""
ShopGuard AI - Firebase Cloud Messaging (FCM) Notification Dispatcher
Manages persistent device registration tokens and dispatches real-time security alerts
to registered mobile devices via Firebase Admin SDK.
"""

from datetime import datetime, timezone
import json
import os
import threading
import warnings
from typing import Any, Dict, List, Optional

try:
    import firebase_admin
    from firebase_admin import credentials, messaging
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    firebase_admin = None
    credentials = None
    messaging = None

from ..utils.logger import get_logger

logger = get_logger("notifications.fcm")


def mask_token(token: str) -> str:
    """Masks an FCM token for privacy and security in logs."""
    if not token:
        return "fcm_empty"
    token = token.strip()
    if len(token) > 12:
        return f"{token[:6]}...{token[-6:]}"
    return "fcm_***"


class FcmNotificationManager:
    """
    Thread-safe manager for device tokens and Firebase push notification dispatching.
    Safely degrades if Firebase credentials are not yet configured.
    """

    DEFAULT_CREDENTIALS_FILE = "config/firebase_credentials.json"
    DEFAULT_TOKENS_FILE = "config/fcm_tokens.json"

    def __init__(
        self,
        credentials_file: str = DEFAULT_CREDENTIALS_FILE,
        tokens_file: str = DEFAULT_TOKENS_FILE,
        app_name: str = "shopguard_fcm",
    ):
        self.credentials_file = credentials_file
        self.tokens_file = tokens_file
        self.app_name = app_name
        self._lock = threading.Lock()
        self._tokens: Dict[str, Dict[str, Any]] = {}
        self._app: Optional[Any] = None
        self.is_configured: bool = False

        self._load_tokens()
        self._init_firebase()

    def _init_firebase(self) -> None:
        """Initializes Firebase Admin SDK if credentials file exists and library is installed."""
        if not FIREBASE_AVAILABLE:
            logger.warning("firebase-admin package is not installed. Push notifications disabled.")
            self.is_configured = False
            return

        if not os.path.isfile(self.credentials_file):
            logger.info(
                f"Firebase credentials not found at '{self.credentials_file}'. "
                "FCM push notifications will remain in standby until service-account JSON is placed."
            )
            self.is_configured = False
            return

        try:
            # Check if app is already initialized under this app_name
            try:
                self._app = firebase_admin.get_app(self.app_name)
            except ValueError:
                cred = credentials.Certificate(self.credentials_file)
                self._app = firebase_admin.initialize_app(cred, name=self.app_name)

            self.is_configured = True
            logger.info(
                f"Firebase Admin SDK successfully initialized from '{self.credentials_file}' "
                f"(app_name='{self.app_name}')."
            )
        except Exception as e:
            logger.error(f"Failed to initialize Firebase Admin SDK from '{self.credentials_file}': {e}", exc_info=True)
            self.is_configured = False

    def reload_credentials(self) -> bool:
        """Attempts to reinitialize Firebase credentials if they were placed after startup."""
        with self._lock:
            self._init_firebase()
            return self.is_configured

    def _load_tokens(self) -> None:
        """Loads stored device tokens from disk."""
        with self._lock:
            if not os.path.isfile(self.tokens_file):
                self._tokens = {}
                return

            try:
                with open(self.tokens_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "tokens" in data and isinstance(data["tokens"], dict):
                        self._tokens = data["tokens"]
                    elif isinstance(data, dict):
                        self._tokens = data
                    else:
                        self._tokens = {}
                logger.info(f"Loaded {len(self._tokens)} FCM device registration token(s) from '{self.tokens_file}'.")
            except Exception as e:
                logger.error(f"Failed to load FCM tokens from '{self.tokens_file}': {e}")
                self._tokens = {}

    def _save_tokens_locked(self) -> None:
        """Persists stored device tokens to disk under self._lock."""
        try:
            os.makedirs(os.path.dirname(self.tokens_file) or ".", exist_ok=True)
            data = {"tokens": self._tokens}
            temp_file = f"{self.tokens_file}.tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(temp_file, self.tokens_file)
        except Exception as e:
            logger.error(f"Failed to save FCM tokens to '{self.tokens_file}': {e}")

    def register_token(
        self,
        token: str,
        device_name: str = "Android Device",
        app_version: str = "1.0.0",
    ) -> int:
        """
        Registers or updates an FCM device token.
        Returns total count of registered tokens.
        """
        if not token or not isinstance(token, str):
            raise ValueError("Token must be a non-empty string.")

        token = token.strip()
        if len(token) < 10 or len(token) > 4096:
            raise ValueError(f"Invalid FCM token length: {len(token)} (expected 10-4096 characters).")

        now = datetime.now(timezone.utc)
        with self._lock:
            self._tokens[token] = {
                "device_name": str(device_name)[:100],
                "app_version": str(app_version)[:50],
                "registered_at": now.timestamp(),
                "registered_at_iso": now.isoformat(),
            }
            self._save_tokens_locked()
            count = len(self._tokens)

        logger.info(
            f"Registered device token {mask_token(token)} for '{device_name}' (v{app_version}). "
            f"Total active devices: {count}"
        )
        return count

    def unregister_token(self, token: str) -> bool:
        """
        Removes an FCM device token.
        Returns True if the token was removed, False if not found.
        """
        if not token:
            return False

        token = token.strip()
        with self._lock:
            if token in self._tokens:
                del self._tokens[token]
                self._save_tokens_locked()
                logger.info(f"Unregistered device token {mask_token(token)}. Remaining: {len(self._tokens)}")
                return True
            return False

    def get_tokens(self) -> List[str]:
        """Returns list of currently registered token strings."""
        with self._lock:
            return list(self._tokens.keys())

    def get_token_count(self) -> int:
        """Returns total count of active registered tokens."""
        with self._lock:
            return len(self._tokens)

    def get_status(self) -> Dict[str, Any]:
        """Returns operational status of the FCM notifier."""
        with self._lock:
            return {
                "configured": self.is_configured,
                "credentials_present": os.path.isfile(self.credentials_file),
                "tokens_count": len(self._tokens),
            }

    def send_security_alert(
        self,
        incident_id: str,
        event_type: str,
        camera_name: str,
        camera_id: str = "",
        timestamp_iso: Optional[str] = None,
        confidence: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Dispatches a high-priority push notification to all registered Android devices.
        Automatically prunes expired/unregistered tokens.
        """
        tokens_list = self.get_tokens()
        if not tokens_list:
            logger.debug("No registered devices for security alert dispatch.")
            return {
                "sent": 0,
                "failed": 0,
                "pruned": 0,
                "total_targets": 0,
                "status": "no_recipients",
            }

        if not self.is_configured or not FIREBASE_AVAILABLE or self._app is None:
            logger.warning(
                f"Cannot dispatch security alert for incident '{incident_id}': "
                "Firebase Admin SDK is not configured."
            )
            return {
                "sent": 0,
                "failed": 0,
                "pruned": 0,
                "total_targets": len(tokens_list),
                "status": "unconfigured",
            }

        iso = timestamp_iso or datetime.now(timezone.utc).isoformat()
        conf_str = f"{confidence:.2f}" if confidence is not None else "0.90"

        title = f"🚨 SECURITY ALERT: {event_type.replace('_', ' ').title()}"
        body = f"Intrusion detected on {camera_name}. Tap to review."

        data_payload = {
            "incident_id": str(incident_id),
            "event_type": str(event_type),
            "camera_name": str(camera_name),
            "camera_id": str(camera_id),
            "event_timestamp": iso,
            "detection_time": iso,
            "confidence": conf_str,
            "alert_title": title,
            "alert_body": body,
        }

        android_cfg = messaging.AndroidConfig(
            priority="high",
            # No AndroidNotification here — keeping this a data-only message so that
            # onMessageReceived() is ALWAYS called on the device regardless of whether
            # the app is foregrounded or backgrounded. If a notification field is present,
            # Android delivers it directly to the system tray and skips onMessageReceived,
            # which prevents SecurityAlarmService from starting.
            # The Android app handles its own notification display inside onMessageReceived.
            data=data_payload,
        )

        # Build one Message per FCM registration token (modern send_each API).
        # Data-only message (no notification= field) ensures onMessageReceived is
        # always invoked on Android whether the app is in foreground OR background.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            messages = [
                messaging.Message(
                    token=t,
                    data=data_payload,
                    android=android_cfg,
                )
                for t in tokens_list
            ]

        try:
            logger.info(
                f"Dispatching FCM security alert for incident '{incident_id}' "
                f"to {len(tokens_list)} device(s)..."
            )
            response = messaging.send_each(messages, app=self._app)
            logger.info(
                f"FCM security alert result: {response.success_count} succeeded, "
                f"{response.failure_count} failed."
            )

            # Auto-prune dead/unregistered tokens — log full error details for diagnosis
            pruned_count = 0
            if response.failure_count > 0:
                for idx, resp in enumerate(response.responses):
                    if not resp.success:
                        exc = resp.exception
                        exc_type = type(exc).__name__
                        exc_code = getattr(exc, 'code', None)
                        exc_cause = getattr(exc, 'cause', None)
                        http_response = getattr(exc_cause, 'response', None)
                        http_status = getattr(http_response, 'status_code', None)
                        logger.warning(
                            f"FCM delivery failed for token {mask_token(tokens_list[idx])}: "
                            f"type={exc_type}, code={exc_code}, http_status={http_status}, detail={exc}"
                        )
                        if isinstance(
                            exc,
                            (messaging.UnregisteredError, messaging.SenderIdMismatchError),
                        ):
                            self.unregister_token(tokens_list[idx])
                            pruned_count += 1

            return {
                "sent": response.success_count,
                "failed": response.failure_count,
                "pruned": pruned_count,
                "total_targets": len(tokens_list),
                "status": "sent",
            }
        except Exception as e:
            logger.error(f"Error executing FCM multicast send: {e}", exc_info=True)
            return {
                "sent": 0,
                "failed": len(tokens_list),
                "pruned": 0,
                "total_targets": len(tokens_list),
                "status": "error",
                "error": str(e),
            }

    def send_test_notification(
        self,
        title: str = "ShopGuard AI Test Alert",
        body: str = "This is a test notification from your Windows security agent.",
    ) -> Dict[str, Any]:
        """Sends a test push notification to verify FCM pipeline without triggering an intrusion."""
        return self.send_security_alert(
            incident_id="test_alert_001",
            event_type="TEST_NOTIFICATION",
            camera_name="Test Station",
            camera_id="cam_test",
            confidence=1.0,
        )


# Global default instance
fcm_notifier = FcmNotificationManager()
