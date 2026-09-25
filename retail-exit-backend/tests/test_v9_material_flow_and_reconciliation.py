"""Master Prompt V9 Comprehensive Test Suite:
Advanced Real-Time Material Flow + Dynamic Inventory Ledger + Person-Wise In/Out Counting
+ Defect Inspection & Quarantine + Multi-Instance Bookshelf File Counting + Atomic Reconciliation.

Verifies all core requirements of Master Prompt V9:
1. Exact per-instance counting and direction flow (IN vs OUT).
2. Dynamic packaging tier conversion (e.g. 5 cases * 24 units = 120 units).
3. Person-material attribution (verified employee vs UNKNOWN_PERSON).
4. Person-wise net movement balance calculation (IN - OUT).
5. Invariant reconciliation: Opening + Incoming - Outgoing + Adjustments == Current Stock.
6. Evidence-based defect quarantine with stock condition partitioning.
7. Anti-duplicate gate crossing lock and reversal handling.
8. Carried material auto-ledger generation upon tripwire line crossing.
9. Dense bookshelf file counting: exact per-instance visible file counting with rejection
   of wall pictures, horizontal shelf planks, and empty shadows.
10. Complete REST API endpoints (/api/materials/... and /api/v1/materials/...).
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
from src.db.models import (
    Base,
    Material,
    PackageDefinition,
    Employee,
    Camera,
    Lane,
    Store,
    VirtualTripwireConfig,
    TripwireCrossingEvent,
    MaterialMovementLedger,
    MaterialInventoryBalance,
    MaterialDefectEvent,
    Alert,
    get_utc_now,
)
from src.engine.inventory_ledger_engine import InventoryLedgerEngine
from src.engine.tripwire_engine import TripwireEngine
from src.ml.dense_shelf_counting import DenseShelfCountingService, DenseShelfCountResult


@pytest.fixture
async def v9_session():
    """Isolated in-memory test database."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture
async def v9_client(v9_session):
    async def override_get_db():
        yield v9_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def seeded_catalog(v9_session: AsyncSession):
    """Seeds baseline catalog with construction, beverage, and document materials."""
    store = Store(store_id="STR-01", name="Central Facility")
    lane = Lane(lane_id="GATE-01", label="Main Dispatch Bay", store_id="STR-01")
    cam = Camera(
        camera_id="CAM-GATE-01",
        lane_id="GATE-01",
        label="Gate 1 Overhead",
        ip_address="192.168.1.101",
        rtsp_path="/live/gate1",
    )
    tw = VirtualTripwireConfig(
        tripwire_id="TW-GATE-01",
        camera_id="CAM-GATE-01",
        label="Perimeter Gate 1 Tripwire",
        line_coords=[[0.1, 0.5], [0.9, 0.5]],
        direction_mode="BOTH",
    )
    emp = Employee(
        employee_id="EMP-101",
        name="Vikram Singh",
        role="LOGISTICS_OPERATOR",
        rfid_badge_id="RFID-EMP-101",
        active_flag=True,
    )
    mat_cement = Material(
        material_id="MAT-CEM-50",
        sku_code="SKU-CEM-50KG",
        name="UltraTech PPC Cement 50kg Bag",
        category="Raw Construction",
        deployment_profile="WAREHOUSE_DISPATCH",
        count_unit="bag",
        packaging_type="bag",
        counting_tier="SINGLE_UNIT",
        units_per_package=1,
        status="ACTIVE",
    )
    mat_water = Material(
        material_id="MAT-WATER-24",
        sku_code="SKU-WATER-CASE24",
        name="Kinley Mineral Water 1L Case",
        category="Beverage",
        deployment_profile="RETAIL_EXIT",
        count_unit="bottle",
        packaging_type="case",
        counting_tier="PACKAGED_BOX",
        units_per_package=24,
        status="ACTIVE",
    )
    pkg_water = PackageDefinition(
        definition_id="PKG-WATER-24",
        material_id="MAT-WATER-24",
        units_per_package=24,
        package_barcode="BAR-WATER-CASE24",
        approval_status="APPROVED",
    )

    v9_session.add_all([store, lane, cam, tw, emp, mat_cement, mat_water, pkg_water])
    await v9_session.commit()
    return {
        "store": store,
        "lane": lane,
        "cam": cam,
        "tw": tw,
        "emp": emp,
        "cement": mat_cement,
        "water": mat_water,
    }


