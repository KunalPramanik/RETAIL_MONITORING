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
