"""Test Suite for Part W: Material Knowledge Base, Counting Tiers & Two-Stage Defect Detection.

Verifies:
1. Formalized Counting Tiers (SINGLE_UNIT, PACKAGED_BOX, BULK_MATERIAL) eliminate unit vs. box ambiguity.
2. Traceable counting arithmetic resolution via REST API.
3. Two-stage defect detection (Stage 1 instance segmentation mask -> Stage 2 surface defect classification).
4. Strict 95% confidence gating (Part N.10.5.1) and honest degradation (Section 2.3) on borderline anomalies.
5. Automated MATERIAL_DEFECT alert creation using existing Alert table with zero new database tables.
"""

import pytest
import numpy as np
import cv2
import base64
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from src.main import app
from src.db.session import get_db
from src.db.models import Base, Material, PackageDefinition, Alert
from src.ml.defect_detection import MaterialDefectService, InstanceDefectResult
from src.ml.material_segmentation import MaterialInstance


@pytest.fixture
async def empty_test_session():
    """Isolated in-memory DB with ZERO seeded operational materials."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture
async def client(empty_test_session):
    async def override_get_db():
        yield empty_test_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def admin_token():
    return "ADMIN"


@pytest.fixture
def sample_torn_cement_bag_frame():
    """Generates a synthetic frame depicting a cement bag with a severe rupture and powder spill."""
    img = np.full((300, 400, 3), 40, dtype=np.uint8)  # Dark floor background
    # Cement bag kraft paper body (brown/tan: BGR 60, 120, 160)
    cv2.rectangle(img, (50, 50), (250, 200), (60, 120, 160), -1)
    # Severe tear rupture with grey-white cement dust plume spilling out (BGR 215, 215, 215)
    cv2.circle(img, (150, 120), 75, (215, 215, 215), -1)
    # Jagged dark tear fissure across sack center
    pts = np.array([[100, 110], [130, 135], [150, 110], [170, 140], [200, 115]], dtype=np.int32)
    cv2.polylines(img, [pts], isClosed=False, color=(20, 20, 20), thickness=5)
    return img


@pytest.fixture
def sample_borderline_torn_bag_frame():
    """Generates a synthetic frame depicting a cement bag with a small ambiguous surface scratch."""
    img = np.full((300, 400, 3), 40, dtype=np.uint8)
    cv2.rectangle(img, (50, 50), (250, 200), (60, 120, 160), -1)
    # Small patch of dust (radius 38, spill ratio ~0.16)
    cv2.circle(img, (150, 120), 38, (215, 215, 215), -1)
    return img


@pytest.fixture
def sample_cracked_tile_frame():
    """Generates a synthetic frame depicting a ceramic tile with sharp penetrating surface cracks."""
    img = np.full((300, 400, 3), 30, dtype=np.uint8)
    # White ceramic tile glazed face (BGR 230, 230, 230)
    cv2.rectangle(img, (80, 60), (280, 240), (230, 230, 230), -1)
    # Multiple penetrating high-contrast crack lines traversing across the interior face
    cv2.line(img, (95, 75), (200, 170), (10, 10, 10), 4)
    cv2.line(img, (200, 170), (265, 220), (10, 10, 10), 4)
    cv2.line(img, (200, 170), (140, 225), (10, 10, 10), 4)
    cv2.line(img, (110, 120), (250, 140), (10, 10, 10), 3)
    cv2.line(img, (130, 80), (160, 210), (10, 10, 10), 3)
    cv2.line(img, (170, 90), (220, 220), (10, 10, 10), 3)
    return img


@pytest.fixture
def sample_intact_box_frame():
    """Generates a synthetic frame depicting an intact master carton without any tears or cracks."""
    img = np.full((300, 400, 3), 40, dtype=np.uint8)
    # Uniform kraft paper master carton (BGR 70, 130, 180)
    cv2.rectangle(img, (70, 70), (270, 230), (70, 130, 180), -1)
    # Straight clean top tape line
    cv2.line(img, (70, 100), (270, 100), (40, 90, 140), 2)
    return img


@pytest.mark.asyncio
async def test_material_counting_tier_onboarding(client: AsyncClient, admin_token: str):
    """Verifies onboarding materials with explicit counting tiers: SINGLE_UNIT, PACKAGED_BOX, BULK_MATERIAL."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Onboard SINGLE_UNIT item
    single_res = await client.post(
        "/api/materials",
        json={
            "name": "Industrial Safety Helmet",
            "skuCode": "PPE-HLM-001",
            "category": "DISCRETE_PACKAGE",
            "deploymentProfile": "RETAIL_EXIT",
            "countUnit": "piece",
            "packagingType": "loose_unit",
            "countingTier": "SINGLE_UNIT",
            "unitsPerPackage": 1,
            "nominalUnitWeightKg": 0.45,
        },
        headers=headers,
    )
    assert single_res.status_code == 201
    single_data = single_res.json()
    assert single_data["countingTier"] == "SINGLE_UNIT"
    assert single_data["unitsPerPackage"] == 1

    # 2. Onboard PACKAGED_BOX item
    box_res = await client.post(
        "/api/materials",
        json={
            "name": "Ceramic Tile Master Carton",
            "skuCode": "TIL-MSTR-024",
            "category": "DISCRETE_PACKAGE",
            "deploymentProfile": "WAREHOUSE_DISPATCH",
            "countUnit": "tile",
            "packagingType": "sealed_case",
            "countingTier": "PACKAGED_BOX",
            "unitsPerPackage": 24,
            "nominalUnitWeightKg": 1.20,
        },
        headers=headers,
    )
    assert box_res.status_code == 201
    box_data = box_res.json()
    assert box_data["countingTier"] == "PACKAGED_BOX"
    assert box_data["unitsPerPackage"] == 24

    # 3. Onboard BULK_MATERIAL item
    bulk_res = await client.post(
        "/api/materials",
        json={
            "name": "Portland Pozzolana Cement 50kg Sack",
            "skuCode": "CEM-PPC-050",
            "category": "STACKED_MATERIAL",
            "deploymentProfile": "WAREHOUSE_DISPATCH",
            "countUnit": "bag",
            "packagingType": "stack",
            "countingTier": "BULK_MATERIAL",
            "unitsPerPackage": 1,
            "nominalUnitWeightKg": 50.0,
            "weightTolerancePct": 3.0,
        },
        headers=headers,
    )
    assert bulk_res.status_code == 201
    bulk_data = bulk_res.json()
    assert bulk_data["countingTier"] == "BULK_MATERIAL"
    assert bulk_data["nominalUnitWeightKg"] == 50.0


