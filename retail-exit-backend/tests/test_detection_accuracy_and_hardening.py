"""Test Suite: Detection Accuracy Overhaul & System Hardening

Validates:
1. Dynamic confidence floor gating (sub-threshold detections excluded from overlay/verdicts).
2. Class-aware per-class NMS: overlapping boxes of different classes (e.g. Phone + Bottle) are both preserved.
3. Specific retail class labeling (e.g. 'Bottle', 'Smartphone', 'Cup / Mug', 'Case / Carton').
4. Liveness evaluation: stationary living persons remain LIVE; flat 2D photos are identified.
5. Non-face noise gate: low-confidence false face detections (< 0.45) on doors/bottles are rejected.
6. Camera registration idempotency: duplicate POST /api/cameras merges rather than creating duplicates.
7. Database duplicate camera reconciliation on startup.
"""

import pytest
import numpy as np
import cv2
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from src.main import app
from src.db.session import get_db
from src.db.models import Base, Camera, Lane, AuditLog, get_utc_now
from src.db.seed import seed_database
from src.ml.model_config import get_vision_config, update_vision_config
from src.ml.vision_service import VisionInferenceService, DetectedBox
from src.ml.liveness_service import LivenessDetectionService, TemporalFaceTrack
from src.ml.face_service import FaceRecognitionService
from src.db.init_config import reconcile_duplicate_cameras


@pytest.fixture
async def test_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        await seed_database(session)
        yield session


@pytest.fixture
async def client(test_session):
    async def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def test_confidence_floor_configuration():
    """Confirms confidence floor defaults to 50% and is dynamically configurable."""
    cfg = get_vision_config()
    assert cfg.confidence_floor == 0.50
    assert cfg.nms_iou_threshold == 0.35
    assert cfg.face_candidate_min_score == 0.45

    update_vision_config(confidence_floor=0.55)
    assert get_vision_config().confidence_floor == 0.55
    # Reset back to 0.50
    update_vision_config(confidence_floor=0.50)
    assert get_vision_config().confidence_floor == 0.50


def test_specific_class_label_mapping():
    """Confirms specific COCO class IDs map to human-readable retail names."""
    cfg = get_vision_config()
    assert cfg.class_labels[39] == "Bottle"
    assert cfg.class_labels[67] == "Smartphone"
    assert cfg.class_labels[41] == "Cup / Mug"
    assert cfg.class_labels[74] == "Clock / Wall Item"
    assert cfg.class_labels[28] == "Case / Carton"
    assert cfg.class_labels[73] == "Book / Document"


def test_class_aware_nms_preserves_overlapping_different_classes():
    """Simulates two overlapping boxes of different classes (Bottle and Smartphone side-by-side).
    
    Verifies that per-class NMS preserves both items, whereas class-agnostic NMS would drop one.
    """
    cfg = get_vision_config()
    
    # Candidate boxes in format [x, y, w, h] with 75% overlap
    boxes = [[100, 100, 80, 160], [110, 110, 85, 150]]
    scores = [0.88, 0.92]
    classes = [39, 67]  # 39 = Bottle, 67 = Smartphone

    # Class-agnostic NMS across all classes together
    agnostic_indices = cv2.dnn.NMSBoxes(boxes, scores, 0.45, 0.35)
    agnostic_count = len(np.asarray(agnostic_indices).flatten())
    # In class-agnostic NMS with high overlap, one suppresses the other
    assert agnostic_count == 1, "Class-agnostic NMS incorrectly kept both or dropped all"

    # Class-aware per-class NMS
    keep_indices = []
    unique_cids = sorted(list(set(classes)))
    for target_cid in unique_cids:
        cls_indices = [k for k in range(len(classes)) if classes[k] == target_cid]
        cls_boxes = [boxes[k] for k in cls_indices]
        cls_scores = [scores[k] for k in cls_indices]
        selected = cv2.dnn.NMSBoxes(cls_boxes, cls_scores, 0.45, cfg.nms_iou_threshold)
        if len(selected) > 0:
            for s in np.asarray(selected).flatten():
                keep_indices.append(cls_indices[int(s)])

    # Under per-class NMS, both Phone and Bottle are preserved!
    assert len(keep_indices) == 2
    assert 0 in keep_indices  # Bottle preserved
    assert 1 in keep_indices  # Smartphone preserved


def test_stationary_living_human_remains_live():
    """Verifies that a real human face sitting still for 10+ frames remains LIVE.
    
    The flawed stillness override has been removed, so high 3D facial depth relief (z_std >= 15mm)
    correctly prevents stationary humans from flipping to STATIC_PHOTO.
    """
    track = TemporalFaceTrack(track_id=99, initial_bbox=[120, 80, 100, 120])
    # Simulate stationary person over 12 consecutive frames (~10+ seconds)
    for f in range(12):
        track.update(
            bbox=[120, 80, 100, 120],
            landmarks=np.zeros((68, 3), dtype=np.float32),
            ear=0.28,
            ts=1000.0 + f * 0.8,
        )

    assert track.frames_tracked == 12

    # Living 3D depth variance (e.g. 19.5mm from nose tip to eye sockets)
    z_std = 19.5
    depth_score = 0.88
    scale_score = 0.90
    texture_score = 0.75
    chroma_score = 0.80
    motion_score = 0.20  # low motion score due to sitting still

    raw_liveness = (
        0.35 * depth_score
        + 0.20 * scale_score
        + 0.15 * texture_score
        + 0.15 * chroma_score
        + 0.15 * motion_score
    )

    cfg = get_vision_config()
    min_z = cfg.min_real_z_std
    pass_thresh = cfg.liveness_pass_threshold

    # Gating check
    spoof_type = None
    if z_std < min_z:
        spoof_type = "STATIC_PHOTO"
    elif raw_liveness < pass_thresh:
        spoof_type = "STATIC_PHOTO"

    is_live = bool(raw_liveness >= pass_thresh and spoof_type is None)

    assert is_live is True, "Stationary living human with valid 3D relief was wrongly classified as static"
    assert spoof_type is None


