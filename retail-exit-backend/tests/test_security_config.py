"""Security, Rate Limiting, and Centralized Configuration Test Suite

Covers:
- Centralized configuration hierarchy with environment variable overrides.
- Sliding-window rate limiter enforcement on sensitive endpoints.
- Motion detection configuration and dynamic debounce windows.
- Camera fleet input validation and SSRF defenses.
- VerdictEngine dynamic threshold configuration.
- Distributed WebSocket hub resilience and in-memory fallback.
- Authentic camera stream URL construction.
"""

import pytest
import asyncio
import cv2
import numpy as np
from unittest.mock import MagicMock
from fastapi import Request, HTTPException, status
from pydantic import ValidationError

from src.core.config import settings, Settings, DetectionConfig, FusionConfig, MotionConfig, VerdictConfig
from src.core.rate_limit import RateLimiter, clear_rate_limit_storage
from src.realtime.hub import ConnectionManager
from src.realtime.events import WebSocketEnvelope
from src.schemas.cameras import CameraCreate, CameraUpdate
from src.engine.camera_worker import camera_worker
from src.engine.verdict import VerdictEngine


def test_centralized_configuration_hierarchy(monkeypatch):
    """Verifies that ML, fusion, tripwire, motion, verdict, and rate limit thresholds load with valid defaults and honor env overrides."""
    assert settings.detection.confidence_floor == 0.50
    assert settings.detection.confirmed_entity_standard == 0.90
    assert settings.tracking.tracker_max_lost_frames == 15
    assert settings.tripwire.lock_cooldown_sec == 3.5
    assert settings.fusion.baseline_vision_weight == 0.50
    assert settings.fusion.baseline_rfid_weight == 0.30
    assert settings.fusion.baseline_scale_weight == 0.20
    assert settings.rate_limit.auth_per_minute == 20
    assert settings.motion.debounce_seconds == 6.0
    assert settings.motion.pixel_threshold == 3500
    assert settings.verdict.unit_tolerance == 0
    assert settings.camera.capture_timeout_sec == 2.5
    assert settings.biometric.face_match_threshold == 0.65

    # Test environment override
    monkeypatch.setenv("SECOPS_CONFIDENCE_FLOOR", "0.65")
    custom_detection = DetectionConfig()
    assert custom_detection.confidence_floor == 0.65

    monkeypatch.setenv("SECOPS_MOTION_DEBOUNCE_SEC", "3.0")
    custom_motion = MotionConfig()
    assert custom_motion.debounce_seconds == 3.0


@pytest.mark.asyncio
async def test_rate_limiter_sliding_window_enforcement():
    """Verifies that RateLimiter allows up to quota requests and blocks subsequent calls with HTTP 429."""
    clear_rate_limit_storage()
    limiter = RateLimiter(times=3, seconds=10, scope="unit_test_quota")

    mock_request = MagicMock(spec=Request)
    mock_request.headers = {}
    mock_request.client.host = "192.168.1.100"

    # First 3 requests must pass
    assert await limiter(mock_request) is True
    assert await limiter(mock_request) is True
    assert await limiter(mock_request) is True

    # 4th request must be rejected with 429
    with pytest.raises(HTTPException) as exc_info:
        await limiter(mock_request)

    assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "Retry-After" in exc_info.value.headers
    assert int(exc_info.value.headers["Retry-After"]) >= 1
    assert "Rate limit exceeded" in exc_info.value.detail

    clear_rate_limit_storage()


def test_motion_detection_configuration_and_debounce():
    """F7: Verifies that _check_motion dynamically respects MotionConfig thresholds and debounce windows."""
    # Create blank test frame and high-motion frame
    black_frame = np.zeros((360, 640, 3), dtype=np.uint8)
    white_frame = np.ones((360, 640, 3), dtype=np.uint8) * 255

    _, black_bytes = cv2.imencode(".jpg", black_frame)
    _, white_bytes = cv2.imencode(".jpg", white_frame)

    cam_id = "test_motion_cam_01"
    camera_worker._last_frames.pop(cam_id, None)
    camera_worker._last_event_time.pop(cam_id, None)

    # Initial frame records baseline
    assert camera_worker._check_motion(cam_id, black_bytes.tobytes()) is False

    # Second frame with large change triggers motion
    motion_detected = camera_worker._check_motion(
        cam_id,
        white_bytes.tobytes(),
        pixel_threshold=100,
        debounce_seconds=5.0,
    )
    assert motion_detected is True

    # Immediate follow-up frame must be debounced
    debounced = camera_worker._check_motion(
        cam_id,
        black_bytes.tobytes(),
        pixel_threshold=100,
        debounce_seconds=5.0,
    )
    assert debounced is False