# ==============================================================================
# TEST 1: Material Arrival (IN / ENTRY) Recording & Stock Increment
# ==============================================================================
@pytest.mark.asyncio
async def test_material_arrival_in_recording(v9_session: AsyncSession, seeded_catalog):
    """Verifies that confirmed incoming material records an immutable ledger entry and increments stock."""
    mat = seeded_catalog["cement"]
    cam = seeded_catalog["cam"]

    ledger_entry, balance, alert = await InventoryLedgerEngine.record_confirmed_movement(
        session=v9_session,
        material_id=mat.material_id,
        transaction_type="IN",
        unit_quantity=40,
        camera_id=cam.camera_id,
        direction="ENTRY",
        person_name="UNKNOWN_PERSON",
        person_identity_status="UNKNOWN_PERSON",
    )

    assert ledger_entry.ledger_id.startswith("mvl_")
    assert ledger_entry.transaction_type == "IN"
    assert ledger_entry.unit_quantity == 40
    assert ledger_entry.direction == "ENTRY"

    # Verify balance
    assert balance.opening_stock == 0
    assert balance.incoming_confirmed == 40
    assert balance.outgoing_confirmed == 0
    assert balance.current_stock == 40
    assert alert is None


# ==============================================================================
# TEST 2: Material Departure (OUT / EXIT) Recording & Invariant Verification
# ==============================================================================
@pytest.mark.asyncio
async def test_material_departure_out_recording(v9_session: AsyncSession, seeded_catalog):
    """Verifies outgoing material decrements stock and preserves the accounting invariant:
    Opening + Incoming - Outgoing + Adjustments == Current Stock.
    """
    mat = seeded_catalog["cement"]

    # First receive 50 units
    await InventoryLedgerEngine.record_confirmed_movement(
        session=v9_session,
        material_id=mat.material_id,
        transaction_type="IN",
        unit_quantity=50,
        direction="ENTRY",
    )

    # Then dispatch 18 units
    ledger_out, balance_out, _ = await InventoryLedgerEngine.record_confirmed_movement(
        session=v9_session,
        material_id=mat.material_id,
        transaction_type="OUT",
        unit_quantity=18,
        direction="EXIT",
    )

    assert ledger_out.transaction_type == "OUT"
    assert ledger_out.unit_quantity == 18
    assert balance_out.incoming_confirmed == 50
    assert balance_out.outgoing_confirmed == 18
    assert balance_out.current_stock == 32

    # Accounting invariant verification
    expected = balance_out.opening_stock + balance_out.incoming_confirmed - balance_out.outgoing_confirmed + balance_out.adjusted_stock
    assert balance_out.current_stock == expected


# ==============================================================================
# TEST 3: Dynamic Packaging Tier Conversion (Case -> Units)
# ==============================================================================
@pytest.mark.asyncio
async def test_packaging_tier_case_conversion(v9_session: AsyncSession, seeded_catalog):
    """Verifies packaging tier conversion: 5 cases * 24 bottles = 120 units."""
    water = seeded_catalog["water"]

    ledger, balance, _ = await InventoryLedgerEngine.record_confirmed_movement(
        session=v9_session,
        material_id=water.material_id,
        transaction_type="IN",
        package_quantity=5,  # 5 cases
        # units_per_package omitted to test dynamic resolution from PackageDefinition
    )

    assert ledger.units_per_package == 24
    assert ledger.package_quantity == 5
    assert ledger.unit_quantity == 120
    assert balance.current_stock == 120


