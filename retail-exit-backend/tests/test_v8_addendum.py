"""Automated Tests for V8 Incremental Addendum APIs

Tests:
1. Live Camera Detection feed (GET /api/cameras/detections/live)
2. Movement Monitor feed (GET /api/events/movement-monitor)
3. Initial Stock Baseline Verification (GET /api/inventory/verification)
4. Confirming Baseline as Accurate (POST /api/inventory/verification/{id}/confirm with accept_proposed=True)
5. Correcting Baseline with Human Override (POST /api/inventory/verification/{id}/confirm with accept_proposed=False)
6. Proposing new verification baseline (POST /api/inventory/verification/propose)
"""

import pytest
from httpx import AsyncClient
from tests.conftest import TestingSessionLocal
from src.db.models import Product, Camera, Lane, Store, Material, InitialStockVerification, MaterialInventoryBalance
from src.security import create_access_token


@pytest.mark.anyio
async def test_live_camera_detections(async_client: AsyncClient):
    # Setup camera and product in db
    async with TestingSessionLocal() as session:
        store = Store(store_id="STORE-ADDENDUM-1", name="Addendum Store", timezone="UTC")
        lane = Lane(lane_id="LANE-ADDENDUM-1", store_id="STORE-ADDENDUM-1", label="Lane Addendum", status="ONLINE")
        cam = Camera(
            camera_id="CAM-ADDENDUM-01",
            label="Front Gate Camera",
            lane_id="LANE-ADDENDUM-1",
            ip_address="192.168.1.199",
            rtsp_path="/live/front",
            stream_url="rtsp://127.0.0.1:8554/live",
            status="ONLINE"
        )
        prod = Product(
            product_id="PROD-ADDENDUM-001",
            sku_code="SKU-TEST-001",
            name="Organic Almond Milk 1L",
            category="Beverages",
            pack_size=12,
            unit_price=4.50,
            case_price=54.00
        )
        session.add_all([store, lane, cam, prod])
        await session.commit()

    resp = await async_client.get("/api/cameras/detections/live?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.anyio
async def test_movement_monitor(async_client: AsyncClient):
    resp = await async_client.get("/api/events/movement-monitor?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.anyio
async def test_initial_stock_verification_workflow(async_client: AsyncClient):
    # Setup test product, material and balance
    async with TestingSessionLocal() as session:
        prod = Product(
            product_id="PROD-VERIF-101",
            sku_code="SKU-VERIF-101",
            name="Premium Dark Roast Coffee",
            category="Groceries",
            pack_size=6,
            unit_price=12.00,
            case_price=72.00
        )
        mat = Material(
            material_id="PROD-VERIF-101",
            sku_code="SKU-VERIF-101",
            name="Premium Dark Roast Coffee",
            category="Groceries"
        )
        balance = MaterialInventoryBalance(
            balance_id="bal-verif-101",
            material_id="PROD-VERIF-101",
            opening_stock=0,
            current_stock=0
        )
        verif = InitialStockVerification(
            verification_id="verif-101",
            product_id="PROD-VERIF-101",
            sku_code="SKU-VERIF-101",
            product_name="Premium Dark Roast Coffee",
            ai_proposed_count=45,
            model_version="yolox-v8.2-shelf",
            status="PENDING_VERIFICATION",
            snapshot_url="/snapshots/shelf_PROD-VERIF-101.jpg",
        )
        session.add_all([prod, mat, balance, verif])
        await session.commit()

    # 1. Fetch initial stock verification list (auto-proposes baseline for new catalog products)
    list_resp = await async_client.get("/api/inventory/verification")
    assert list_resp.status_code == 200
    verifications = list_resp.json()
    assert len(verifications) > 0
    
    target_verif = next((v for v in verifications if v["productId"] == "PROD-VERIF-101"), None)
    assert target_verif is not None
    verif_id = target_verif["verificationId"]
    assert target_verif["status"] == "PENDING_VERIFICATION"
    assert target_verif["aiProposedCount"] >= 0

    # 2. Confirm proposed count [ YES ]
    admin_token = create_access_token(subject="AUDITOR-1", role="ADMIN")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    yes_resp = await async_client.post(
        f"/api/inventory/verification/{verif_id}/confirm",
        json={"isCorrect": True},
        headers=admin_headers
    )
    assert yes_resp.status_code == 200
    yes_data = yes_resp.json()
    assert yes_data["verificationStatus"] == "VERIFIED_ACCURATE"
    assert yes_data["verifiedCount"] == target_verif["aiProposedCount"]
    assert yes_data["difference"] == 0

    # 3. Create another proposed verification and test [ NO / EDIT ] correction
    async with TestingSessionLocal() as session:
        prod2 = Product(
            product_id="PROD-VERIF-102",
            sku_code="SKU-VERIF-102",
            name="Organic Green Tea Bags",
            category="Beverages",
            pack_size=24,
            unit_price=6.50,
            case_price=156.00
        )
        mat2 = Material(
            material_id="PROD-VERIF-102",
            sku_code="SKU-VERIF-102",
            name="Organic Green Tea Bags",
            category="Beverages"
        )
        balance2 = MaterialInventoryBalance(
            balance_id="bal-verif-102",
            material_id="PROD-VERIF-102",
            opening_stock=0,
            current_stock=0
        )
        session.add_all([prod2, mat2, balance2])
        await session.commit()

    propose_resp = await async_client.post(
        "/api/inventory/verification/propose",
        json={
            "productId": "PROD-VERIF-102",
            "aiProposedCount": 50,
            "modelVersion": "yolox-v8.2-shelf",
            "snapshotUrl": "/snapshots/shelf_PROD-VERIF-102.jpg"
        },
        headers=admin_headers
    )
    assert propose_resp.status_code == 200
    verif2_id = propose_resp.json()["verificationId"]

    # Reject / Correct with manual physical count [ NO / EDIT ]
    correction_resp = await async_client.post(
        f"/api/inventory/verification/{verif2_id}/confirm",
        json={
            "isCorrect": False,
            "correctedCount": 42,
            "reason": "8 units damaged in storage pallet recount"
        },
        headers=admin_headers
    )
    assert correction_resp.status_code == 200
    corr_data = correction_resp.json()
    assert corr_data["verificationStatus"] == "CORRECTED"
    assert corr_data["verifiedCount"] == 42
    assert corr_data["difference"] == -8

