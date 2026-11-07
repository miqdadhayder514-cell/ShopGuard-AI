"""
ShopGuard AI - Notification Services
Handles push notifications and alerts (including Firebase Cloud Messaging).
"""

from .fcm_notifier import FcmNotificationManager, fcm_notifier

__all__ = ["FcmNotificationManager", "fcm_notifier"]