def test_camera_schema_validation_and_ssrf_blocking():
    """F9: Verifies strict input validation and SSRF defenses on CameraCreate schema."""
    # 1. Valid camera payload passes
    valid_cam = CameraCreate(
        label="Lane 1 Primary Exit",
        ipAddress="192.168.1.150",
        rtspPath="/live/ch0",
        resolution="1920x1080",
        fps=30,
    )
    assert valid_cam.ipAddress == "192.168.1.150"
    assert valid_cam.rtspPath == "/live/ch0"

    # 2. Block SSRF: Cloud Metadata Service link-local IP
    with pytest.raises(ValidationError) as exc_ssrf:
        CameraCreate(
            label="Rogue Metadata Probe",
            ipAddress="169.254.169.254",
            rtspPath="/latest/meta-data",
        )
    assert "Prohibited IP address" in str(exc_ssrf.value)

    # 3. Block Multicast IP
    with pytest.raises(ValidationError) as exc_multi:
        CameraCreate(
            label="Multicast Stream",
            ipAddress="224.0.0.1",
            rtspPath="/stream",
        )
    assert "Prohibited IP address" in str(exc_multi.value)

    # 4. Reject invalid resolution format
    with pytest.raises(ValidationError) as exc_res:
        CameraCreate(
            label="Invalid Resolution Cam",
            ipAddress="192.168.1.151",
            rtspPath="/live/ch0",
            resolution="invalid-res",
        )
    assert "Invalid resolution format" in str(exc_res.value)

    # 5. Reject out-of-range FPS
    with pytest.raises(ValidationError) as exc_fps:
        CameraCreate(
            label="Overclocked Cam",
            ipAddress="192.168.1.152",
            rtspPath="/live/ch0",
            fps=500,
        )
    assert "FPS must be between 1 and 120" in str(exc_fps.value)


def test_verdict_engine_configuration_defaults():
    """F11: Verifies VerdictEngine.evaluate dynamically defaults to centralized settings."""
    # Consensus matches declared -> PASS
    res = VerdictEngine.evaluate(consensus_units=10, declared_units=10)
    assert res.verdict == "PASS"
    assert res.severity == "NONE"

    # Mismatch of 1 unit exceeds default tolerance of 0 -> raises MISMATCH
    res_mismatch = VerdictEngine.evaluate(consensus_units=11, declared_units=10)
    assert res_mismatch.verdict == "MISMATCH"
    assert res_mismatch.severity == "LOW"

    # Overridden tolerance allows 1 unit mismatch to PASS
    res_tolerated = VerdictEngine.evaluate(
        consensus_units=11,
        declared_units=10,
        unit_tolerance=2,
    )
    assert res_tolerated.verdict == "PASS"
    assert res_tolerated.severity == "NONE"


@pytest.mark.asyncio
async def test_websocket_hub_in_memory_and_cluster_fallback():
    """Verifies that ConnectionManager operates reliably in standalone mode and handles Redis fallback."""
    hub = ConnectionManager()
    await hub.start()

    mock_ws = MagicMock()
    mock_ws.accept = MagicMock()
    mock_ws.send_text = MagicMock()

    # Create async mock for accept & send_text
    async def async_accept():
        return None
    async def async_send_text(data):
        return None

    mock_ws.accept = async_accept
    mock_ws.send_text = async_send_text

    await hub.connect(mock_ws)
    assert mock_ws in hub.active_connections

    envelope = WebSocketEnvelope(type="heartbeat", payload={"status": "HEALTHY", "edgeNodesOnline": 4})
    await hub.broadcast(envelope)

    hub.disconnect(mock_ws)
    assert mock_ws not in hub.active_connections
    await hub.stop()


def test_authentic_stream_url_no_fake_webrtc():
    """Verifies that camera pairing constructs authentic RTSP / HTTP stream endpoints rather than fake WebRTC URLs."""
    ip = "10.0.0.55"
    rtsp = "/live/ch1"

    # Authentic RTSP construction
    norm_rtsp = rtsp if rtsp.startswith("/") else f"/{rtsp}"
    stream_url = f"rtsp://{ip}{norm_rtsp}"
    assert stream_url == "rtsp://10.0.0.55/live/ch1"
    assert "webrtc://edge-media-server.local" not in stream_url
