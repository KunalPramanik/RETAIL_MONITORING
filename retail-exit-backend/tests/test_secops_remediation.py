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
    rotate_ciphertext,
    erase_biometric_embedding,
    reset_fernet_instance,
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
# 2. MultiFernet Encryption, Key Rotation & Secure Erasure Tests (R8)
# =============================================================================

def test_fernet_string_encryption_roundtrip():
    secret = "rtsp://admin:super_secret_password@192.168.1.50:554/stream"
    encrypted = encrypt_string(secret)
    assert encrypted != secret
    assert encrypted.startswith("enc:v1:")
    
    decrypted = decrypt_string(encrypted)
    assert decrypted == secret


def test_fernet_json_encryption_roundtrip():
    payload = {"rtsp_url": "rtsp://cam1", "user": "admin", "token": "abc123xyz"}
    encrypted = encrypt_json(payload)
    assert isinstance(encrypted, str)
    assert encrypted.startswith("enc:v1:")
    
    decrypted = decrypt_json(encrypted)
    assert decrypted == payload


def test_fernet_legacy_plaintext_and_unversioned_fallback():
    # Legacy plain text without encryption
    plaintext = "legacy_unencrypted_credential"
    assert decrypt_string(plaintext) == plaintext
    
    # Legacy unversioned enc: prefix
    from cryptography.fernet import Fernet
    from src.core.encryption import get_encryption_keys
    primary_key = get_encryption_keys()[0]
    legacy_token = f"enc:{Fernet(primary_key).encrypt(b'unversioned_secret').decode('utf-8')}"
    assert decrypt_string(legacy_token) == "unversioned_secret"

    raw_json_str = '{"user": "legacy", "verified": true}'
    decrypted_json = decrypt_json(raw_json_str)
    assert decrypted_json == {"user": "legacy", "verified": True}


def test_multifernet_key_rotation():
    """Verify MultiFernet decrypts with secondary retiring keys and rotates to primary."""
    import os
    from cryptography.fernet import Fernet
    
    # Generate two distinct 32-byte Fernet keys
    old_key = Fernet.generate_key().decode("utf-8")
    new_primary_key = Fernet.generate_key().decode("utf-8")
    
    # Token encrypted under old key
    old_cipher = Fernet(old_key.encode("utf-8"))
    old_ciphertext = f"enc:v1:{old_cipher.encrypt(b'confidential_data_payload').decode('utf-8')}"
    
    # Configure MultiFernet with new key first (primary), then old key
    orig_keys_env = os.environ.get("SECOPS_ENCRYPTION_KEYS")
    try:
        os.environ["SECOPS_ENCRYPTION_KEYS"] = f"{new_primary_key},{old_key}"
        reset_fernet_instance()
        
        # 1. Decrypts old ciphertext seamlessly
        assert decrypt_string(old_ciphertext) == "confidential_data_payload"
        
        # 2. Rotate ciphertext to re-encrypt under new primary key
        rotated = rotate_ciphertext(old_ciphertext)
        assert rotated != old_ciphertext
        assert rotated.startswith("enc:v1:")
        assert decrypt_string(rotated) == "confidential_data_payload"
        
        # 3. New primary key alone can decrypt the rotated token
        raw_rotated = rotated.replace("enc:v1:", "")
        new_cipher = Fernet(new_primary_key.encode("utf-8"))
        assert new_cipher.decrypt(raw_rotated.encode("utf-8")).decode("utf-8") == "confidential_data_payload"
    finally:
        if orig_keys_env is not None:
            os.environ["SECOPS_ENCRYPTION_KEYS"] = orig_keys_env
        else:
            os.environ.pop("SECOPS_ENCRYPTION_KEYS", None)
        reset_fernet_instance()


def test_biometric_secure_erasure():
    """Verify explicit erasure zeros and clears biometric embedding vectors."""
    class MockEmployee:
        def __init__(self):
            self.face_embedding = [0.123, -0.456, 0.789, 0.321]
            self.embedding_updated_at = datetime.now(timezone.utc)
    
    emp = MockEmployee()
    assert emp.face_embedding is not None
    assert len(emp.face_embedding) == 4
    
    erase_biometric_embedding(emp)
    assert emp.face_embedding is None
    assert emp.embedding_updated_at is None


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


# =============================================================================
# 11. Concealment Posture & Non-Accusatory Alert Tests (R7 / Req 9.5)
# =============================================================================

def test_concealment_posture_innocent_actions_no_false_positives():
    """Verify innocent customer actions (standing, sitting, walking) never trigger concealment alerts."""
    cam_id = "test_cam_innocent"
    tid = "track_innocent_1"
    PostureClassifier.cleanup_track(cam_id, tid)

    # 1. Standing posture
    stand_res = PostureClassifier.classify_posture([100, 100, 80, 240], camera_id=cam_id, track_id=tid)
    is_anomaly, details = PostureClassifier.evaluate_concealment_risk(cam_id, tid, stand_res)
    assert is_anomaly is False
    assert details is None

    # 2. Sitting posture
    sit_res = PostureClassifier.classify_posture([100, 100, 100, 150], camera_id=cam_id, track_id=tid)
    is_anomaly, details = PostureClassifier.evaluate_concealment_risk(cam_id, tid, sit_res)
    assert is_anomaly is False
    assert details is None


def test_concealment_posture_sustained_crouch_detection():
    """Verify sustained crouching in merchandise area generates non-accusatory alert per Req 9.5."""
    cam_id = "test_cam_crouch"
    tid = "track_crouch_1"
    PostureClassifier.cleanup_track(cam_id, tid)

    now = 1000.0
    crouch_res = PostureClassifier.classify_posture(
        [100, 100, 100, 120],  # crouching aspect ratio
        camera_id=cam_id,
        track_id=tid,
        timestamp=now,
    )
    assert crouch_res.posture == PostureState.CROUCHING

    # Momentary crouch (1 second) -> No alert
    is_anomaly, details = PostureClassifier.evaluate_concealment_risk(cam_id, tid, crouch_res, timestamp=now + 1.0)
    assert is_anomaly is False

    # Sustained crouch (5 seconds >= threshold) -> Triggers alert
    is_anomaly, details = PostureClassifier.evaluate_concealment_risk(cam_id, tid, crouch_res, timestamp=now + 5.0)
    assert is_anomaly is True
    assert details is not None
    assert details["non_accusatory"] is True
    assert details["requirement_id"] == "REQ_9_5"
    assert "Possible Concealment Anomaly" in details["description"]
    # Check that forbidden accusatory words are NOT in the description
    for forbidden in ["theft", "thief", "steal", "stealing", "criminal", "guilty", "shoplifter"]:
        assert forbidden not in details["description"].lower()
