"""Live Camera Computer Vision & Biometric Pipeline Tests"""

import os
import sys
import pytest
import cv2
import numpy as np
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.main import app
from src.ml.vision_service import VisionInferenceService
from src.ml.face_service import FaceRecognitionService


def create_test_frame_with_box():
    """Generates a test image frame with a clear simulated case box."""
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    # Draw a prominent white rectangle (case box)
    cv2.rectangle(img, (150, 120), (350, 320), (255, 255, 255), -1)
    _, encoded = cv2.imencode(".jpg", img)
    return encoded.tobytes()


def test_vision_analyze_frame_real_contours():
    """Confirms real OpenCV contour detection accurately counts cases on a frame."""
    frame_bytes = create_test_frame_with_box()
    v_result, annotated_bytes = VisionInferenceService.analyze_frame_bytes(frame_bytes)

    assert v_result.cases_detected >= 1
    assert v_result.vision_count >= 1
    assert len(annotated_bytes) > 500
    assert v_result.latency_ms > 0


def test_face_detection_on_empty_frame():
    """Confirms face detector runs on frame and returns NO_MATCH without crashing."""
    frame_bytes = create_test_frame_with_box()
    match_res, ann_bytes, boxes = FaceRecognitionService.detect_and_match_faces(
        frame_bytes=frame_bytes,
        enrolled_employees=[],
    )

    assert match_res.decision == "NO_MATCH"
    assert len(boxes) == 0


from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from src.db.session import get_db
from src.db.models import Base
from src.db.init_config import init_baseline_configuration


@pytest.fixture
async def test_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        await init_baseline_configuration(session)
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


@pytest.mark.asyncio
async def test_camera_scan_now_endpoint(client):
    """Tests the /api/cameras/{camera_id}/scan-now endpoint with an isolated test session."""
    created_files = []
    try:
        # 0. Ensure lane exists dynamically
        await client.post("/api/lanes", json={"laneId": "LANE-01", "label": "Exit Lane 01"})

        # 1. Register a camera
        cam_payload = {
            "label": "Test Portal Camera",
            "laneId": "LANE-01",
            "ipAddress": "192.168.1.100",
            "rtspPath": "/video",
        }
        res_reg = await client.post("/api/cameras", json=cam_payload)
        assert res_reg.status_code == 201
        cam_id = res_reg.json()["cameraId"]

        # 2. Write a mock test snapshot into snapshots/
        os.makedirs("snapshots", exist_ok=True)
        preview_file = os.path.join("snapshots", f"preview_{cam_id}.jpg")
        with open(preview_file, "wb") as f:
            f.write(create_test_frame_with_box())
        created_files.append(preview_file)

        # 3. Trigger scan-now
        res_scan = await client.post(f"/api/cameras/{cam_id}/scan-now")
        assert res_scan.status_code == 200
        data = res_scan.json()
        assert data["success"] is True
        assert data["laneId"] == "LANE-01"
        assert "snapshotUrl" in data
        snap_path = data["snapshotUrl"].lstrip("/")
        created_files.append(snap_path)
        assert os.path.exists(snap_path)
    finally:
        for f in created_files:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

