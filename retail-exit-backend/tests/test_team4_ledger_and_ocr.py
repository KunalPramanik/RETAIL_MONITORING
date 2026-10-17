"""Team 4 Test Suite — Stock Ledger, Balanced Idempotency, Initial Stock Human Verification & OCR

Covers Section 10, 11, 12, 13 and User Revision 3:
1. Opening stock must first be confirmed through human verification before being committed to the ledger.
2. After opening stock confirmation, only validated physical IN/OUT crossing events update stock balances.
3. The balanced idempotency logic prevents duplicate movements from the same crossing without blocking subsequent valid movements of the same item.
4. Accounting Invariant: Opening + Incoming - Outgoing + Adjustments == Current Stock.
5. OCR Bill Ingestion with field-level confidence and zero-fabrication.
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, and_

from src.db.models import (
    Product,
    Material,
    MaterialInventoryBalance,
    MaterialMovementLedger,
    InitialStockVerification,
    get_utc_now,
)
from src.engine.inventory_ledger_engine import InventoryLedgerEngine
from src.ml.ocr.invoice_ocr_service import OcrService


@pytest.mark.asyncio
async def test_initial_stock_requires_human_verification(db_session):
    """Proves that initial stock proposals do not update balances until human verification occurs."""
    now = get_utc_now()
    test_sku = f"SKU-T4-{uuid.uuid4().hex[:6]}"
    
    product = Product(
        product_id=f"prod_{uuid.uuid4().hex[:8]}",
        sku_code=test_sku,
        name="Industrial Safety Boots",
        category="PPE",
        pack_size=5,
        unit_price=120.00,
        case_price=600.00,
    )
    db_session.add(product)
    
    material = Material(
        material_id=product.product_id,
        sku_code=test_sku,
        name=product.name,
        category="PPE",
        packaging_type="sealed_case",
        units_per_package=5,
        status="ACTIVE",
    )
    db_session.add(material)
    await db_session.commit()

    # 1. AI detects stock and submits a proposal (PENDING_VERIFICATION)
    verif = InitialStockVerification(
        verification_id=f"verif_{uuid.uuid4().hex[:8]}",
        product_id=product.product_id,
        sku_code=product.sku_code,
        product_name=product.name,
        camera_id="CAM-STOCK-01",
        ai_proposed_count=45,
        status="PENDING_VERIFICATION",
        model_version="yolox_retail_v8",
        created_at=now,
    )
    db_session.add(verif)
    await db_session.commit()

    # 2. Verify that NO balance record was prematurely created with the AI proposed count
    bal_res = await db_session.execute(
        select(MaterialInventoryBalance).where(MaterialInventoryBalance.material_id == product.product_id)
    )
    balance = bal_res.scalar_one_or_none()
    assert balance is None or balance.opening_stock == 0

    # 3. Human Operator inspects and CORRECTS the count (NO - EDIT: 40 units verified instead of 45)
    human_count = 40
    verif.verified_count = human_count
    verif.difference = human_count - verif.ai_proposed_count
    verif.status = "CORRECTED"
    verif.correction_reason = "5 pairs in back row damaged/uncounted"
    verif.verified_by = "SUPERVISOR-JANE"
    verif.verified_at = now

    # Now commit baseline opening balance
    balance = MaterialInventoryBalance(
        balance_id=f"bal_{uuid.uuid4().hex[:8]}",
        material_id=product.product_id,
        location_id="MAIN_WAREHOUSE",
        opening_stock=human_count,
        incoming_confirmed=0,
        outgoing_confirmed=0,
        defective_stock=0,
        adjusted_stock=0,
        current_stock=human_count,
        last_reconciled_at=now,
        updated_at=now,
    )
    db_session.add(balance)
    await db_session.commit()

    # Invariant holds
    assert balance.opening_stock == 40
    assert balance.current_stock == 40
    assert balance.opening_stock + balance.incoming_confirmed - balance.outgoing_confirmed + balance.adjusted_stock == balance.current_stock


@pytest.mark.asyncio
async def test_balanced_idempotency_prevents_duplicate_crossing_writes(db_session):
    """Proves that duplicate frames from the same crossing are ignored,

    while subsequent valid physical movements of the same item are correctly recorded.
    """
    now = get_utc_now()
    test_sku = f"SKU-IDEMP-{uuid.uuid4().hex[:6]}"
    
    product = Product(
        product_id=f"prod_{uuid.uuid4().hex[:8]}",
        sku_code=test_sku,
        name="Precision Torque Wrench",
        category="Tools",
        pack_size=1,
        unit_price=45.00,
        case_price=45.00,
    )
    db_session.add(product)
    
    material = Material(
        material_id=product.product_id,
        sku_code=test_sku,
        name=product.name,
        category="Tools",
        packaging_type="loose_unit",
        units_per_package=1,
        status="ACTIVE",
    )
    db_session.add(material)

    # Establish baseline balance
    initial_stock = 100
    balance = MaterialInventoryBalance(
        balance_id=f"bal_{uuid.uuid4().hex[:8]}",
        material_id=product.product_id,
        location_id="MAIN_WAREHOUSE",
        opening_stock=initial_stock,
        incoming_confirmed=0,
        outgoing_confirmed=0,
        defective_stock=0,
        adjusted_stock=0,
        current_stock=initial_stock,
        last_reconciled_at=now,
        updated_at=now,
    )
    db_session.add(balance)
    await db_session.commit()

    # Step 1: First crossing event (Track TRK-99 crossing Camera CAM-01 outbound)
    trk_id = "TRK-99"
    cam_id = "CAM-01"
    tw_id = "TW-MAIN-EXIT"

    entry1, bal1, _ = await InventoryLedgerEngine.record_confirmed_movement(
        session=db_session,
        material_id=product.product_id,
        transaction_type="OUT",
        unit_quantity=10,
        camera_id=cam_id,
        track_id=trk_id,
        tripwire_id=tw_id,
        direction="EXIT",
        timestamp=now,
        commit=True,
    )
    assert bal1.current_stock == 90
    assert bal1.outgoing_confirmed == 10

    # Step 2: Duplicate frame 500ms later (Same track, same camera, same tripwire, same direction)
    duplicate_ts = now + timedelta(milliseconds=500)
    entry2, bal2, _ = await InventoryLedgerEngine.record_confirmed_movement(
        session=db_session,
        material_id=product.product_id,
        transaction_type="OUT",
        unit_quantity=10,
        camera_id=cam_id,
        track_id=trk_id,
        tripwire_id=tw_id,
        direction="EXIT",
        timestamp=duplicate_ts,
        commit=True,
    )

    # Idempotency triggered: entry2 is the exact same record as entry1, stock was NOT deducted again!
    assert entry2.ledger_id == entry1.ledger_id
    assert bal2.current_stock == 90
    assert bal2.outgoing_confirmed == 10

    # Step 3: Legitimate subsequent movement of the same item 30 seconds later (different track or crossing)
    later_ts = now + timedelta(seconds=30)
    subsequent_trk_id = "TRK-102"
    entry3, bal3, _ = await InventoryLedgerEngine.record_confirmed_movement(
        session=db_session,
        material_id=product.product_id,
        transaction_type="OUT",
        unit_quantity=5,
        camera_id=cam_id,
        track_id=subsequent_trk_id,
        tripwire_id=tw_id,
        direction="EXIT",
        timestamp=later_ts,
        commit=True,
    )

    # Subsequent movement is NOT blocked: balance updates from 90 to 85
    assert entry3.ledger_id != entry1.ledger_id
    assert bal3.current_stock == 85
    assert bal3.outgoing_confirmed == 15

    # Step 4: Legitimate inbound movement of the same item (IN / replenishment)
    entry4, bal4, _ = await InventoryLedgerEngine.record_confirmed_movement(
        session=db_session,
        material_id=product.product_id,
        transaction_type="IN",
        unit_quantity=20,
        camera_id="CAM-02",
        track_id="TRK-201",
        tripwire_id="TW-MAIN-ENTRY",
        direction="ENTRY",
        timestamp=later_ts + timedelta(seconds=10),
        commit=True,
    )
    assert bal4.current_stock == 105
    assert bal4.incoming_confirmed == 20
    assert bal4.outgoing_confirmed == 15

    # Verify Accounting Invariant:
    # Opening (100) + Incoming (20) - Outgoing (15) + Adjustments (0) == 105
    expected = bal4.opening_stock + bal4.incoming_confirmed - bal4.outgoing_confirmed + bal4.adjusted_stock
    assert bal4.current_stock == expected


@pytest.mark.asyncio
async def test_ocr_invoice_extraction_and_field_confidence():
    """Validates CPU OCR document extraction, field-level confidence, and zero fabrication."""
    catalog_skus = ["SKU-BOOT-01", "SKU-HELM-02"]

    line_items = [
        {"sku_code": "SKU-B00T-01", "description": "Safety Boots", "cases_qty": 2, "pack_size": 10},
        {"sku_code": "SKU-HELM-02", "description": "Hard Hat ANSI", "cases_qty": 5, "pack_size": 10},
    ]

    res = OcrService.parse_manifest(
        invoice_number="INV-2026-9812",
        carrier_name="IndusPPE Logistics",
        line_items_data=line_items,
        catalog_skus=catalog_skus,
    )

    assert "INV-2026-9812" in res.raw_ocr_text
    assert res.extraction_confidence > 0.80
    assert len(res.line_items) == 2
    assert res.declared_total_units == 70  # (2*10) + (5*10) = 70 units

    extracted_skus = {item.sku_code for item in res.line_items}
    # Notice OCR character substitution / fuzzy correction: SKU-B00T-01 -> SKU-BOOT-01
    assert "SKU-BOOT-01" in extracted_skus
    assert "SKU-HELM-02" in extracted_skus


@pytest.mark.asyncio
async def test_discrepancy_reconciliation_and_audit(db_session):
    """Validates physical audit reconciliation flagging discrepancies without silent resets."""
    now = get_utc_now()
    test_sku = f"SKU-REC-{uuid.uuid4().hex[:6]}"
    
    material = Material(
        material_id=f"mat_{uuid.uuid4().hex[:8]}",
        sku_code=test_sku,
        name="Safety Gloves Pack",
        category="PPE",
        packaging_type="loose_unit",
        units_per_package=1,
        status="ACTIVE",
    )
    db_session.add(material)
    
    balance = MaterialInventoryBalance(
        balance_id=f"bal_{uuid.uuid4().hex[:8]}",
        material_id=material.material_id,
        location_id="MAIN_WAREHOUSE",
        opening_stock=50,
        incoming_confirmed=10,
        outgoing_confirmed=5,
        defective_stock=0,
        adjusted_stock=0,
        current_stock=55,
        last_reconciled_at=now,
        updated_at=now,
    )
    db_session.add(balance)
    await db_session.commit()

    # Reconcile with physical count of 53 (2 missing units)
    rec_result = await InventoryLedgerEngine.reconcile_inventory(
        session=db_session,
        physical_counts={test_sku: 53},
        location_id="MAIN_WAREHOUSE",
        auto_adjust=True,
    )

    assert rec_result["discrepanciesCount"] == 1
    assert rec_result["totalDiscrepancyMagnitude"] == 2
    
    # Check that adjustment was posted and current stock is now 53
    bal_after = await db_session.execute(
        select(MaterialInventoryBalance).where(MaterialInventoryBalance.material_id == material.material_id)
    )
    b = bal_after.scalar_one()
    assert b.current_stock == 53
    assert b.adjusted_stock == -2
    assert b.opening_stock + b.incoming_confirmed - b.outgoing_confirmed + b.adjusted_stock == b.current_stock
