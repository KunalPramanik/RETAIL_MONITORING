"""Integration Tests for Camera Fleet Management and Lifecycle"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from src.main import app
from src.db.session import get_db
from src.db.models import Base, Camera, Lane, AuditLog
from src.db.seed import seed_database


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
async def test_list_cameras(client):
    """List cameras endpoint returns seeded fleet."""
    resp = await client.get("/api/cameras")
    assert resp.status_code == 200
    cameras = resp.json()
    assert len(cameras) >= 5
    first = cameras[0]
    assert "cameraId" in first
    assert "label" in first
    assert "status" in first
    assert "ipAddress" in first


@pytest.mark.asyncio
async def test_register_new_camera(client, test_session):
    """Registering a new camera creates a PENDING_SETUP record and audit entry."""
    new_cam_data = {
        "label": "Exit Lane 5 — Self-Checkout North",
        "ipAddress": "192.168.10.45",
        "rtspPath": "/stream0",
        "credentials": "admin:supersecret",
        "laneId": "LANE-01",
        "resolution": "1920x1080",
        "fps": 30,
    }
    resp = await client.post("/api/cameras", json=new_cam_data)
    assert resp.status_code == 201
    cam = resp.json()
    assert cam["status"] == "PENDING_SETUP"
    assert cam["label"] == new_cam_data["label"]
    assert cam["laneId"] == "LANE-01"

    # Verify audit log was recorded
    audit_res = await test_session.execute(
        select(AuditLog).where(AuditLog.entity_id == cam["cameraId"], AuditLog.action == "REGISTER_CAMERA")
    )
    audit = audit_res.scalar_one_or_none()
    assert audit is not None
    assert audit.after_state["label"] == new_cam_data["label"]


@pytest.mark.asyncio
async def test_camera_connection_test_failure_diagnostics(client):
    """Connection test should return specific, actionable diagnostics on failure."""
    # Bad IP
    resp_ip = await client.post(
        "/api/cameras/cam_101/test-connection",
        json={"ipAddress": "192.168.10.255", "rtspPath": "/live"},
    )
    assert resp_ip.status_code == 200
    data_ip = resp_ip.json()
    assert data_ip["success"] is False
    assert "Could not reach" in data_ip["errorMessage"]

    # Bad credentials
    resp_auth = await client.post(
        "/api/cameras/cam_101/test-connection",
        json={"ipAddress": "192.168.10.41", "rtspPath": "/live", "credentials": "user:badpass"},
    )
    assert resp_auth.status_code == 200
    data_auth = resp_auth.json()
    assert data_auth["success"] is False
    assert "401 Unauthorized" in data_auth["errorMessage"]

    # Malformed RTSP path
    resp_path = await client.post(
        "/api/cameras/cam_101/test-connection",
        json={"ipAddress": "192.168.10.41", "rtspPath": "live_no_slash"},
    )
    assert resp_path.status_code == 200
    data_path = resp_path.json()
    assert data_path["success"] is False
    assert "leading slash" in data_path["errorMessage"]


@pytest.mark.asyncio
async def test_camera_connection_test_success(client):
    """Successful connection test returns snapshot frame and flips camera to ONLINE."""
    resp = await client.post(
        "/api/cameras/cam_105/test-connection",
        json={"ipAddress": "192.168.10.55", "rtspPath": "/stream"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["status"] == "ONLINE"
    assert data["snapshotUrl"] is not None

    # Check that cam_105 status flipped to ONLINE
    cam_resp = await client.get("/api/cameras/cam_105")
    assert cam_resp.status_code == 200
    assert cam_resp.json()["status"] == "ONLINE"


@pytest.mark.asyncio
async def test_update_camera_and_reassign_lane(client, test_session):
    """Updating camera metadata and reassigning lane."""
    resp = await client.put(
        "/api/cameras/cam_101",
        json={"label": "Exit Lane 1 — High-Resolution Overhead", "laneId": "LANE-03"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["label"] == "Exit Lane 1 — High-Resolution Overhead"
    assert data["laneId"] == "LANE-03"

    # Verify audit log
    audit_res = await test_session.execute(
        select(AuditLog).where(AuditLog.entity_id == "cam_101", AuditLog.action == "UPDATE_CAMERA")
    )
    audit = audit_res.scalar_one_or_none()
    assert audit is not None
    assert audit.after_state["lane_id"] == "LANE-03"


@pytest.mark.asyncio
async def test_remove_camera_soft_delete(client, test_session):
    """Decommissioning camera soft-deletes record, unbinds lane, and logs audit."""
    resp = await client.delete("/api/cameras/cam_102")
    assert resp.status_code == 200
    data = resp.json()
    assert data["removedAt"] is not None
    assert data["status"] == "OFFLINE"
    assert data["laneId"] is None

    # Normal list should not include cam_102
    list_resp = await client.get("/api/cameras")
    ids = [c["cameraId"] for c in list_resp.json()]
    assert "cam_102" not in ids

    # List with includeRemoved=True should include cam_102
    removed_resp = await client.get("/api/cameras?includeRemoved=true")
    all_ids = [c["cameraId"] for c in removed_resp.json()]
    assert "cam_102" in all_ids


@pytest.mark.asyncio
async def test_create_lane_inline(client):
    """Creating a new sensor lane inline."""
    new_lane = {
        "laneId": "LANE-05",
        "label": "Exit Lane 05 (North Warehouse Staging)",
        "storeId": "store_0402",
    }
    resp = await client.post("/api/lanes", json=new_lane)
    assert resp.status_code == 201
    data = resp.json()
    assert data["laneId"] == "LANE-05"
    assert data["location"] == new_lane["label"]


@pytest.mark.asyncio
async def test_qr_decode_direction_1(client):
    """Tests Direction 1: decoding camera-displayed QR payloads (JSON, URL, Key-Value)."""
    # 1. JSON payload
    json_qr = '{"ip": "192.168.10.77", "model": "Hikvision 4K", "rtsp": "/live/ch1", "user": "admin", "pass": "secret"}'
    resp = await client.post("/api/cameras/qr-decode", json={"qrPayload": json_qr})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ipAddress"] == "192.168.10.77"
    assert data["model"] == "Hikvision 4K"
    assert data["rtspPath"] == "/live/ch1"
    assert data["credentials"] == "admin:secret"

    # 2. RTSP URL payload
    url_qr = "rtsp://operator:cam_pass@192.168.10.88:554/stream0"
    resp2 = await client.post("/api/cameras/qr-decode", json={"qrPayload": url_qr})
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["ipAddress"] == "192.168.10.88"
    assert data2["credentials"] == "operator:cam_pass"
    assert data2["rtspPath"] == "/stream0"

    # 3. Key-value payload
    kv_qr = "IP:192.168.10.99;MODEL:Dahua-IPC;RTSP:/cam/realmonitor"
    resp3 = await client.post("/api/cameras/qr-decode", json={"qrPayload": kv_qr})
    assert resp3.status_code == 200
    data3 = resp3.json()
    assert data3["ipAddress"] == "192.168.10.99"
    assert data3["model"] == "Dahua-IPC"


@pytest.mark.asyncio
async def test_qr_pairing_direction_2(client):
    """Tests Direction 2: generating pairing token, polling status, and camera self-pairing."""
    # 1. Generate pairing token
    tok_req = {"storeId": "store_0402", "laneId": "LANE-01", "wifiSsid": "SEC-OPS-SECURE"}
    resp = await client.post("/api/cameras/pairing-tokens", json=tok_req)
    assert resp.status_code == 200
    tok_data = resp.json()
    assert "tokenId" in tok_data
    assert "tokenValue" in tok_data
    assert "qrPayload" in tok_data
    assert tok_data["status"] == "ACTIVE"
    token_id = tok_data["tokenId"]
    token_val = tok_data["tokenValue"]

    # 2. Poll token status
    status_resp = await client.get(f"/api/cameras/pairing-tokens/{token_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "ACTIVE"

    # 3. Camera device calls /pair with the token
    pair_resp = await client.post("/api/cameras/pair", json={
        "token": token_val,
        "ipAddress": "192.168.10.50",
        "model": "SmartOnvif-Pro",
        "label": "Exit Lane 1 — QR Paired Cam",
    })
    assert pair_resp.status_code == 200
    cam = pair_resp.json()
    assert cam["pairingMethod"] == "QR_APP_GENERATED"
    assert cam["status"] == "PENDING_SETUP"
    assert cam["laneId"] == "LANE-01"
    assert cam["ipAddress"] == "192.168.10.50"

    # 4. Token status is now USED
    status_resp2 = await client.get(f"/api/cameras/pairing-tokens/{token_id}")
    assert status_resp2.status_code == 200
    assert status_resp2.json()["status"] == "USED"
    assert status_resp2.json()["usedByCameraId"] == cam["cameraId"]

    # 5. Re-attempting to use the consumed token fails (single-use constraint)
    repeat_pair = await client.post("/api/cameras/pair", json={"token": token_val})
    assert repeat_pair.status_code == 400


@pytest.mark.asyncio
async def test_scan_now_without_lane_linkage_returns_actionable_error(client):
    """Attempting scan-now on an unbound camera returns actionable HTTP 400 error pointing to settings."""
    # cam_105 in seed has no lane_id assigned
    resp = await client.post("/api/cameras/cam_105/scan-now")
    assert resp.status_code == 400
    data = resp.json()
    assert "Camera setup incomplete: lane linkage was never finished" in data["detail"]
    assert "Settings -> Camera Fleet" in data["detail"]


@pytest.mark.asyncio
async def test_camera_telemetry_endpoint(client):
    """GET /api/cameras/{id}/telemetry returns live observed FPS, bitrate, and dropped frames."""
    # First send heartbeat with telemetry
    hb_resp = await client.post(
        "/api/cameras/cam_101/heartbeat",
        json={"fpsObserved": 29.5, "bitrateKbps": 4200.0, "droppedFrames": 2},
    )
    assert hb_resp.status_code == 200

    # Query telemetry
    resp = await client.get("/api/cameras/cam_101/telemetry")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cameraId"] == "cam_101"
    assert data["fpsObserved"] == 29.5
    assert data["bitrateKbps"] == 4200.0
    assert data["droppedFrames"] == 2