@pytest.mark.asyncio
async def test_resolve_tier_count_api(client: AsyncClient, admin_token: str):
    """Verifies the /resolve-tier-count API eliminates box vs unit ambiguity with formula exposure."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Create packaged box material: 12 units per case
    create_res = await client.post(
        "/api/materials",
        json={
            "name": "1000ml Lubricant Oil Case",
            "skuCode": "OIL-CS-012",
            "category": "DISCRETE_PACKAGE",
            "deploymentProfile": "WAREHOUSE_DISPATCH",
            "countUnit": "bottle",
            "packagingType": "sealed_case",
            "countingTier": "PACKAGED_BOX",
            "unitsPerPackage": 12,
            "nominalUnitWeightKg": 0.95,
        },
        headers=headers,
    )
    assert create_res.status_code == 201
    mat_id = create_res.json()["materialId"]

    # Test resolving 8 boxes detected
    resolve_res = await client.post(
        f"/api/materials/{mat_id}/resolve-tier-count",
        json={
            "materialId": mat_id,
            "rawDetectedCount": 8,
        },
        headers=headers,
    )
    assert resolve_res.status_code == 200
    res_data = resolve_res.json()
    assert res_data["countingTier"] == "PACKAGED_BOX"
    assert res_data["resolvedPackagesCount"] == 8
    assert res_data["resolvedTotalUnits"] == 96  # 8 * 12
    assert "8 boxes detected @ 12 units/box = 96 total units" in res_data["arithmeticTrace"]

    # Test resolving bulk material with load cell weight delta
    bulk_mat_res = await client.post(
        "/api/materials",
        json={
            "name": "Deformed Steel Rebar 12mm",
            "skuCode": "STL-RBR-012",
            "category": "STACKED_MATERIAL",
            "deploymentProfile": "WAREHOUSE_DISPATCH",
            "countUnit": "rod",
            "packagingType": "bundle",
            "countingTier": "BULK_MATERIAL",
            "unitsPerPackage": 1,
            "nominalUnitWeightKg": 8.88,
        },
        headers=headers,
    )
    assert bulk_mat_res.status_code == 201
    bulk_id = bulk_mat_res.json()["materialId"]

    # 177.6 kg weight observed -> 177.6 / 8.88 = 20 rods
    resolve_bulk = await client.post(
        f"/api/materials/{bulk_id}/resolve-tier-count",
        json={
            "materialId": bulk_id,
            "rawDetectedCount": 18,  # Slightly occluded vision count
            "observedWeightKg": 177.60,
        },
        headers=headers,
    )
    assert resolve_bulk.status_code == 200
    bulk_out = resolve_bulk.json()
    assert bulk_out["countingTier"] == "BULK_MATERIAL"
    assert bulk_out["resolvedTotalUnits"] == 20  # Derived traceable units from load cell


def test_two_stage_defect_detection_torn_bag(sample_torn_cement_bag_frame):
    """Verifies Stage 2 classifies a ruptured cement sack with >= 95% confidence."""
    # Stage 1 instance
    inst = MaterialInstance(
        class_id="101",
        class_name="Cement Bag (50kg)",
        confidence=0.96,
        bbox=[50, 50, 200, 150],
        polygon=[[50, 50], [250, 50], [250, 200], [50, 200]],
        area_pixels=30000,
    )

    defect_res = MaterialDefectService.classify_instance_defect(
        frame=sample_torn_cement_bag_frame,
        instance=inst,
        min_confidence=0.95,
    )

    assert defect_res.is_defective is True
    assert defect_res.defect_type == "TORN_BAG"
    assert defect_res.defect_confidence >= 0.95
    assert defect_res.defect_severity in ("MEDIUM", "HIGH")
    assert defect_res.honest_degradation is False


def test_two_stage_defect_honest_degradation_borderline(sample_borderline_torn_bag_frame):
    """Verifies borderline anomalies degrade honestly to REVIEW_REQUIRED instead of guessing."""
    inst = MaterialInstance(
        class_id="101",
        class_name="Cement Bag (50kg)",
        confidence=0.96,
        bbox=[50, 50, 200, 150],
        polygon=[[50, 50], [250, 50], [250, 200], [50, 200]],
        area_pixels=30000,
    )

    defect_res = MaterialDefectService.classify_instance_defect(
        frame=sample_borderline_torn_bag_frame,
        instance=inst,
        min_confidence=0.95,
    )

    assert defect_res.is_defective is False  # Suppressed from automatic false alarm
    assert defect_res.honest_degradation is True
    assert "REVIEW_REQUIRED" in defect_res.degradation_reason
    assert defect_res.defect_type == "TORN_BAG"


def test_two_stage_defect_detection_cracked_tile(sample_cracked_tile_frame):
    """Verifies Stage 2 classifies cracked ceramic tiles with >= 95% confidence."""
    inst = MaterialInstance(
        class_id="106",
        class_name="Ceramic Tiles / Tile Box",
        confidence=0.94,
        bbox=[80, 60, 200, 180],
        polygon=[[80, 60], [280, 60], [280, 240], [80, 240]],
        area_pixels=36000,
    )

    defect_res = MaterialDefectService.classify_instance_defect(
        frame=sample_cracked_tile_frame,
        instance=inst,
        min_confidence=0.95,
    )

    assert defect_res.is_defective is True
    assert defect_res.defect_type == "CRACKED_TILE"
    assert defect_res.defect_confidence >= 0.95
    assert defect_res.honest_degradation is False


def test_two_stage_defect_detection_intact_item(sample_intact_box_frame):
    """Verifies intact items are cleanly classified as non-defective."""
    inst = MaterialInstance(
        class_id="104",
        class_name="Heavy Corrugated Master Carton",
        confidence=0.95,
        bbox=[70, 70, 200, 160],
        polygon=[[70, 70], [270, 70], [270, 230], [70, 230]],
        area_pixels=32000,
    )

    defect_res = MaterialDefectService.classify_instance_defect(
        frame=sample_intact_box_frame,
        instance=inst,
        min_confidence=0.95,
    )

    assert defect_res.is_defective is False
    assert defect_res.defect_severity == "NONE"


@pytest.mark.asyncio
async def test_defect_inspect_api_and_automated_alert(
    client: AsyncClient,
    admin_token: str,
    empty_test_session: AsyncSession,
    sample_torn_cement_bag_frame,
):
    """Verifies the POST /api/materials/defect-inspect endpoint raises automated MATERIAL_DEFECT alert."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Encode frame to base64
    _, buf = cv2.imencode(".jpg", sample_torn_cement_bag_frame)
    b64_str = base64.b64encode(buf).decode("utf-8")

    res = await client.post(
        "/api/materials/defect-inspect",
        json={
            "imageBase64": f"data:image/jpeg;base64,{b64_str}",
            "minConfidence": 0.95,
        },
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["totalInstances"] >= 1
    assert data["defectiveInstances"] >= 1
    assert data["alertRaised"] is True
    assert data["alertId"] is not None

    # Check alert was stored in existing Alert table without creating any new table
    alert_stmt = select(Alert).where(Alert.alert_id == data["alertId"])
    alert_row = await empty_test_session.execute(alert_stmt)
    saved_alert = alert_row.scalar_one_or_none()
    assert saved_alert is not None
    assert saved_alert.alert_type == "MATERIAL_DEFECT"
    assert saved_alert.status == "OPEN"