# ==============================================================================
# TEST 4: Partial and Mixed Packaging (e.g. 1 Case + 7 Singles)
# ==============================================================================
@pytest.mark.asyncio
async def test_partial_and_mixed_packaging(v9_session: AsyncSession, seeded_catalog):
    """Verifies exact base unit quantities can be recorded directly for partial packages."""
    water = seeded_catalog["water"]

    # Move 31 units (1 case + 7 singles)
    ledger, balance, _ = await InventoryLedgerEngine.record_confirmed_movement(
        session=v9_session,
        material_id=water.material_id,
        transaction_type="IN",
        unit_quantity=31,
        package_quantity=1,
    )

    assert ledger.unit_quantity == 31
    assert balance.current_stock == 31


# ==============================================================================
# TEST 5: Person Attribution — Known Verified Employee
# ==============================================================================
@pytest.mark.asyncio
async def test_person_attribution_known_employee(v9_session: AsyncSession, seeded_catalog):
    """Verifies carrier attribution when the person is a verified employee from the database."""
    mat = seeded_catalog["cement"]
    emp = seeded_catalog["emp"]

    ledger, _, _ = await InventoryLedgerEngine.record_confirmed_movement(
        session=v9_session,
        material_id=mat.material_id,
        transaction_type="IN",
        unit_quantity=25,
        person_id=emp.employee_id,
        carrier_relation="carrying",
    )

    assert ledger.person_id == emp.employee_id
    assert ledger.person_name == "Vikram Singh"
    assert ledger.person_identity_status == "VERIFIED_KNOWN"
    assert ledger.carrier_relation == "carrying"


# ==============================================================================
# TEST 6: Person Attribution — Unknown Person (Zero Hallucination)
# ==============================================================================
@pytest.mark.asyncio
async def test_person_attribution_unknown_person(v9_session: AsyncSession, seeded_catalog):
    """Verifies carrier attribution when identity is unknown: strictly preserved as UNKNOWN_PERSON."""
    mat = seeded_catalog["cement"]

    ledger, _, _ = await InventoryLedgerEngine.record_confirmed_movement(
        session=v9_session,
        material_id=mat.material_id,
        transaction_type="OUT",
        unit_quantity=5,
        person_id=None,
        person_name=None,
    )

    assert ledger.person_id is None
    assert ledger.person_name == "UNKNOWN_PERSON"
    assert ledger.person_identity_status == "UNKNOWN_PERSON"


# ==============================================================================
# TEST 7: Person-Wise In/Out Movement Balance (Net = IN - OUT)
# ==============================================================================
@pytest.mark.asyncio
async def test_person_wise_net_movement_balance(v9_session: AsyncSession, seeded_catalog):
    """Verifies authoritative person-wise calculation: Total In - Total Out = Net Balance."""
    mat = seeded_catalog["cement"]
    emp = seeded_catalog["emp"]

    # Vikram brings in 45 bags
    await InventoryLedgerEngine.record_confirmed_movement(
        session=v9_session,
        material_id=mat.material_id,
        transaction_type="IN",
        unit_quantity=45,
        person_id=emp.employee_id,
    )

    # Vikram takes out 15 bags
    await InventoryLedgerEngine.record_confirmed_movement(
        session=v9_session,
        material_id=mat.material_id,
        transaction_type="OUT",
        unit_quantity=15,
        person_id=emp.employee_id,
    )

    summary = await InventoryLedgerEngine.get_person_movement_summary(
        session=v9_session,
        person_id_or_name=emp.employee_id,
    )

    assert summary["personName"] == "Vikram Singh"
    assert summary["totalBroughtIn"] == 45
    assert summary["totalTakenOut"] == 15
    assert summary["netMovementBalance"] == 30  # 45 - 15 = 30
    assert summary["transactionsCount"] == 2


