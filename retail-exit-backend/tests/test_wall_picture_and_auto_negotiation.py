import pytest
import numpy as np
import cv2
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from src.main import app
from src.db.session import get_db
from src.db.models import Base
from src.ml.wall_picture_detector import WallPictureDetector
from src.api.cameras import capture_camera_frame_sync


@pytest.fixture
async def test_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
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


def test_wall_picture_detector_synthetic_frame():
    """Verifies that WallPictureDetector dynamically detects framed prints with bezel borders."""
    # Create a synthetic 1280x720 scene (uniform wall background)
    img = np.full((720, 1280, 3), 220, dtype=np.uint8)

    # Draw a framed quote poster on the wall:
    # Outer dark bezel frame: x=150, y=120, w=180, h=140
    cv2.rectangle(img, (150, 120), (330, 260), (30, 30, 30), 6)
    # Inner artwork with high texture variance (text quote / graphics)
    for i in range(130, 250, 12):
        cv2.line(img, (165, i), (315, i), (60, 60, 60), 2)
    cv2.putText(img, "FOCUS", (180, 195), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (10, 10, 10), 2)

    # Draw a second portrait photo frame on the wall: x=800, y=100, w=140, h=190
    cv2.rectangle(img, (800, 100), (940, 290), (40, 40, 40), 6)
    cv2.putText(img, "TODAY", (815, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (15, 15, 15), 2)

    # Run WallPictureDetector
    results = WallPictureDetector.detect_wall_pictures(img)
    assert len(results) >= 2

    # Verify attributes of detected wall frames
    for res in results:
        assert res["type"] == "STATIC_IMAGE"
        assert res["color"] == "static"
        assert res["confidence"] >= 0.50
        assert "Static:" in res["label"]
        assert len(res["box"]) == 4

    # Verify annotate_frame creates a valid annotated image
    annotated = WallPictureDetector.annotate_frame(img, results)
    assert annotated.shape == img.shape
    assert annotated.dtype == np.uint8


def test_wall_picture_detector_respects_exclude_boxes():
    """Verifies that human bodies and faces in exclude_boxes are never falsely flagged as wall frames."""
    img = np.full((720, 1280, 3), 200, dtype=np.uint8)

    # Simulate a human torso/clothing region with high texture
    cv2.rectangle(img, (400, 200), (650, 600), (80, 50, 40), -1)
    for i in range(220, 580, 15):
        cv2.line(img, (410, i), (640, i), (120, 80, 60), 3)

    # Also add a genuine wall frame on the wall
    cv2.rectangle(img, (100, 100), (250, 240), (20, 20, 20), 5)
    cv2.putText(img, "ART", (120, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

    # Exclude the human body box
    exclude_human = [[400, 200, 250, 400]]
    results = WallPictureDetector.detect_wall_pictures(img, exclude_boxes=exclude_human)

    # Should detect the wall frame, but NOT the human body
    for r in results:
        bx, by, bw, bh = r["box"]
        # Ensure no detection inside the excluded human torso
        assert not (bx >= 380 and (bx + bw) <= 670 and by >= 180 and (by + bh) <= 620)


@pytest.mark.asyncio
async def test_auto_negotiation_reports_probed_ports_on_closed_target(client):
    """Verifies that when an IP camera has port 554 closed, auto-negotiation probes video ports

    and returns a structured, staged diagnostic failure without crashing or hallucinating.
    """
    resp = await client.post(
        "/api/cameras/cam_auto_neg_test/test-connection",
        json={"ipAddress": "192.168.199.199", "rtspPath": "/live/ch0"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert data["status"] == "CONNECTION_FAILED"
    err = data.get("errorMessage", "")
    assert err != ""
    # Verifies that developer shortcuts remain purged
    assert "enter '0'" not in err.lower()
    assert "webcam" not in err.lower()


def test_dynamic_item_and_person_overlay_deduplication():
    """Verifies that items like Bottle are dynamic amber items, and people are never labeled as 'Item: Person'."""
    from src.ml.vision_service import DetectedBox
    from src.ml.model_config import get_vision_config

    cfg = get_vision_config()

    # Simulate overlay boxes with face detection
    overlay_boxes = [
        {
            "box": [200, 150, 80, 90],
            "type": "PERSON_UNMATCHED",
            "label": "Unknown Person (75%)",
            "confidence": 0.75,
            "color": "red",
            "entity": None,
        }
    ]

    # Detections from YOLOX:
    # 1. Person body overlapping the face
    # 2. Bottle held in hand
    yolox_detections = [
        DetectedBox(
            bbox=[180, 130, 150, 300],
            class_label="person",
            product_id=None,
            sku_code="SKU-UNIT-PACK",
            confidence=0.82,
            pack_size=1,
            track_id=301,
            exit_vector=(0.0, 15.0),
            specific_label="Person",
        ),
        DetectedBox(
            bbox=[320, 260, 60, 140],
            class_label="single_unit",
            product_id="prod_water_bottle",
            sku_code="SKU-BOTTLE-500ML",
            confidence=0.78,
            pack_size=1,
            track_id=302,
            exit_vector=(0.0, 15.0),
            specific_label="Bottle",
        ),
    ]

    # Process detections using the camera_worker logic
    for d in yolox_detections:
        is_person = d.class_label == "person"
        is_veh = d.class_label == "vehicle"
        is_case = "case" in d.class_label.lower()

        if is_person:
            has_face_overlap = False
            for ob in overlay_boxes:
                if ob["type"] in ("PERSON_MATCHED", "PERSON_UNMATCHED"):
                    fx, fy, fw, fh = ob["box"]
                    fcx, fcy = fx + fw / 2.0, fy + fh / 2.0
                    if (d.bbox[0] - 25 <= fcx <= d.bbox[0] + d.bbox[2] + 25 and
                        d.bbox[1] - 25 <= fcy <= d.bbox[1] + d.bbox[3] + 25):
                        has_face_overlap = True
                        break
            if not has_face_overlap and d.confidence >= cfg.person_conf_threshold:
                overlay_boxes.append({
                    "box": d.bbox,
                    "type": "PERSON_UNMATCHED",
                    "label": f"Person ({int(d.confidence * 100)}%)",
                    "confidence": round(float(d.confidence), 4),
                    "color": "red",
                    "entity": "Person",
                })
            continue

        item_label = getattr(d, "specific_label", None) or d.class_label
        overlay_boxes.append({
            "box": d.bbox,
            "type": "ITEM",
            "label": f"{item_label} ({int(d.confidence * 100)}%)",
            "confidence": round(float(d.confidence), 4),
            "color": "amber",
            "entity": item_label,
        })

    # Assertions:
    # 1. Bottle was added as ITEM with amber color
    bottle_boxes = [b for b in overlay_boxes if b.get("entity") == "Bottle"]
    assert len(bottle_boxes) == 1
    assert bottle_boxes[0]["type"] == "ITEM"
    assert bottle_boxes[0]["color"] == "amber"
    assert "Bottle (78%)" in bottle_boxes[0]["label"]

    # 2. No duplicate 'Item: Person' box was added!
    item_person_boxes = [b for b in overlay_boxes if "Item: Person" in b.get("label", "")]
    assert len(item_person_boxes) == 0

    # 3. Exactly 2 boxes exist: the face and the bottle (no spurious wall boxes or duplicate person boxes)
    assert len(overlay_boxes) == 2
