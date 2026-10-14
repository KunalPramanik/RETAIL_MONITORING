"""Camera Fleet Resilience & Fault Tolerance Test Suite

Covers:
- Multi-camera batch transaction isolation (isolated sessions preventing rollback contagion)
- Inference watchdog timeout and 3-state circuit breaker protection against model stalls
"""

import asyncio
import time
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import select

from src.core.config import settings
from src.engine.circuit_breaker import InferenceCircuitBreaker, CircuitBreakerOpenException, CircuitState
from src.engine.camera_worker import camera_worker
from src.db.models import Camera, get_utc_now
from src.db.session import AsyncSessionLocal


@pytest.mark.asyncio
async def test_circuit_breaker_state_transitions():
    """Verifies CLOSED -> OPEN -> HALF_OPEN -> CLOSED state lifecycle."""
    breaker = InferenceCircuitBreaker(
        failure_threshold=3,
        recovery_cooldown_sec=0.1,  # Short cooldown for test
        half_open_success_threshold=1,
    )

    # Initial state is CLOSED
    assert breaker.state == CircuitState.CLOSED
    assert breaker.can_execute() is True

    # 1st and 2nd failure do not trip the breaker
    breaker.record_failure(ValueError("Error 1"))
    assert breaker.state == CircuitState.CLOSED
    assert breaker.can_execute() is True

    breaker.record_failure(ValueError("Error 2"))
    assert breaker.state == CircuitState.CLOSED
    assert breaker.can_execute() is True

    # 3rd consecutive failure trips breaker to OPEN
    breaker.record_failure(ValueError("Error 3"))
    assert breaker.state == CircuitState.OPEN
    assert breaker.can_execute() is False

    # During cooldown, execution is rejected
    await asyncio.sleep(0.02)
    assert breaker.can_execute() is False

    # After cooldown expires, can_execute() transitions to HALF_OPEN
    await asyncio.sleep(0.12)
    assert breaker.can_execute() is True
    assert breaker.state == CircuitState.HALF_OPEN

    # In HALF_OPEN, failure immediately returns breaker to OPEN
    breaker.record_failure(ValueError("Half-open failure"))
    assert breaker.state == CircuitState.OPEN
    assert breaker.can_execute() is False

    # Wait for cooldown again
    await asyncio.sleep(0.12)
    assert breaker.can_execute() is True
    assert breaker.state == CircuitState.HALF_OPEN

    # In HALF_OPEN, success restores breaker to CLOSED
    breaker.record_success()
    assert breaker.state == CircuitState.CLOSED
    assert breaker.can_execute() is True


@pytest.mark.asyncio
async def test_inference_timeout_watchdog_enforcement():
    """Verifies that an inference call exceeding inference_timeout_sec trips TimeoutError and registers failure."""
    cam_id = "CAM-TIMEOUT-WATCHDOG"
    breaker = camera_worker._get_circuit_breaker(cam_id)
    breaker.state = CircuitState.CLOSED
    breaker.consecutive_failures = 0

    fake_cam = Camera(
        camera_id=cam_id,
        ip_address="192.168.1.100",
        rtsp_path="/live",
        label="Watchdog Test Cam",
        status="ONLINE",
    )

    # Simulate a hanging inference service (e.g. frozen ONNX runtime / GPU memory stall)
    def slow_inference(*args, **kwargs):
        time.sleep(0.5)
        return MagicMock(), b""

    # Temporarily set timeout to 0.1s
    original_timeout = settings.detection.inference_timeout_sec
    settings.detection.inference_timeout_sec = 0.1
    try:
        with patch("src.ml.level1_detection.vision_service.VisionInferenceService.analyze_frame_bytes", side_effect=slow_inference):
            with pytest.raises((asyncio.TimeoutError, TimeoutError)):
                await camera_worker._run_vision_and_face_inference(
                    cam=fake_cam,
                    frame_bytes=b"dummy_bytes",
                    catalog=[],
                    roster=[],
                )

        # The circuit breaker for this camera must have registered the failure
        assert breaker.consecutive_failures == 1
    finally:
        settings.detection.inference_timeout_sec = original_timeout


@pytest.mark.asyncio
async def test_circuit_breaker_open_blocks_execution():
    """Verifies that when circuit breaker is OPEN, execution is immediately blocked without running inference."""
    cam_id = "CAM-BREAKER-OPEN"
    breaker = camera_worker._get_circuit_breaker(cam_id)
    breaker.state = CircuitState.OPEN
    breaker.recovery_cooldown_sec = 60.0  # long cooldown
    breaker.last_state_change = time.time()

    fake_cam = Camera(
        camera_id=cam_id,
        ip_address="192.168.1.101",
        rtsp_path="/live",
        label="Breaker Test Cam",
        status="ONLINE",
    )

    # _run_vision_and_face_inference must raise CircuitBreakerOpenException immediately
    with pytest.raises(CircuitBreakerOpenException) as exc_info:
        await camera_worker._run_vision_and_face_inference(
            cam=fake_cam,
            frame_bytes=b"dummy_bytes",
            catalog=[],
            roster=[],
        )
    assert "circuit breaker is OPEN" in str(exc_info.value)


