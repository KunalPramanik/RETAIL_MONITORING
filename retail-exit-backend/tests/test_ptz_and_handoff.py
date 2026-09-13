"""Tests for Multi-Camera PTZ Controls and Cross-Camera Tracking Hand-Off"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from src.main import app
from src.db.session import get_db
from src.db.models import Base, Camera, Store, Lane, get_utc_now
from src.engine.ptz_service import ptz_service, PTZNotSupportedError
from src.ml.tracker_service import CrossCameraTracker


@pytest.fixture
async def test_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
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
async def test_ptz_service_fixed_camera_rejection():
    """Fixed cameras must cleanly reject PTZ commands with PTZNotSupportedError."""
    fixed_cam = Camera(
        camera_id="CAM-FIXED-01",
        label="Lane 1 Fixed Overhead",
        ip_address="192.168.1.101",
        rtsp_path="/live/fixed/ch0",
        status="ONLINE",
    )
    assert not ptz_service.is_ptz_capable(fixed_cam)

    with pytest.raises(PTZNotSupportedError) as exc_info:
        await ptz_service.continuous_move(fixed_cam, pan_velocity=0.5)
    assert "does not support PTZ" in str(exc_info.value)


@pytest.mark.asyncio
async def test_ptz_service_motion_and_presets():
    """PTZ capable cameras must support pan/tilt/zoom motion, stop, and preset navigation."""
    ptz_cam = Camera(
        camera_id="CAM-PTZ-99",
        label="Portal 1 Speed Dome PTZ",
        ip_address="192.168.1.199",
        rtsp_path="/onvif/ptz/main",
        status="ONLINE",
    )
    assert ptz_service.is_ptz_capable(ptz_cam)

    # 1. Move continuous
    move_res = await ptz_service.continuous_move(ptz_cam, pan_velocity=1.0, tilt_velocity=0.5, zoom_velocity=1.0)
    assert move_res["isMoving"] is True
    assert move_res["pan"] > 0.0
    assert move_res["zoom"] > 1.0

    # 2. Stop
    stop_res = await ptz_service.stop(ptz_cam)
    assert stop_res["isMoving"] is False

    # 3. Goto Preset 2 (Pedestal/Turnstile Close-Up)
    preset_res = await ptz_service.goto_preset(ptz_cam, preset_id=2)
    assert preset_res["activePresetId"] == 2
    assert preset_res["zoom"] == 2.5
    assert preset_res["pan"] == 0.2


@pytest.mark.asyncio
async def test_ptz_http_endpoints(client: AsyncClient, test_session: AsyncSession):
    """Verify HTTP /api/cameras/{id}/ptz endpoints for both PTZ and fixed cameras."""
    now = get_utc_now()
    store = Store(store_id="STORE-PTZ-TEST", name="PTZ Test Store", timezone="UTC")
    lane = Lane(lane_id="LANE-PTZ-TEST", store_id="STORE-PTZ-TEST", label="Lane PTZ", status="ONLINE")
    test_session.add_all([store, lane])
    await test_session.flush()

    fixed_cam = Camera(
        camera_id="CAM-HTTP-FIXED",
        lane_id="LANE-PTZ-TEST",
        label="Fixed Wall Cam",
        ip_address="192.168.1.50",
        rtsp_path="/stream/fixed",
        status="ONLINE",
        added_at=now,
    )
    ptz_cam = Camera(
        camera_id="CAM-HTTP-PTZ",
        lane_id="LANE-PTZ-TEST",
        label="Overhead PTZ Dome 360",
        ip_address="192.168.1.51",
        rtsp_path="/stream/ptz",
        status="ONLINE",
        added_at=now,
    )
    test_session.add_all([fixed_cam, ptz_cam])
    await test_session.commit()

    # 1. Fixed camera move must return HTTP 422
    res_fixed = await client.post("/api/cameras/CAM-HTTP-FIXED/ptz/move", json={"pan": 0.5, "tilt": 0.0})
    assert res_fixed.status_code == 422
    assert "does not support PTZ" in res_fixed.json()["detail"]

    # 2. PTZ camera move must return HTTP 200
    res_ptz = await client.post("/api/cameras/CAM-HTTP-PTZ/ptz/move", json={"pan": 0.8, "tilt": -0.4, "zoom": 1.0})
    assert res_ptz.status_code == 200
    data = res_ptz.json()
    assert data["isMoving"] is True
    assert data["pan"] > 0.0

    # 3. PTZ camera stop must return HTTP 200
    res_stop = await client.post("/api/cameras/CAM-HTTP-PTZ/ptz/stop")
    assert res_stop.status_code == 200
    assert res_stop.json()["isMoving"] is False

    # 4. Preset navigation
    res_preset = await client.post("/api/cameras/CAM-HTTP-PTZ/ptz/preset/1")
    assert res_preset.status_code == 200
    assert res_preset.json()["activePresetId"] == 1

    # 5. Get status
    res_status = await client.get("/api/cameras/CAM-HTTP-PTZ/ptz/status")
    assert res_status.status_code == 200
    assert res_status.json()["isPtzCapable"] is True
    assert len(res_status.json()["availablePresets"]) == 4


def test_cross_camera_tracking_and_double_counting():
    """Verify Re-ID matching hands off tracking across cameras and suppresses duplicate events."""
    tracker = CrossCameraTracker(handoff_window_sec=10.0, double_count_suppression_window_sec=8.0)

    # Synthetic 128-d Re-ID embedding
    person_embedding = [0.1] * 128

    t0 = 1000.0
    # Step 1: Subject first spotted in Lane 1 on Camera 1
    track1, is_handoff_1 = tracker.process_detection(
        camera_id="CAM-LANE-01",
        lane_id="LANE-01",
        embedding=person_embedding,
        timestamp=t0,
    )
    assert not is_handoff_1
    assert track1.current_camera_id == "CAM-LANE-01"
    assert track1.camera_history == ["CAM-LANE-01"]
    track_id = track1.track_id

    # Simulate exit event emitted on Lane 1
    tracker.mark_event_emitted(track_id, event_id="EVT-001", timestamp=t0 + 1.0)

    # Step 2: 3 seconds later, subject steps across to adjacent Lane 2 (Camera 2)
    # Similar embedding (slight noise: cosine similarity ~0.98)
    noisy_embedding = [0.1 + (0.005 if i % 2 == 0 else -0.005) for i in range(128)]
    track2, is_handoff_2 = tracker.process_detection(
        camera_id="CAM-LANE-02",
        lane_id="LANE-02",
        embedding=noisy_embedding,
        timestamp=t0 + 3.0,
    )

    # Hand-off must be recognized
    assert is_handoff_2 is True
    assert track2.track_id == track_id  # Same identity preserved!
    assert track2.is_handed_off is True
    assert track2.camera_history == ["CAM-LANE-01", "CAM-LANE-02"]
    assert track2.tracking_label == "Multi-Camera Tracking: CAM-LANE-01 -> CAM-LANE-02"

    # Step 3: Verify double-counting suppression
    # Since EVT-001 was emitted at t=1001, and current time is t=1003 (2s elapsed < 8s window),
    # double-counting MUST be suppressed!
    suppress = tracker.should_suppress_exit_event(track_id, current_ts=t0 + 3.0)
    assert suppress is True, "Second exit event must be suppressed to prevent double-counting!"

    # Step 4: After suppression window elapses (e.g., 10s later), suppression expires
    suppress_expired = tracker.should_suppress_exit_event(track_id, current_ts=t0 + 15.0)
    assert suppress_expired is False
