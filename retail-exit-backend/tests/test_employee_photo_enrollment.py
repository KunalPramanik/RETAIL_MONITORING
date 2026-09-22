"""Test Employee Biometric Photo Enrollment and Known/Unknown Classification"""

import pytest
import io
import cv2
import numpy as np
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from unittest.mock import patch

from src.main import app
from src.db.session import get_db
from src.db.models import Base, Employee
from src.db.seed import seed_database
from src.ml.face_service import FaceRecognitionService


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


def create_test_image_bytes():
    """Generates a dummy JPEG image buffer for HTTP upload testing."""
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    ret, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


@pytest.mark.asyncio
async def test_upload_photo_no_face_detected(client):
    """Uploading an image with no face returns HTTP 422."""
    dummy_bytes = create_test_image_bytes()
    files = {"file": ("test.jpg", dummy_bytes, "image/jpeg")}

    with patch.object(FaceRecognitionService, "extract_face_embedding", return_value=None):
        resp = await client.post("/api/employees/emp_101/photo", files=files)
        assert resp.status_code == 422
        assert "No detectable face found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_and_delete_employee_photo_success(client, test_session):
    """Uploading a photo with a detected face enrolls the 512-d vector."""
    dummy_bytes = create_test_image_bytes()
    files = {"file": ("portrait.jpg", dummy_bytes, "image/jpeg")}
    fake_embedding = [0.05] * 512

    with patch.object(FaceRecognitionService, "extract_face_embedding", return_value=fake_embedding):
        resp = await client.post("/api/employees/emp_101/photo", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["employeeId"] == "emp_101"
        assert data["hasFaceEnrolled"] is True
        assert data["embeddingDimension"] == 512

    # Verify GET /api/employees returns hasFaceEnrolled: True
    list_resp = await client.get("/api/employees")
    assert list_resp.status_code == 200
    emps = list_resp.json()
    emp_101 = next(e for e in emps if e["employeeId"] == "emp_101")
    assert emp_101["hasFaceEnrolled"] is True
    assert emp_101["embeddingUpdatedAt"] is not None

    # Verify DELETE /api/employees/emp_101/photo clears the enrollment
    del_resp = await client.delete("/api/employees/emp_101/photo")
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True

    # Check that hasFaceEnrolled is now False
    list_resp2 = await client.get("/api/employees")
    emp_101_after = next(e for e in list_resp2.json() if e["employeeId"] == "emp_101")
    assert emp_101_after["hasFaceEnrolled"] is False


@pytest.mark.asyncio
async def test_known_vs_unknown_face_matching():
    """Verify FaceRecognitionService correctly separates enrolled known employees from unknown persons."""
    # Create an enrolled employee with vector pointing in direction [1, 0, 0, ...]
    enrolled_vec = [1.0] + [0.0] * 511
    roster = [
        {"employee_id": "emp_sarah", "name": "Sarah Connor", "face_embedding": enrolled_vec}
    ]

    # Probe 1: Same person with high cosine similarity (e.g. 0.95)
    known_probe = [0.95, 0.05] + [0.0] * 510
    res_known = FaceRecognitionService.match_carrier(known_probe, roster)
    assert res_known.decision == "MATCHED"
    assert res_known.matched_employee_id == "emp_sarah"
    assert res_known.employee_name == "Sarah Connor"
    assert res_known.similarity >= 0.65

    # Probe 2: Completely unknown person with orthogonal vector [0, 1, 0, ...]
    unknown_probe = [0.0, 1.0] + [0.0] * 510
    res_unknown = FaceRecognitionService.match_carrier(unknown_probe, roster)
    assert res_unknown.decision in ("NO_MATCH", "LOW_CONFIDENCE")
    assert res_unknown.matched_employee_id is None

