import pytest
import time
import io
import cv2
import numpy as np
from datetime import datetime, timezone
from httpx import AsyncClient

from src.ml.posture_service import PostureClassifier, PostureState
from src.core.encryption import (
    encrypt_string,
    decrypt_string,
    encrypt_json,
    decrypt_json,
)
from src.security import revoke_token, is_token_revoked, create_access_token
from src.engine.motion_detector import MotionDetector
from src.ml.anti_tailgating.concealment_service import ConcealmentDetectionService
from src.engine.inventory_ledger_engine import InventoryLedgerEngine
from src.engine.camera_worker import camera_worker
from src.db.models.camera import Camera
from src.db.models.misc import Material
from src.core.config import settings


# =============================================================================
# 1. Posture Classification & Static Object Suppression Tests
# =============================================================================

def test_posture_classifier_standing_aspect_ratio():
    """Test fallback aspect ratio classification for standing."""
    cam_id = "test_cam_stand"
    tid = "track_stand_1"
    PostureClassifier.cleanup_track(cam_id, tid)
    
    # Tall bounding box (height >> width) typical of standing person: h/w = 3.0
    bbox = [100, 100, 80, 240]
    result = PostureClassifier.classify_posture(
        person_bbox=bbox,
        camera_id=cam_id,
        track_id=tid,
        keypoints=None,
        frame_h=1080,
        frame_w=1920,
    )
    assert result.posture == PostureState.STANDING
    assert result.confidence > 0.5
    assert not result.is_static_false_positive


def test_posture_classifier_sitting_aspect_ratio():
    """Test fallback aspect ratio classification for sitting."""
    cam_id = "test_cam_sit"
    tid = "track_sit_1"
    PostureClassifier.cleanup_track(cam_id, tid)
    
    # Seated person box: height = 150, width = 100 -> aspect ratio = 1.50
    bbox = [100, 100, 100, 150]
    result = PostureClassifier.classify_posture(
        person_bbox=bbox,
        camera_id=cam_id,
        track_id=tid,
        keypoints=None,
        frame_h=1080,
        frame_w=1920,
    )
    assert result.posture == PostureState.SITTING
    assert result.confidence > 0.5


def test_posture_classifier_temporal_smoothing():
    """Test temporal majority voting across frames."""
    cam_id = "test_cam_smooth"
    tid = "track_smooth_1"
    PostureClassifier.cleanup_track(cam_id, tid)
    
    # Feed 3 standing frames
    for _ in range(3):
        res = PostureClassifier.classify_posture(
            person_bbox=[100, 100, 80, 240],
            camera_id=cam_id,
            track_id=tid,
        )
    assert res.posture == PostureState.STANDING
    
    # 1 momentary glitch frame shouldn't immediately flip majority
    res2 = PostureClassifier.classify_posture(
        person_bbox=[100, 100, 100, 150],
        camera_id=cam_id,
        track_id=tid,
    )
    assert res2.posture == PostureState.STANDING


def test_static_false_positive_detection():
    """Test static object suppression for mannequin/poster motionless >= 30s."""
    cam_id = "test_cam_static"
    tid = "track_static_1"
    PostureClassifier.cleanup_track(cam_id, tid)
    now = time.time()
    
    # Simulate track staying at same position for 35 seconds
    PostureClassifier._track_first_seen.setdefault(cam_id, {})[tid] = now - 35.0
    PostureClassifier._track_initial_pos.setdefault(cam_id, {})[tid] = (500.0, 500.0)
    
    # Standing box at virtually identical centroid
    res = PostureClassifier.classify_posture(
        person_bbox=[460, 380, 80, 240],  # centroid (500, 500)
        camera_id=cam_id,
        track_id=tid,
        timestamp=now,
    )
    assert res.is_static_false_positive is True


# =============================================================================
# 2. Fernet Encryption & Legacy Plaintext Fallback Tests
# =============================================================================

def test_fernet_string_encryption_roundtrip():
    secret = "rtsp://admin:super_secret_password@192.168.1.50:554/stream"
    encrypted = encrypt_string(secret)
    assert encrypted != secret
    assert encrypted.startswith("enc:")
    
    decrypted = decrypt_string(encrypted)
    assert decrypted == secret