@pytest.mark.asyncio
async def test_poll_single_camera_degradation_telemetry():
    """Verifies that CircuitBreakerOpenException and TimeoutError transition camera to DEGRADED with explicit telemetry."""
    cam_id = "CAM-DEGRADED-TELEMETRY"
    fake_cam = Camera(
        camera_id=cam_id,
        ip_address="192.168.1.102",
        rtsp_path="/live",
        label="Degraded Telemetry Cam",
        status="ONLINE",
        added_at=get_utc_now(),
    )

    # 1. Test CircuitBreakerOpenException propagation
    with patch.object(camera_worker, "_capture_camera_frame", return_value=b"\xff\xd8\xff\xe0dummy_jpeg"):
        with patch.object(
            camera_worker,
            "_run_vision_and_face_inference",
            side_effect=CircuitBreakerOpenException("Circuit breaker is OPEN for camera"),
        ):
            async with AsyncSessionLocal() as session:
                await camera_worker.poll_single_camera(fake_cam, session)

            assert fake_cam.status == "DEGRADED"
            latest_det = camera_worker.get_latest_detection(cam_id)
            assert latest_det["operationalStatus"] == "MODEL_UNAVAILABLE"
            assert latest_det["circuitBreaker"] == "OPEN"

    # 2. Test TimeoutError propagation
    with patch.object(camera_worker, "_capture_camera_frame", return_value=b"\xff\xd8\xff\xe0dummy_jpeg"):
        with patch.object(
            camera_worker,
            "_run_vision_and_face_inference",
            side_effect=asyncio.TimeoutError("Inference timed out"),
        ):
            async with AsyncSessionLocal() as session:
                await camera_worker.poll_single_camera(fake_cam, session)

            assert fake_cam.status == "DEGRADED"
            latest_det = camera_worker.get_latest_detection(cam_id)
            assert latest_det["operationalStatus"] == "INFERENCE_TIMEOUT"


@pytest.mark.asyncio
async def test_multi_camera_transaction_isolation():
    """F2: Verifies that a database crash or rollback on Camera 1 does NOT contaminate or roll back Camera 2."""
    cam1_id = "CAM-ISO-CRASH-1"
    cam2_id = "CAM-ISO-HEALTHY-2"

    async with AsyncSessionLocal() as session:
        # Clean up any remnants
        res = await session.execute(select(Camera).where(Camera.camera_id.in_([cam1_id, cam2_id])))
        for c in res.scalars().all():
            await session.delete(c)
        await session.commit()

        # Seed two test cameras
        c1 = Camera(
            camera_id=cam1_id,
            ip_address="192.168.1.201",
            rtsp_path="/live",
            label="Crashing Cam",
            status="ONLINE",
            added_at=get_utc_now(),
        )
        c2 = Camera(
            camera_id=cam2_id,
            ip_address="192.168.1.202",
            rtsp_path="/live",
            label="Healthy Cam",
            status="ONLINE",
            added_at=get_utc_now(),
        )
        session.add_all([c1, c2])
        await session.commit()

    # Track invocations
    processed_cameras = []

    async def mock_poll_single(cam, session):
        processed_cameras.append(cam.camera_id)
        if cam.camera_id == cam1_id:
            # Simulate an unhandled database / engine error on camera 1
            raise RuntimeError("Simulated DB lock or commit crash on Camera 1")
        # Camera 2 succeeds and modifies its camera record in its isolated session
        cam.status = "ONLINE"
        cam.label = "Healthy Cam Updated"

    camera_worker.is_running = True
    try:
        with patch.object(camera_worker, "poll_single_camera", side_effect=mock_poll_single):
            # Run batch polling across all cameras
            await camera_worker.poll_all_cameras()

        # Both cameras were attempted
        assert cam1_id in processed_cameras
        assert cam2_id in processed_cameras

        # Verify Camera 2 committed successfully despite Camera 1 failing
        async with AsyncSessionLocal() as session:
            c2_db = await session.get(Camera, cam2_id)
            assert c2_db is not None
            assert c2_db.label == "Healthy Cam Updated"

    finally:
        camera_worker.is_running = False
        # Clean up
        async with AsyncSessionLocal() as session:
            res = await session.execute(select(Camera).where(Camera.camera_id.in_([cam1_id, cam2_id])))
            for c in res.scalars().all():
                await session.delete(c)
            await session.commit()