# ==============================================================================
# TEST 8: Evidence-Based Defect Inspection & Stock Quarantine
# ==============================================================================
@pytest.mark.asyncio
async def test_evidence_based_defect_quarantine(v9_session: AsyncSession, seeded_catalog):
    """Verifies that torn/damaged material increments defective_stock and raises a MATERIAL_DEFECT alert."""
    mat = seeded_catalog["cement"]

    ledger, balance, alert = await InventoryLedgerEngine.record_confirmed_movement(
        session=v9_session,
        material_id=mat.material_id,
        transaction_type="IN",
        unit_quantity=6,
        defect_status="DAMAGED",
        defect_severity="HIGH",
    )

    assert ledger.defect_status == "DAMAGED"
    assert ledger.defect_severity == "HIGH"
    assert balance.incoming_confirmed == 6
    assert balance.defective_stock == 6
    assert alert is not None
    assert alert.alert_type == "MATERIAL_DEFECT"
    assert alert.severity == "HIGH"

    # Verify defect event persisted
    stmt = select(MaterialDefectEvent).where(MaterialDefectEvent.ledger_id == ledger.ledger_id)
    res = await v9_session.execute(stmt)
    def_evt = res.scalar_one_or_none()
    assert def_evt is not None
    assert def_evt.affected_units == 6


# ==============================================================================
# TEST 9: Inventory Discrepancy Auditing & Auto-Reconciliation
# ==============================================================================
@pytest.mark.asyncio
async def test_inventory_discrepancy_and_auto_reconciliation(v9_session: AsyncSession, seeded_catalog):
    """Verifies that physical audits detect shortages/surpluses and can auto-adjust stock."""
    mat = seeded_catalog["cement"]

    # Ingest 50 units
    await InventoryLedgerEngine.record_confirmed_movement(
        session=v9_session,
        material_id=mat.material_id,
        transaction_type="IN",
        unit_quantity=50,
    )

    # Physical count shows only 47 units (3 units missing)
    audit = await InventoryLedgerEngine.reconcile_inventory(
        session=v9_session,
        physical_counts={mat.sku_code: 47},
        auto_adjust=True,
    )

    assert audit["matchesCount"] == 0
    assert audit["discrepanciesCount"] == 1
    assert audit["totalDiscrepancyMagnitude"] == 3
    assert audit["discrepancies"][0]["status"] == "SHORTAGE"
    assert audit["discrepancies"][0]["discrepancyDelta"] == -3

    # Check updated balance after auto-adjust
    balances = await InventoryLedgerEngine.get_inventory_balance(
        session=v9_session,
        material_id=mat.material_id,
    )
    b0 = balances[0]
    assert b0["currentStock"] == 47
    assert b0["adjustedStock"] == -3
    assert b0["accountingInvariantValid"] is True


# ==============================================================================
# TEST 10: Anti-Duplicate Gate Crossing Protection
# ==============================================================================
def test_anti_duplicate_tripwire_crossing_lock():
    """Verifies that rapid successive hits for the same track in the same direction are suppressed as duplicates."""
    tw_id = "TW-TEST-01"
    trk_id = "trk_shopper_88"

    TripwireEngine._crossing_locks.clear()

    # 1. First crossing: allowed
    allowed_1 = TripwireEngine.should_allow_crossing(tw_id, trk_id, "ENTRY")
    assert allowed_1 is True

    # 2. Immediate second hit (within cooldown window) in same direction: suppressed!
    allowed_2 = TripwireEngine.should_allow_crossing(tw_id, trk_id, "ENTRY")
    assert allowed_2 is False

    # 3. Legitimate direction reversal: allowed!
    allowed_rev = TripwireEngine.should_allow_crossing(tw_id, trk_id, "EXIT")
    assert allowed_rev is True


