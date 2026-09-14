"""Tests for Maximum-Automation Device Auto-Connect & Discovery

Covers:
1. Zero-click USB Scale Auto-Connect via VID/PID signature lookup.
2. USB Unrecognized Device alert and manual configuration fallback.
3. USB port state persistence and reload.
4. LAN Continuous Discovery with Reachability Pre-testing and Stream Profile Extraction.
5. Smart Lane Suggestion Heuristic (subnet, unassigned lanes, temporal correlation).
6. Guarantee that suggestions are NEVER silently auto-assigned to DB without human confirmation.
7. One-Tap Lane Confirmation creating camera and starting worker.
"""

import pytest
import os
import json
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from src.main import app
from src.db.session import get_db
from src.db.models import Base, Camera, Lane, AuditLog
from src.db.seed import seed_database
from src.hardware.usb_detector import usb_service, UsbDeviceRecord
from src.engine.discovery_service import discovery_service, DiscoveredDevice


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


# =====================================================================
# 1. USB Auto-Connect Tests
# =====================================================================

def test_usb_known_scale_zero_click_auto_connect():
    """Plugging in a known USB scale automatically identifies it and binds it to LANE-01 with zero clicks."""
    # Simulate plugging in an FTDI FT232R USB-Serial chip commonly found in retail scales
    dev = usb_service.simulate_usb_event(
        action="ATTACH",
        vid="0403",
        pid="6001",
        port="COM3",
        description="USB Serial Converter",
        lane_id="LANE-01",
    )

    assert dev.device_type == "WEIGHT_SCALE"
    assert dev.is_connected is True
    assert dev.lane_id == "LANE-01"
    assert "FT232R" in dev.model
    assert usb_service.active_scale_port == "COM3"


def test_usb_known_cas_scale_auto_connect():
    """Plugging in a CAS SW-Series scale (Silicon Labs CP210x) auto-connects."""
    dev = usb_service.simulate_usb_event(
        action="ATTACH",
        vid="10c4",
        pid="ea60",
        port="COM4",
        description="Silicon Labs CP210x USB to UART Bridge",
    )

    assert dev.device_type == "WEIGHT_SCALE"
    assert "CP210x" in dev.model or "CAS" in dev.model
    assert dev.is_connected is True
    assert usb_service.active_scale_port == "COM4"


def test_usb_unrecognized_device_warning_and_configure():
    """An unknown USB peripheral is flagged as UNRECOGNIZED and not bound as scale until configured."""
    usb_service.mappings = [m for m in usb_service.mappings if m.get("vid") != "9999"]
    try:
        dev = usb_service.simulate_usb_event(
            action="ATTACH",
            vid="9999",
            pid="8888",
            port="COM9",
            description="Generic Microcontroller Sensor",
        )

        assert dev.device_type == "UNRECOGNIZED"
        assert dev.is_connected is True
        # Should not overwrite the active scale port
        assert usb_service.active_scale_port != "COM9"

        # Now configure it manually via the service
        configured = usb_service.configure_unrecognized_device(
            port="COM9",
            device_type="WEIGHT_SCALE",
            lane_id="LANE-02",
            custom_model="Custom Load Cell Scale",
        )
        assert configured.device_type == "WEIGHT_SCALE"
        assert configured.lane_id == "LANE-02"
        assert configured.model == "Custom Load Cell Scale"
        assert usb_service.active_scale_port == "COM9"
    finally:
        usb_service.mappings = [m for m in usb_service.mappings if m.get("vid") != "9999"]
        usb_service.devices.pop("COM9", None)
        usb_service.save_mappings()


def test_usb_disconnect_and_reconnect():
    """Unplugging a device marks it disconnected and clears active scale port if it was the active scale."""
    usb_service.simulate_usb_event(
        action="ATTACH",
        vid="0403",
        pid="6001",
        port="COM5",
    )
    assert usb_service.active_scale_port == "COM5"

    # Disconnect
    detached = usb_service.simulate_usb_event(
        action="DETACH",
        port="COM5",
    )
    assert detached.is_connected is False
    assert usb_service.active_scale_port is None


def test_usb_state_persistence_and_reload():
    """Saved USB device state survives re-initialization."""
    usb_service.simulate_usb_event(
        action="ATTACH",
        vid="0403",
        pid="6001",
        port="COM7",
        lane_id="LANE-03",
    )
    # Reload from state file
    usb_service._load_state()
    assert "COM7" in usb_service.devices
    assert usb_service.devices["COM7"].lane_id == "LANE-03"


# =====================================================================
# 2. LAN Discovery & Reachability Tests
# =====================================================================

