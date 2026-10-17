import pytest
import numpy as np
import cv2
import base64
from httpx import AsyncClient
from src.ml.dense_bookshelf_counter import DenseBookshelfCounter
from src.security import create_access_token
from tests.conftest import TestingSessionLocal
from src.db.models import AppUser, get_utc_now
from src.security import get_password_hash


def create_test_shelf_image() -> np.ndarray:
    """Creates a synthetic shelf image with 10 distinct vertical books."""
    img = np.full((300, 600, 3), 220, dtype=np.uint8)
    # Shelf frame
    cv2.rectangle(img, (50, 40), (550, 260), (70, 70, 70), -1)
    cv2.rectangle(img, (60, 50), (540, 250), (140, 140, 140), -1)

    colors = [
        (40, 40, 200), (200, 40, 40), (40, 180, 40), (20, 180, 200),
        (180, 40, 180), (30, 90, 220), (220, 120, 30), (80, 40, 160),
        (50, 150, 200), (160, 180, 30),
    ]
    # Draw 10 vertical books
    x = 80
    for col in colors:
        cv2.rectangle(img, (x, 70), (x + 35, 240), col, -1)
        cv2.rectangle(img, (x, 70), (x + 35, 240), (20, 20, 20), 2)
        x += 42
    return img


@pytest.mark.asyncio
async def test_dense_bookshelf_counter_synthetic():
    frame = create_test_shelf_image()
    res = DenseBookshelfCounter.detect_and_count_books(frame)
    assert res["total_books"] >= 8, f"Expected at least 8 segmented books, got {res['total_books']}"


@pytest.mark.asyncio
async def test_scan_and_count_endpoint(async_client: AsyncClient):
    # Ensure supervisor user exists in db
    async with TestingSessionLocal() as session:
        user = AppUser(
            user_id="user_test_supervisor",
            email="supervisor@secops.io",
            username="supervisor",
            role="SUPERVISOR",
            password_hash=get_password_hash("Supervisor@123"),
            is_active=True,
            created_at=get_utc_now(),
        )
        session.add(user)
        await session.commit()

    token = create_access_token({"sub": "user_test_supervisor", "role": "SUPERVISOR"})
    headers = {"Authorization": f"Bearer {token}"}

    frame = create_test_shelf_image()
    _, buf = cv2.imencode(".jpg", frame)
    b64_str = base64.b64encode(buf).decode("utf-8")

    res = await async_client.post(
        "/api/inventory/scan-and-count",
        json={
            "cameraId": "CAM-01",
            "imageBase64": b64_str,
            "minConfidence": 0.20,
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "SUCCESS"
    assert len(data["scannedMaterials"]) > 0
    assert data["totalDetectedUnits"] > 0