# ==============================================================================
# TEST 11: Tripwire Carried Material Auto-Ledger Integration
# ==============================================================================
@pytest.mark.asyncio
async def test_tripwire_carried_material_auto_ledger(v9_session: AsyncSession, seeded_catalog):
    """Verifies that a person crossing a virtual tripwire while carrying materials automatically updates the inventory ledger."""
    tw = seeded_catalog["tw"]
    cam = seeded_catalog["cam"]
    mat = seeded_catalog["cement"]
    emp = seeded_catalog["emp"]

    crossing, alert = await TripwireEngine.record_crossing(
        session=v9_session,
        tripwire_id=tw.tripwire_id,
        camera_id=cam.camera_id,
        track_id="tr_carried_1",
        direction="ENTRY",
        entity_type="PERSON",
        matched_employee={"decision": "MATCHED", "employee_id": emp.employee_id, "employee_name": emp.name},
        carried_materials=[
            {"material_id": mat.material_id, "quantity": 4, "carrier_relation": "carrying"}
        ],
    )

    assert crossing.direction == "ENTRY"
    assert hasattr(crossing, "ledger_entries")
    assert len(crossing.ledger_entries) == 1

    rec = crossing.ledger_entries[0]
    assert rec.material_id == mat.material_id
    assert rec.unit_quantity == 4
    assert rec.person_id == emp.employee_id
    assert rec.person_name == emp.name

    # Check inventory balance updated
    balances = await InventoryLedgerEngine.get_inventory_balance(v9_session, material_id=mat.material_id)
    assert balances[0]["currentStock"] == 4


# ==============================================================================
# TEST 12: Dense Bookshelf File Instance Counting (Exact Per-Instance Count)
# ==============================================================================
def test_dense_bookshelf_file_instance_counting():
    """User Question: Can the system detect and count how many files are on a bookshelf?
    Answer: YES.
    Tests DenseShelfCountingService on a synthetic shelf scene with 6 distinct vertical files,
    horizontal planks, and a background wall picture to verify separation and false-positive rejection.
    """
    img = np.zeros((600, 800, 3), dtype=np.uint8)
    img[:] = (230, 230, 230)  # Light room background

    # Draw shelf fixture: outer box [100, 150, 600, 300]
    cv2.rectangle(img, (100, 150), (700, 450), (60, 40, 25), 6)  # Dark wood frame
    # Horizontal divider plank at y = 300
    cv2.line(img, (100, 300), (700, 300), (60, 40, 25), 8)

    # Shelf Tier 1 (y: 155 to 295, height = 140px):
    # Draw 6 distinct vertical document files/binders with varied colors
    file_colors = [
        (40, 40, 180),    # Red binder
        (180, 40, 40),    # Blue binder
        (40, 160, 40),    # Green binder
        (30, 30, 30),     # Black binder
        (50, 180, 180),   # Yellow binder
        (160, 160, 160),  # White binder
    ]

    start_x = 130
    spine_w = 26
    for i, col in enumerate(file_colors):
        x = start_x + i * (spine_w + 2)
        # Fill file spine
        cv2.rectangle(img, (x, 160), (x + spine_w, 292), col, -1)
        # Black spine border
        cv2.rectangle(img, (x, 160), (x + spine_w, 292), (10, 10, 10), 1)

    # In the second compartment (y: 310 to 445), add an empty shadow area to verify shadow rejection
    cv2.rectangle(img, (400, 320), (650, 440), (25, 25, 25), -1)

    # Draw a framed wall picture in the background above the shelf to test rejection
    cv2.rectangle(img, (300, 20), (550, 120), (40, 40, 40), 4)  # Bezel
    cv2.rectangle(img, (306, 26), (544, 114), (200, 150, 100), -1)  # Canvas

    res = DenseShelfCountingService.count_files_on_shelf(
        frame=img,
        shelf_bbox=[100, 150, 600, 300],
    )

    assert res.shelf_detected is True
    # Exactly 6 vertical files were rendered
    assert res.total_visible_files == 6
    assert len(res.file_instances) == 6
    assert res.file_instances[0].status == "CONFIRMED_VISIBLE"

    # Verify each file has appropriate aspect ratio (height / width >= 1.6)
    for f in res.file_instances:
        assert f.aspect_ratio >= 1.6
        assert f.shelf_level == 1