def test_fernet_json_encryption_roundtrip():
    payload = {"rtsp_url": "rtsp://cam1", "user": "admin", "token": "abc123xyz"}
    encrypted = encrypt_json(payload)
    assert isinstance(encrypted, str)
    assert encrypted.startswith("enc:")
    
    decrypted = decrypt_json(encrypted)
    assert decrypted == payload


def test_fernet_legacy_plaintext_fallback():
    plaintext = "legacy_unencrypted_credential"
    assert decrypt_string(plaintext) == plaintext
    
    raw_json_str = '{"user": "legacy", "verified": true}'
    decrypted_json = decrypt_json(raw_json_str)
    assert decrypted_json == {"user": "legacy", "verified": True}


# =============================================================================
# 3. Session Lockout & Token Revocation Tests
# =============================================================================

def test_token_revocation_lifecycle():
    token = create_access_token(subject="user@example.com", role="ADMIN")
    assert not is_token_revoked(token)
    
    revoke_token(token)
    assert is_token_revoked(token)


# =============================================================================
# 4. Motion Detector Dynamic Relative Threshold Tests
# =============================================================================

def test_motion_detector_relative_threshold():
    detector = MotionDetector()
    
    h, w = 240, 320
    f1 = np.zeros((h, w, 3), dtype=np.uint8)
    _, f1_encoded = cv2.imencode(".jpg", f1)
    bytes1 = f1_encoded.tobytes()
    
    # First frame initializes baseline
    motion1 = detector.check_motion(
        camera_id="test_cam_motion",
        frame_bytes=bytes1,
        resize_width=w,
        resize_height=h,
    )
    assert motion1 is False
    
    # Second frame with large white block (significant motion)
    f2 = f1.copy()
    f2[50:180, 50:180] = 255
    _, f2_encoded = cv2.imencode(".jpg", f2)
    bytes2 = f2_encoded.tobytes()
    
    motion2 = detector.check_motion(
        camera_id="test_cam_motion",
        frame_bytes=bytes2,
        resize_width=w,
        resize_height=h,
    )
    assert motion2 is True


# =============================================================================
# 5. Concealment Relative Proximity Tests
# =============================================================================

def test_concealment_relative_proximity_threshold():
    # Leading person box: height = 400px, width = 120px at (100, 100)
    leading_track = {
        "track_id": 1,
        "bbox": [100, 100, 120, 400],
        "confidence": 0.95,
        "velocity": (0.0, 5.0),
    }
    # Trailing person directly behind in lockstep with lower confidence
    trailing_track = {
        "track_id": 2,
        "bbox": [105, 120, 115, 380],
        "confidence": 0.45,
        "velocity": (0.0, 5.0),
    }
    
    is_concealed, details = ConcealmentDetectionService.evaluate_pair(leading_track, trailing_track)
    assert is_concealed is True
    assert details is not None
    assert details["reason"] == "SILHOUETTE_CONCEALMENT"


# =============================================================================
# 6. Camera Worker Non-Fatal Reconnect Backoff & State Transitions
# =============================================================================

@pytest.mark.asyncio
async def test_camera_worker_offline_backoff(db_session):
    cam = Camera(
        camera_id="cam_backoff_test",
        label="Backoff Test Camera",
        ip_address="192.168.1.254",
        status="ONLINE",
    )
    now = datetime.now(timezone.utc)
    
    # 1st missed frame -> DEGRADED with reconnect backoff scheduled
    await camera_worker._handle_offline_camera(cam, db_session, now)
    assert cam.status == "DEGRADED"
    assert "RECONNECTING" in str(cam.degraded_reason)
    assert camera_worker._reconnect_retries[cam.camera_id] == 1
    assert camera_worker._next_poll_ts[cam.camera_id] > time.monotonic()
    
    # Drop frames until max_missed_frames reached -> OFFLINE
    max_missed = getattr(settings.camera, "max_missed_frames", 5) or 5
    for _ in range(max_missed):
        await camera_worker._handle_offline_camera(cam, db_session, now)
    
    assert cam.status == "OFFLINE"
    assert cam.offline_since is not None


