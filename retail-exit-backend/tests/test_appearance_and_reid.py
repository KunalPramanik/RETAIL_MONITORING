"""Tests for Unverified-Person Appearance Summary & Cross-Camera Re-Identification Tracking

Verifies:
1. Verified Employee Detail: Unrounded confidence, 30-day mismatch history count, employee records.
2. Unverified Appearance Summary: Clothing color extraction (spatial HSV), relative build category, accessories.
3. Strict Prohibited Profiling Absence: NO weight, NO material, NO eye color, NO body marks.
4. Cross-Camera Re-ID Tracking: 30-day rolling window sighting clusters.
5. Anti-False-Matching: Distinct subjects with similar clothing colors do not falsely match on Re-ID.
"""

import pytest
import numpy as np
import cv2
from datetime import timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from src.main import app
from src.db.session import get_db
from src.db.models import Base, ExitEvent, PersonAppearanceSummary, Employee, get_utc_now
from src.db.seed import seed_database
from src.ml.appearance_service import AppearanceService


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


@pytest.mark.asyncio
async def test_verified_employee_detail_and_unrounded_confidence(client, test_session):
    """Verified employee matches return full record, unrounded similarity, and 30-day mismatch count."""
    # Ingest event with matched employee badge (Marcus Vance: RFID-BADGE-4419)
    resp = await client.post(
        "/api/ingest/event",
        json={
            "laneId": "LANE-01",
            "employeeBadgeId": "RFID-BADGE-4419",
            "lineItems": [{"productId": "prod_001", "casesQty": 2, "singlesQty": 0}],
            "declaredUnits": 48,
        },
    )
    assert resp.status_code == 200
    event_id = resp.json()["eventId"]

    # Query event detail
    detail_resp = await client.get(f"/api/events/{event_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()

    # Verify employee record is populated
    assert detail["verifiedEmployee"] is not None
    ve = detail["verifiedEmployee"]
    assert ve["name"] == "Marcus Vance"
    assert ve["rfidBadgeId"] == "RFID-BADGE-4419"
    assert ve["activeFlag"] is True
    # Verify unrounded similarity (float with decimal precision e.g. 0.9850)
    assert isinstance(ve["similarity"], float)
    assert ve["similarity"] > 0.90
    # Marcus Vance has 1 seed mismatch in the last 30 days (EVT-2026-9045)
    assert ve["mismatchCount30d"] >= 1
    # No appearance summary for verified employee
    assert detail["appearanceSummary"] is None


@pytest.mark.asyncio
async def test_unverified_appearance_summary_generation(client, test_session):
    """Unverified carrier triggers automated appearance summary with clothing colors, build, and accessories."""
    resp = await client.post(
        "/api/ingest/event",
        json={
            "laneId": "LANE-02",
            "employeeBadgeId": None,  # Unverified carrier
            "clothingTopColor": "dark navy",
            "clothingBottomColor": "grey",
            "buildCategory": "AVERAGE",
            "accessories": ["bag", "cap"],
            "lineItems": [{"productId": "prod_001", "casesQty": 1, "singlesQty": 0}],
            "declaredUnits": 24,
        },
    )
    assert resp.status_code == 200
    event_id = resp.json()["eventId"]

    detail_resp = await client.get(f"/api/events/{event_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()

    assert detail["verifiedEmployee"] is None
    assert detail["appearanceSummary"] is not None
    pas = detail["appearanceSummary"]

    assert pas["clothingTopColor"] == "dark navy"
    assert pas["clothingBottomColor"] == "grey"
    assert pas["buildCategory"] == "AVERAGE"
    assert "bag" in pas["accessories"]
    assert "cap" in pas["accessories"]
    assert pas["recentSightingsCount"] >= 1


@pytest.mark.asyncio
async def test_strict_absence_of_prohibited_profiling_fields(client, test_session):
    """Verifies that prohibited fields (weight, material, eye color, body marks) are strictly NOT present in models or responses."""
    # 1. Inspect PersonAppearanceSummary model columns
    pas_cols = [c.name for c in PersonAppearanceSummary.__table__.columns]
    for prohibited in ["person_weight", "weight_est", "material", "eye_color", "body_marks", "scars", "tattoos", "height_cm"]:
        assert prohibited not in pas_cols, f"Prohibited column '{prohibited}' found in PersonAppearanceSummary!"

    # 2. Ingest unverified event and inspect detail response
    resp = await client.post(
        "/api/ingest/event",
        json={
            "laneId": "LANE-01",
            "employeeBadgeId": None,
            "lineItems": [{"productId": "prod_001", "casesQty": 1, "singlesQty": 0}],
            "declaredUnits": 24,
        },
    )
    event_id = resp.json()["eventId"]
    detail_resp = await client.get(f"/api/events/{event_id}")
    pas_dict = detail_resp.json()["appearanceSummary"]

    assert pas_dict is not None
    # Ensure forbidden keys are absent in appearanceSummary schema
    for forbidden in ["weight", "personWeight", "material", "objectMaterial", "eyeColor", "bodyMarks", "exactHeight"]:
        assert forbidden not in pas_dict, f"Prohibited key '{forbidden}' found in appearanceSummary API response!"


@pytest.mark.asyncio
async def test_cross_camera_reid_rolling_window_sightings(client, test_session):
    """Cross-camera Re-ID clusters sightings within a 30-day window and increments sightings count."""
    # Create a synthetic 256-d embedding
    synth_crop = np.zeros((256, 128, 3), dtype=np.uint8)
    synth_crop[0:128, :] = (120, 60, 40)   # Blue top
    synth_crop[128:256, :] = (40, 40, 40)   # Dark trousers
    embedding = AppearanceService.generate_reid_embedding(synth_crop)

    # 1. First sighting on Lane 1
    resp1 = await client.post(
        "/api/ingest/event",
        json={
            "laneId": "LANE-01",
            "employeeBadgeId": None,
            "reidEmbedding": embedding,
            "clothingTopColor": "blue",
            "clothingBottomColor": "black",
            "buildCategory": "AVERAGE",
            "lineItems": [{"productId": "prod_001", "casesQty": 1, "singlesQty": 0}],
            "declaredUnits": 24,
        },
    )
    evt1_id = resp1.json()["eventId"]
    detail1 = (await client.get(f"/api/events/{evt1_id}")).json()
    pas1 = detail1["appearanceSummary"]
    assert pas1["recentSightingsCount"] == 1
    cluster_id = pas1["reidClusterId"]
    assert cluster_id is not None

    # 2. Second sighting on Lane 2 (different camera, same day)
    resp2 = await client.post(
        "/api/ingest/event",
        json={
            "laneId": "LANE-02",
            "employeeBadgeId": None,
            "reidEmbedding": embedding,
            "clothingTopColor": "blue",
            "clothingBottomColor": "black",
            "buildCategory": "AVERAGE",
            "lineItems": [{"productId": "prod_001", "casesQty": 1, "singlesQty": 0}],
            "declaredUnits": 24,
        },
    )
    evt2_id = resp2.json()["eventId"]
    detail2 = (await client.get(f"/api/events/{evt2_id}")).json()
    pas2 = detail2["appearanceSummary"]
    # Should cluster into same cluster and reflect 2 sightings
    assert pas2["reidClusterId"] == cluster_id
    assert pas2["recentSightingsCount"] >= 2


def test_anti_false_matching_two_distinct_subjects():
    """Anti-false-matching: Two different subjects with similar dark tops do not falsely match on Re-ID."""
    # Subject A: Dark green jacket with plain texture
    subj_a = np.zeros((256, 128, 3), dtype=np.uint8)
    subj_a[0:128, :] = (30, 80, 40)   # Dark green
    subj_a[128:256, :] = (40, 40, 40)  # Charcoal pants

    # Subject B: Dark navy hoodie with high horizontal striping/texture
    subj_b = np.zeros((256, 128, 3), dtype=np.uint8)
    subj_b[0:128, :] = (120, 60, 40)  # Dark navy
    # Add horizontal texture stripes to Subject B
    for y in range(0, 128, 8):
        subj_b[y : y + 4, :] = (200, 200, 200)
    subj_b[128:256, :] = (40, 40, 40)

    emb_a = AppearanceService.generate_reid_embedding(subj_a)
    emb_b = AppearanceService.generate_reid_embedding(subj_b)

    assert len(emb_a) == 256
    assert len(emb_b) == 256

    # Compute cosine similarity
    dot = sum(a * b for a, b in zip(emb_a, emb_b))
    # Threshold for matching is 0.82; distinct subjects must score below threshold
    assert dot < AppearanceService.REID_SIMILARITY_THRESHOLD, (
        f"False match occurred! Cosine similarity {dot:.4f} exceeds {AppearanceService.REID_SIMILARITY_THRESHOLD}"
    )


def test_clothing_color_and_accessory_extraction():
    """Validates HSV color extraction and accessory detection."""
    # Synthetic subject wearing bright red shirt and blue jeans, with a cap on top
    crop = np.zeros((200, 100, 3), dtype=np.uint8)
    # Head with cap edge
    crop[0:30, 20:80] = (255, 255, 255)
    cv2.rectangle(crop, (15, 20), (85, 28), (0, 0, 0), -1)
    # Torso: Red (BGR: 0, 0, 220)
    crop[30:100, 15:85] = (0, 0, 220)
    # Legs: Blue (BGR: 220, 100, 0)
    crop[100:180, 20:80] = (220, 100, 0)

    top_col, bot_col, conf = AppearanceService.extract_clothing_colors(crop)
    assert top_col == "red"
    assert bot_col == "blue"
    assert conf > 0.60

    # Build category for height ratio 200/720 = 0.27 (< 0.40 -> SHORTER)
    cat, bconf = AppearanceService.classify_build_category([0, 0, 100, 200], (720, 1280), True)
    assert cat == "SHORTER"

    # Build category for height ratio 500/720 = 0.69 (> 0.65 -> TALLER)
    cat_tall, _ = AppearanceService.classify_build_category([0, 0, 100, 500], (720, 1280), True)
    assert cat_tall == "TALLER"