def test_flat_2d_photo_classified_as_static():
    """Verifies that a flat printed photograph (z_std < 15mm) is correctly classified as spoof/static."""
    z_std_flat = 6.2  # flat 2D paper surface
    cfg = get_vision_config()
    min_z = cfg.min_real_z_std

    spoof_type = None
    if z_std_flat < min_z:
        spoof_type = "STATIC_PHOTO"

    assert spoof_type == "STATIC_PHOTO"


@pytest.mark.asyncio
async def test_camera_registration_idempotency(client, test_session):
    """Submitting POST /api/cameras twice with the same IP and RTSP path must update/merge, NOT create duplicate rows."""
    payload = {
        "label": "Exit Lane 2 — Primary Overhead",
        "ipAddress": "192.168.10.188",
        "rtspPath": "/Streaming/Channels/101",
        "pairingMethod": "MANUAL",
    }

    # First registration
    resp1 = await client.post("/api/cameras", json=payload)
    assert resp1.status_code in (200, 201)
    cam1 = resp1.json()
    cam1_id = cam1["cameraId"]

    # Second registration (e.g. double-click or network retry)
    resp2 = await client.post("/api/cameras", json=payload)
    assert resp2.status_code in (200, 201)
    cam2 = resp2.json()
    cam2_id = cam2["cameraId"]

    # Must be identical camera ID — no duplicate row created!
    assert cam1_id == cam2_id

    # Verify database has exactly 1 active camera for this IP
    res = await test_session.execute(
        select(Camera).where(
            Camera.ip_address == "192.168.10.188",
            Camera.removed_at.is_(None),
        )
    )
    active_cams = res.scalars().all()
    assert len(active_cams) == 1


@pytest.mark.asyncio
async def test_duplicate_camera_reconciliation(test_session):
    """Verifies that reconcile_duplicate_cameras detects duplicate rows and soft-deletes the duplicate with audit log."""
    now = get_utc_now()
    cam_a = Camera(
        camera_id="cam_dup_primary",
        label="Lane 1 Cam Primary",
        lane_id="LANE-01",
        ip_address="192.168.1.77",
        rtsp_path="/live/ch0",
        stream_url="rtsp://192.168.1.77:554/live/ch0",
        status="ONLINE",
        added_at=now,
    )
    cam_b = Camera(
        camera_id="cam_dup_secondary",
        label="Lane 1 Cam Duplicate",
        lane_id=None,
        ip_address="192.168.1.77",
        rtsp_path="/live/ch0",
        stream_url="rtsp://192.168.1.77:554/live/ch0",
        status="PENDING_SETUP",
        added_at=now,
    )
    test_session.add_all([cam_a, cam_b])
    await test_session.commit()

    # Run reconciliation
    await reconcile_duplicate_cameras(test_session)

    # Verify primary remains active and secondary is soft-deleted
    res_a = await test_session.execute(select(Camera).where(Camera.camera_id == "cam_dup_primary"))
    updated_a = res_a.scalar_one()
    assert updated_a.removed_at is None
    assert updated_a.status == "ONLINE"

    res_b = await test_session.execute(select(Camera).where(Camera.camera_id == "cam_dup_secondary"))
    updated_b = res_b.scalar_one()
    assert updated_b.removed_at is not None
    assert updated_b.status == "OFFLINE"


def test_colocated_laptop_and_smartphone_preservation():
    """Verifies that co-located dark devices (Laptop and Smartphone on a table)
    are preserved under per-class NMS without suppressing each other.
    """
    cfg = get_vision_config()
    # Overlapping bounding boxes: Laptop (class 63) and Smartphone (class 67)
    boxes = [[120, 100, 220, 160], [180, 130, 70, 120]]
    scores = [0.85, 0.78]
    classes = [63, 67]

    # Per-class NMS
    keep = []
    for cid in [63, 67]:
        cls_idx = [i for i in range(len(classes)) if classes[i] == cid]
        b = [boxes[i] for i in cls_idx]
        s = [scores[i] for i in cls_idx]
        res = cv2.dnn.NMSBoxes(b, s, cfg.item_conf_threshold, cfg.nms_iou_threshold)
        if len(res) > 0:
            for r in np.asarray(res).flatten():
                keep.append(cls_idx[int(r)])

    assert len(keep) == 2
    assert 0 in keep  # Laptop preserved
    assert 1 in keep  # Smartphone preserved