# ==============================================================================
# TEST 13: REST API Endpoints Verification (/api/materials/... & /api/v1/...)
# ==============================================================================
@pytest.mark.asyncio
async def test_material_flow_rest_api(v9_client: AsyncClient, seeded_catalog):
    """Verifies all Master Prompt V9 REST endpoints via HTTP client."""
    mat = seeded_catalog["cement"]

    # 1. POST /api/materials/movement-ledger (or /api/v1/materials/movement-ledger)
    tx_payload = {
        "materialId": mat.material_id,
        "transactionType": "IN",
        "unitQuantity": 20,
        "direction": "ENTRY",
        "personName": "Vikram Singh",
        "personIdentityStatus": "VERIFIED_KNOWN",
        "carrierRelation": "carrying",
        "packagingType": "bag",
    }
    resp = await v9_client.post("/api/materials/movement-ledger", json=tx_payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["unitQuantity"] == 20
    assert data["transactionType"] == "IN"
    assert data["personName"] == "Vikram Singh"

    # Also test /api/v1 prefix
    resp_v1 = await v9_client.post("/api/v1/materials/movement-ledger", json=tx_payload)
    assert resp_v1.status_code == 200, resp_v1.text

    # 2. GET /api/materials/movement-ledger
    list_resp = await v9_client.get("/api/materials/movement-ledger")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert len(list_data) >= 2

    # 3. GET /api/materials/person-summary/{person_id}
    sum_resp = await v9_client.get("/api/materials/person-summary/Vikram Singh")
    assert sum_resp.status_code == 200
    sum_data = sum_resp.json()
    assert sum_data["personName"] == "Vikram Singh"
    assert sum_data["totalBroughtIn"] == 40  # 20 + 20
    assert sum_data["netMovementBalance"] == 40

    # 4. GET /api/materials/inventory-balance
    bal_resp = await v9_client.get(f"/api/materials/inventory-balance?material_id={mat.material_id}")
    assert bal_resp.status_code == 200
    bal_data = bal_resp.json()
    assert len(bal_data) == 1
    assert bal_data[0]["currentStock"] == 40

    # 5. POST /api/materials/inventory-reconciliation
    recon_payload = {
        "physicalCounts": {mat.sku_code: 38},
        "autoAdjust": True,
    }
    recon_resp = await v9_client.post("/api/materials/inventory-reconciliation", json=recon_payload)
    assert recon_resp.status_code == 200
    recon_data = recon_resp.json()
    assert recon_data["discrepanciesCount"] == 1
    assert recon_data["discrepancies"][0]["discrepancyDelta"] == -2

    # 6. POST /api/materials/shelf-dense-count
    # Generate test image
    test_shelf = np.zeros((300, 400, 3), dtype=np.uint8)
    test_shelf[:] = 200
    # 3 vertical file spines
    for i in range(3):
        cv2.rectangle(test_shelf, (50 + i * 30, 50), (75 + i * 30, 200), (30, 30, 160), -1)

    _, enc = cv2.imencode(".jpg", test_shelf)
    b64_str = base64.b64encode(enc.tobytes()).decode("utf-8")

    shelf_resp = await v9_client.post(
        "/api/materials/shelf-dense-count",
        json={"imageBase64": b64_str, "shelfBbox": [30, 30, 200, 200]},
    )
    assert shelf_resp.status_code == 200
    shelf_data = shelf_resp.json()
    assert shelf_data["shelfDetected"] is True
    assert shelf_data["totalVisibleFiles"] == 3

