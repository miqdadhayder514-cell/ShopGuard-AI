"""
ShopGuard AI - RTSP Diagnostic Utility Tests
Tests syntax checking, credential masking, and error reporting of tools/rtsp_diagnostic.py.
"""

import pytest
from tools.rtsp_diagnostic import probe_rtsp_stream
from shopguard.utils.logger import mask_url


def test_rtsp_diagnostic_url_syntax_validation():
    # Empty URL
    rep_empty = probe_rtsp_stream("")
    assert rep_empty["syntax_valid"] is False
    assert rep_empty["error_stage"] == "URL Parsing"

    # Non-RTSP scheme (HTTP)
    rep_http = probe_rtsp_stream("http://192.168.1.100:80/stream")
    assert rep_http["syntax_valid"] is False
    assert rep_http["error_stage"] == "URL Protocol"

    # Valid syntax
    rep_valid = probe_rtsp_stream("rtsp://admin:secret123@127.0.0.1:554/test", timeout=0.1)
    assert rep_valid["syntax_valid"] is True


def test_rtsp_diagnostic_masks_credentials():
    url = "rtsp://shop_owner:SuperSecretP@ss99@192.168.1.55:554/h264"
    masked = mask_url(url)
    assert "SuperSecretP@ss99" not in masked
    assert "shop_owner:***@" in masked

    rep = probe_rtsp_stream(url, timeout=0.1)
    assert "SuperSecretP@ss99" not in rep["url_masked"]
    assert "shop_owner:***@" in rep["url_masked"]