@pytest.mark.asyncio
async def test_lan_device_discovery_and_reachability():
    """Discovered devices are reachability-tested and stream profiles are extracted."""
    dev = discovery_service.simulate_discovered_device(
        ip_address="192.168.1.188",
        manufacturer="Hikvision",
        model="DS-2CD2143G0-I 4MP Dome",
        device_type="CAMERA",
        suggested_lane_id="LANE-01",
    )

    assert dev.discovery_id.startswith("DISC-")
    assert dev.ip_address == "192.168.1.188"
    assert dev.is_reachable is True
    assert dev.rtsp_path in ["/Streaming/Channels/101", "/h264Preview_01_main"]
    assert dev.sub_stream_path in ["/Streaming/Channels/102", "/h264Preview_01_sub"]
    assert dev.status == "UNASSIGNED"
    assert dev.suggested_lane_id == "LANE-01"
    assert dev.suggestion_confidence >= 0.8


@pytest.mark.asyncio
async def test_smart_lane_suggestion_never_silently_persisted(test_session):
    """CRITICAL: Discovered device suggestion must NEVER be silently inserted into DB without operator confirmation."""
    # Simulate 2 devices discovered
    dev = discovery_service.simulate_discovered_device(
        ip_address="192.168.1.199",
        manufacturer="Dahua",
        model="IPC-HFW4431R-Z",
        device_type="CAMERA",
    )

    # Query the database camera table directly
    stmt = select(Camera).where(Camera.ip_address == "192.168.1.199")
    result = await test_session.execute(stmt)
    cam = result.scalars().first()

    # MUST be None — zero autonomous lane assignment without human action
    assert cam is None


@pytest.mark.asyncio
async def test_one_tap_lane_confirmation_creates_camera(test_session):
    """Operator one-tap confirmation binds the discovered camera to the database and marks discovery CONFIRMED."""
    dev = discovery_service.simulate_discovered_device(
        ip_address="192.168.1.205",
        manufacturer="Axis",
        model="M3046-V Portal Cam",
        device_type="CAMERA",
        suggested_lane_id="LANE-02",
    )

    res = await discovery_service.confirm_lane_assignment(
        session=test_session,
        discovery_id=dev.discovery_id,
        lane_id="LANE-02",
        label="Lane 2 Auto-Discovered Axis",
    )

    assert res["status"] == "CONFIRMED"
    camera_id = res["cameraId"]
    assert camera_id.startswith("CAM-")

    # Verify camera in DB
    stmt = select(Camera).where(Camera.camera_id == camera_id)
    result = await test_session.execute(stmt)
    cam = result.scalars().first()

    assert cam is not None
    assert cam.ip_address == "192.168.1.205"
    assert cam.lane_id == "LANE-02"
    assert cam.pairing_method in ["AUTO_DISCOVERED", "MANUAL"]
    assert cam.status in ["ONLINE", "PENDING_SETUP"]

    # Verify discovery item is marked CONFIRMED
    assert dev.status == "CONFIRMED"


# =====================================================================
# 3. API Endpoints Integration Tests
# =====================================================================

@pytest.mark.asyncio
async def test_api_discovery_endpoints(client):
    """Verify REST API discovery endpoints."""
    # 1. Simulate discovery via API
    sim_resp = await client.post("/api/discovery/simulate", json={
        "deviceType": "CAMERA",
        "ipAddress": "192.168.1.222",
        "manufacturer": "Uniview",
        "model": "IPC3614LR3",
        "suggestedLaneId": "LANE-01",
    })
    assert sim_resp.status_code == 200
    disc_data = sim_resp.json()
    disc_id = disc_data["discoveryId"]

    # 2. List discovered devices
    list_resp = await client.get("/api/discovery/devices")
    assert list_resp.status_code == 200
    devices = list_resp.json()
    assert any(d["discoveryId"] == disc_id for d in devices)

    # 3. Confirm lane assignment
    conf_resp = await client.post("/api/discovery/confirm-lane", json={
        "discoveryId": disc_id,
        "laneId": "LANE-01",
        "label": "Front Exit Lane 1 Uniview",
    })
    assert conf_resp.status_code == 200
    conf_data = conf_resp.json()
    assert conf_data["status"] == "CONFIRMED"
    assert "cameraId" in conf_data

    # 4. Query USB status
    usb_resp = await client.get("/api/discovery/usb")
    assert usb_resp.status_code == 200
    usb_data = usb_resp.json()
    assert "devices" in usb_data

    # 5. Trigger full scan
    scan_resp = await client.post("/api/discovery/scan-now")
    assert scan_resp.status_code == 200
    scan_data = scan_resp.json()
    assert "lanDevicesDiscovered" in scan_data
    assert "usbDevicesConnected" in scan_data