# =============================================================================
# 7. Authentic /health Endpoint Tests
# =============================================================================

@pytest.mark.asyncio
async def test_authentic_health_endpoint(async_client: AsyncClient):
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"].upper() in ("HEALTHY", "OK", "DEGRADED")
    assert "database" in data
    assert data["database"] == "CONNECTED"
    assert "cameraFleet" in data
    assert "inferenceRuntime" in data
    assert "worker" in data


# =============================================================================
# 8. Store-Timezone KPI Start-Of-Day Tests
# =============================================================================

@pytest.mark.asyncio
async def test_kpi_live_store_timezone_start_of_day(async_client: AsyncClient):
    response = await async_client.get("/api/kpis/live")
    assert response.status_code == 200
    data = response.json()
    
    assert "startOfDay" in data
    parsed_dt = datetime.fromisoformat(data["startOfDay"])
    assert parsed_dt.tzinfo is not None
    assert "todayThroughputUnits" in data
    assert "openAlertsCount" in data


# =============================================================================
# 9. Negative Stock Policy Tests
# =============================================================================

@pytest.mark.asyncio
async def test_negative_stock_rejection(db_session):
    mat = Material(
        material_id="mat_test_neg_policy",
        sku_code="SKU-NEG-POL-1",
        name="Negative Policy Test Item",
        category="RAW_MATERIAL",
        units_per_package=1,
    )
    db_session.add(mat)
    await db_session.flush()

    with pytest.raises(ValueError, match="prohibited"):
        await InventoryLedgerEngine.record_confirmed_movement(
            session=db_session,
            material_id=mat.material_id,
            transaction_type="ADJUSTMENT",
            unit_quantity=-10,
            allow_negative=False,
        )


# =============================================================================
# 10. Biometric Default-Disabled and Commercial License Gate Tests (R6)
# =============================================================================

def test_biometric_default_disabled():
    """Verify biometrics are strictly disabled by default."""
    from src.core.config import settings
    from src.ml.face_recognition.face_service import FaceRecognitionService

    # Reset in case any prior test touched it
    original_enabled = settings.biometric.enabled
    try:
        settings.biometric.enabled = False
        assert FaceRecognitionService.is_available() is False
        assert FaceRecognitionService.extract_face_embedding(b"fake_frame_bytes") is None
        
        match_res = FaceRecognitionService.match_carrier([0.1]*512, [])
        assert match_res.decision == "DISABLED"

        with pytest.raises(RuntimeError, match="disabled by default"):
            FaceRecognitionService.get_app()
    finally:
        settings.biometric.enabled = original_enabled


def test_biometric_production_commercial_license_gate():
    """Verify production requires commercial license acknowledgement for InsightFace."""
    from src.core.config import settings
    from src.ml.face_recognition.face_service import FaceRecognitionService

    orig_env = settings.ENVIRONMENT
    orig_enabled = settings.biometric.enabled
    orig_ack = settings.biometric.commercial_license_acknowledged
    try:
        settings.ENVIRONMENT = "production"
        settings.biometric.enabled = True
        settings.biometric.commercial_license_acknowledged = False

        assert FaceRecognitionService.is_available() is False
        with pytest.raises(RuntimeError, match="commercial license"):
            FaceRecognitionService.get_app()

        # When acknowledged, is_available() returns True
        settings.biometric.commercial_license_acknowledged = True
        assert FaceRecognitionService.is_available() is True
    finally:
        settings.ENVIRONMENT = orig_env
        settings.biometric.enabled = orig_enabled
        settings.biometric.commercial_license_acknowledged = orig_ack


@pytest.mark.asyncio
async def test_employee_face_enrollment_disabled_by_default(async_client: AsyncClient):
    """Verify employee face upload endpoints return 403 when biometrics disabled."""
    from src.core.config import settings
    orig_enabled = settings.biometric.enabled
    try:
        settings.biometric.enabled = False
        files = {"file": ("face.jpg", b"fake_image_bytes_1234567890", "image/jpeg")}
        resp = await async_client.post("/api/employees/emp-123/photo", files=files)
        assert resp.status_code == 403
        assert "disabled by default" in resp.json()["detail"]
    finally:
        settings.biometric.enabled = orig_enabled
