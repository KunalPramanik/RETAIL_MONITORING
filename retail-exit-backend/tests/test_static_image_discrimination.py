"""Unit & Integration Tests for Static Image Discrimination & Detection Overlay Pipeline"""

import pytest
import numpy as np
import cv2
from typing import Any
from datetime import datetime, timezone
from sqlalchemy import select

from src.ml.static_image_service import StaticImageClassifier, StaticImageClassificationResult
from src.db.models import Camera, StaticImageDetection, Base
from src.db.session import AsyncSessionLocal, init_db
from src.realtime.events import WebSocketEnvelope


@pytest.fixture(autouse=True)
async def setup_test_db():
    await init_db()


def test_classify_religious_image_warm_palette():
    """Religious imagery (e.g. Ganesh, Mahadev wall pictures) has high saturation in saffron/gold/orange."""
    # Synthetic saffron / gold crop with ornate border
    img = np.zeros((120, 120, 3), dtype=np.uint8)
    # Saffron / orange BGR: (30, 130, 240)
    img[:, :] = (20, 140, 245)
    # Add gold ornaments BGR: (20, 215, 255)
    img[20:100, 20:100] = (25, 215, 255)
    # Add contour edges
    cv2.circle(img, (60, 60), 30, (0, 0, 0), 2)

    res = StaticImageClassifier.classify_crop(
        crop=img,
        liveness_score=0.18,
        has_face_geometry=True,
        skin_ratio=0.10,
    )
    assert res.classification == "RELIGIOUS_IMAGE"
    assert res.confidence >= 0.45
    assert "Religious Image" in res.friendly_label
    assert res.suppressed_alert is True


def test_classify_person_photo():
    """Planar photo with realistic human skin tone and portrait boundary is classified as PERSON_PHOTO."""
    img = np.zeros((120, 120, 3), dtype=np.uint8)
    # Human skin tone in BGR ~ (150, 175, 220)
    img[:, :] = (150, 175, 220)
    # Add picture frame edge around border
    cv2.rectangle(img, (2, 2), (118, 118), (40, 40, 40), 4)

    res = StaticImageClassifier.classify_crop(
        crop=img,
        liveness_score=0.15,
        has_face_geometry=True,
        skin_ratio=0.55,
    )
    assert res.classification == "PERSON_PHOTO"
    assert res.confidence >= 0.40
    assert "Person Photo" in res.friendly_label


def test_classify_poster_or_signage():
    """Retail signage with high horizontal text edge density and low skin is classified as POSTER_OR_SIGNAGE."""
    img = np.ones((120, 120, 3), dtype=np.uint8) * 240
    # Add horizontal text bar lines
    for y in range(25, 95, 12):
        cv2.line(img, (15, y), (105, y), (10, 10, 10), 3)

    res = StaticImageClassifier.classify_crop(
        crop=img,
        liveness_score=0.10,
        has_face_geometry=False,
        skin_ratio=0.0,
    )
    assert res.classification in ("POSTER_OR_SIGNAGE", "UNCLASSIFIED_STATIC")
    assert res.suppressed_alert is True


def test_classify_screen_display():
    """Digital monitor display with bezel border and high-frequency Moiré pattern."""
    img = np.zeros((120, 120, 3), dtype=np.uint8)
    # Screen bezel
    cv2.rectangle(img, (2, 2), (118, 118), (15, 15, 15), 6)
    # Fill with alternating high-frequency pattern
    img[8:112:2, 8:112:2] = (220, 220, 220)

    res = StaticImageClassifier.classify_crop(
        crop=img,
        liveness_score=0.22,
        has_face_geometry=False,
        skin_ratio=0.0,
    )
    assert res.classification in ("SCREEN_DISPLAY", "POSTER_OR_SIGNAGE")
    assert res.suppressed_alert is True


def test_classify_unclassified_fallback():
    """Blank or featureless surface falls back to UNCLASSIFIED_STATIC."""
    img = np.ones((100, 100, 3), dtype=np.uint8) * 128
    res = StaticImageClassifier.classify_crop(
        crop=img,
        liveness_score=0.20,
        has_face_geometry=False,
        skin_ratio=0.0,
    )
    assert res.classification == "UNCLASSIFIED_STATIC"


def test_websocket_envelope_detection_update():
    """Verify that detection_update is a valid typed WebSocket envelope."""
    payload = {
        "cameraId": "cam-101",
        "boxes": [
            {
                "box": [10, 20, 80, 100],
                "type": "PERSON_MATCHED",
                "label": "Recognized: J. Alvarez (96%)",
                "confidence": 0.96,
                "color": "green",
            }
        ],
        "entityCount": 1,
    }
    envelope = WebSocketEnvelope(type="detection_update", payload=payload)
    assert envelope.type == "detection_update"
    assert envelope.payload["cameraId"] == "cam-101"
    assert len(envelope.payload["boxes"]) == 1


@pytest.mark.asyncio
async def test_static_image_db_persistence():
    """Verify writing and querying StaticImageDetection in SQLite DB."""
    import uuid
    async with AsyncSessionLocal() as session:
        cam_id = f"cam-test-{uuid.uuid4()}"
        cam = Camera(
            camera_id=cam_id,
            label="Exit Gate 1 — Wall Test",
            ip_address="192.168.1.199",
            rtsp_path="/live",
            status="ONLINE",
        )
        session.add(cam)
        await session.commit()

        detection = StaticImageDetection(
            camera_id=cam_id,
            frame_ts=datetime.now(timezone.utc),
            bbox=[50, 60, 120, 140],
            liveness_score=0.25,
            classification="RELIGIOUS_IMAGE",
            classification_confidence=0.92,
            model_version="static-classifier-v1.0",
            suppressed_alert=True,
        )
        session.add(detection)
        await session.commit()

        res = await session.execute(
            select(StaticImageDetection).where(StaticImageDetection.camera_id == cam_id)
        )
        records = res.scalars().all()
        assert len(records) >= 1
        r: Any = records[0]
        assert str(r.classification) == "RELIGIOUS_IMAGE"
        assert float(r.liveness_score) == 0.25
        assert bool(r.suppressed_alert) is True

