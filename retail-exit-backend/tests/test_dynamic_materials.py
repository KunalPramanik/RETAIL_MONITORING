"""Test Dynamic Material Master, 8-Stage Lifecycle, and Versioned Packaging Definitions.

Complies strictly with Section 5 & Rule 2.1/2.2 of the Master Prompt:
- No hardcoded operational data: starts with zero materials.
- All materials created dynamically through authenticated APIs.
- 8-stage lifecycle: DRAFT -> DATA_COLLECTION -> ANNOTATION -> TRAINING -> EVALUATION -> SHADOW -> APPROVED -> ACTIVE
- Versioned Package Definitions with audit traceability and effective dates.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from src.main import app
from src.db.session import get_db
from src.db.models import Base


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


@pytest.mark.asyncio
async def test_empty_catalog_initially(client):
    """Rule 2.1 & 2.2: The system starts with ZERO hardcoded materials."""
    resp = await client.get("/api/materials")
    assert resp.status_code == 200
    data = resp.json()
    assert data == [], "Operational catalog must start completely empty"


@pytest.mark.asyncio
async def test_dynamic_material_creation(client):
    """Section 5.1: Create new material dynamically via API with full physical attributes."""
    payload = {
        "name": "Portland Pozzolana Cement Grade 53",
        "sku": "SKU-CEM-PPC-53",
        "category": "Raw Construction",
        "deployment_profile": "WAREHOUSE_DISPATCH",
        "count_unit": "bag",
        "packaging_type": "bag",
        "nominal_unit_weight_kg": 50.0,
        "weight_tolerance_pct": 2.0,
        "length_m": 0.6,
        "barcode": "8901234567890",
        "created_by": "qa_engineer",
        "notes": "Standard 50kg bag for warehouse dispatch"
    }

    resp = await client.post("/api/materials", json=payload)
    assert resp.status_code == 201
    created = resp.json()
    assert created["skuCode"] == "SKU-CEM-PPC-53"
    assert created["status"] == "DRAFT"  # Dynamic lifecycle starts at DRAFT
    assert created["nominalUnitWeightKg"] == 50.0
    assert created["weightTolerancePct"] == 2.0

    # Verify retrieval by materialId and by SKU
    mat_id = created["materialId"]
    get_resp = await client.get(f"/api/materials/{mat_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Portland Pozzolana Cement Grade 53"

    sku_resp = await client.get("/api/materials/SKU-CEM-PPC-53")
    assert sku_resp.status_code == 200
    assert sku_resp.json()["materialId"] == mat_id


@pytest.mark.asyncio
async def test_lifecycle_transitions_state_machine(client):
    """Section 5.3: Verify full 8-stage lifecycle progression and state machine validation."""
    # 1. Create in DRAFT
    payload = {
        "name": "TMT High-Yield Rebar Fe500D 12mm",
        "sku": "SKU-REBAR-12MM",
        "deployment_profile": "WAREHOUSE_DISPATCH",
        "count_unit": "rod",
        "packaging_type": "rod",
        "nominal_unit_weight_kg": 10.65,
        "length_m": 12.0,
        "diameter_mm": 12.0,
        "created_by": "materials_lead"
    }
    resp = await client.post("/api/materials", json=payload)
    mat_id = resp.json()["materialId"]

    # 2. Advance through valid sequence:
    # DRAFT -> DATA_COLLECTION -> ANNOTATION -> TRAINING -> EVALUATION -> SHADOW -> APPROVED -> ACTIVE
    valid_stages = [
        "DATA_COLLECTION",
        "ANNOTATION",
        "TRAINING",
        "EVALUATION",
        "SHADOW",
        "APPROVED",
        "ACTIVE",
    ]

    for stage in valid_stages:
        trans_resp = await client.post(
            f"/api/materials/{mat_id}/lifecycle",
            json={
                "target_stage": stage,
                "actor": "lead_ml_engineer",
                "notes": f"Progressing to {stage} after compliance gate"
            }
        )
        assert trans_resp.status_code == 200
        data = trans_resp.json()
        assert data["status"] == stage

    # 3. Disallowed transition test: cannot jump directly from ACTIVE to TRAINING without approval
    invalid_resp = await client.post(
        f"/api/materials/{mat_id}/lifecycle",
        json={"target_stage": "TRAINING", "actor": "rogue_actor"}
    )
    assert invalid_resp.status_code == 400
    assert "Invalid lifecycle transition" in invalid_resp.json()["detail"]


@pytest.mark.asyncio
async def test_versioned_package_definitions(client):
    """Section 5.2: Product and Case Definitions must be versioned with effective timestamps."""
    # 1. Create a base tile material
    mat_resp = await client.post("/api/materials", json={
        "name": "Vitrified Floor Tile 600x600mm",
        "sku": "SKU-TILE-600X600",
        "deployment_profile": "RETAIL_EXIT",
        "count_unit": "tile",
        "packaging_type": "case",
        "nominal_unit_weight_kg": 3.75,
        "created_by": "catalog_admin"
    })
    mat_id = mat_resp.json()["materialId"]

    # 2. Add Revision 1: 4 tiles per sealed carton (15kg gross)
    pkg1_payload = {
        "units_per_package": 4,
        "package_barcode": "012345670001",
        "gross_weight_kg": 15.5,
        "net_weight_kg": 15.0,
        "tolerance_range_pct": 2.0,
        "approval_status": "APPROVED",
        "approved_by": "qa_lead",
        "evidence_source": "Manufacturer Spec Sheet v1.2"
    }
    pkg1_resp = await client.post(f"/api/materials/{mat_id}/package-definitions", json=pkg1_payload)
    assert pkg1_resp.status_code == 201
    pkg1_data = pkg1_resp.json()
    assert pkg1_data["unitsPerPackage"] == 4
    assert pkg1_data["approvalStatus"] == "APPROVED"

    # 3. Add Revision 2: Pack size updated to 6 tiles per carton
    pkg2_payload = {
        "units_per_package": 6,
        "package_barcode": "012345670002",
        "gross_weight_kg": 23.0,
        "net_weight_kg": 22.5,
        "approval_status": "APPROVED",
        "approved_by": "qa_lead",
        "evidence_source": "New Packaging Line 2026"
    }
    pkg2_resp = await client.post(f"/api/materials/{mat_id}/package-definitions", json=pkg2_payload)
    assert pkg2_resp.status_code == 201

    # 4. Fetch material and verify both historical revisions are intact
    full_mat_resp = await client.get(f"/api/materials/{mat_id}")
    defs = full_mat_resp.json()["packageDefinitions"]
    assert len(defs) == 3
    assert defs[0]["unitsPerPackage"] == 1  # Initial baseline
    assert defs[1]["unitsPerPackage"] == 4  # Revision 1
    assert defs[2]["unitsPerPackage"] == 6  # Revision 2


@pytest.mark.asyncio
async def test_material_profile_filtering(client):
    """Section 3 & Section 5.1: Catalog filtering by Deployment Profile (Retail vs Warehouse vs Industrial)."""
    # Create Retail Material
    await client.post("/api/materials", json={
        "name": "Sparkling Water 330ml Can",
        "sku": "SKU-RETAIL-WATER-CAN",
        "deployment_profile": "RETAIL_EXIT",
        "count_unit": "piece",
        "created_by": "retail_mgr"
    })

    # Create Warehouse Material
    await client.post("/api/materials", json={
        "name": "Corrugated Aluminium Sheet 10ft",
        "sku": "SKU-ALUM-SHEET-10FT",
        "deployment_profile": "WAREHOUSE_DISPATCH",
        "count_unit": "sheet",
        "created_by": "wh_mgr"
    })

    # Filter by RETAIL_EXIT
    retail_resp = await client.get("/api/materials?profile=RETAIL_EXIT")
    retail_list = retail_resp.json()
    assert len(retail_list) == 1
    assert retail_list[0]["skuCode"] == "SKU-RETAIL-WATER-CAN"
    assert retail_list[0]["name"] == "Sparkling Water 330ml Can"

    # Filter by WAREHOUSE_DISPATCH
    wh_resp = await client.get("/api/materials?profile=WAREHOUSE_DISPATCH")
    wh_list = wh_resp.json()
    assert len(wh_list) == 1
    assert wh_list[0]["skuCode"] == "SKU-ALUM-SHEET-10FT"
    assert wh_list[0]["name"] == "Corrugated Aluminium Sheet 10ft"
