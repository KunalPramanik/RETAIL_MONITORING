"""Automated Verification of Zero-Fake-Data & Zero-Simulation Policy

Validates that:
1. No synthetic bounding boxes or detections are fabricated when no frame is provided.
2. Blank camera frames produce exactly 0 detections and 0.0 confidence (never default 0.95 or 98.6%).
3. Deskewed manifest parsing on blank frames never invents carriers ("Rajesh Kumar") or fake items.
4. Hardware interlocks report offline/failure when disconnected, never simulating success in production.
5. Simulation endpoints (/api/discovery/simulate and /api/ingest/scenario) are strictly blocked in production.
"""

import pytest
import numpy as np
import cv2
from httpx import AsyncClient

from src.ml.level1_detection.vision_service import VisionInferenceService
from src.engine.manifest_ingestion_daemon import DeskManifestScanner
from src.engine.hardware_interlock import AsyncModbusTCPDriver
from src.core.config import settings


def test_empty_frame_produces_zero_fake_detections():
    """Ensures blank frames produce NO_DETECTION with 0.0 confidence and 0.0 tracking accuracy."""
    blank_bgr = np.zeros((480, 640, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".jpg", blank_bgr)
    frame_bytes = encoded.tobytes()

    result, _ = VisionInferenceService.analyze_frame_bytes(frame_bytes=frame_bytes)
    assert result.vision_count == 0
    assert result.cases_detected == 0
    assert result.singles_detected == 0
    assert result.vision_confidence == 0.0
    assert len(result.detections) == 0
    assert result.tracking_accuracy_pct == 0.0


def test_process_frame_batch_refuses_to_fabricate_detections():
    """Ensures process_frame_batch refuses to fabricate bounding boxes without physical frames."""
    line_items = [
        {"product_id": "PROD-1", "sku_code": "SKU-BEV-100", "cases_qty": 4, "singles_qty": 2, "pack_size": 24}
    ]
    result = VisionInferenceService.process_frame_batch(line_items)
    assert result.vision_count == 0
    assert result.vision_confidence == 0.0
    assert len(result.detections) == 0
    assert result.tracking_accuracy_pct == 0.0


def test_manifest_parser_never_hallucinates_on_blank_frame():
    """Ensures manifest parsing on blank/featureless images returns unparsed document, never fake text."""
    blank_bgr = np.zeros((600, 800, 3), dtype=np.uint8)
    manifest = DeskManifestScanner.process_desk_frame(blank_bgr)

    assert manifest.carrier_name is None
    assert manifest.bol_number == "UNKNOWN"
    assert len(manifest.line_items) == 0
    assert manifest.confidence == 0.0
    assert "Rajesh Kumar" not in manifest.raw_text
    assert "CEMENT_BAG" not in manifest.raw_text


@pytest.mark.anyio
async def test_hardware_interlock_reports_offline_in_production(monkeypatch):
    """Ensures hardware interlock does not claim connection or relay success when PLC is unreachable."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "SECOPS_DEBUG", False)

    driver = AsyncModbusTCPDriver(host="192.0.2.1", port=502, timeout_ms=50.0)
    connected = await driver.connect()
    assert connected is False
    assert driver._is_connected is False

    coil_written = await driver.write_coil(0, True)
    assert coil_written is False


@pytest.mark.anyio
async def test_discovery_simulate_endpoint_blocked_in_production(async_client: AsyncClient, monkeypatch):
    """Ensures /api/discovery/simulate returns HTTP 403 when running in production."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "SECOPS_DEBUG", False)

    resp = await async_client.post(
        "/api/discovery/simulate",
        json={"deviceType": "CAMERA"},
        headers={"X-User-Role": "ADMIN"},
    )
    assert resp.status_code == 403
    assert "forbidden in production mode" in resp.json()["detail"]


@pytest.mark.anyio
async def test_ingest_scenario_endpoint_blocked_in_production(async_client: AsyncClient, monkeypatch):
    """Ensures /api/ingest/scenario returns HTTP 403 when running in production."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "SECOPS_DEBUG", False)

    resp = await async_client.post(
        "/api/ingest/scenario",
        headers={"X-User-Role": "ADMIN"},
    )
    assert resp.status_code == 403
    assert "forbidden in production mode" in resp.json()["detail"]
