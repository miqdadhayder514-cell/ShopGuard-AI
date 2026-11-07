"""
ShopGuard AI - Testing Package
Provides test utilities, recorded video evaluation runners, and scenario harness tools.
"""

from .recorded_video_tester import RecordedVideoTester, select_video_file

__all__ = ["RecordedVideoTester", "select_video_file"]
