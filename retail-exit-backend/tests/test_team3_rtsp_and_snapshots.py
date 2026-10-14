"""Team 3 — RTSP Ingestion, Stream Resilience & 8-Partition Snapshot Storage Test Suite

Validates:
1. Eight explicit partition categories including BILL_DOCUMENT.
2. Cryptographic SHA-256 integrity on saved snapshots.
3. Strict Evidence Rule: LIVE_FRAMES and PERSON_DETECTIONS prohibited as material evidence.
4. MATERIAL_TRANSFERS and BILL_DOCUMENT permitted for material and billing evidence.
5. Exact binding to camera_id, event_id, and movement_id.
"""

import os
import cv2
import pytest
import numpy as np
import hashlib

from src.services.snapshot_archive_service import SnapshotArchiveService, PARTITIONS


def test_all_eight_partitions_supported():
    """Verify all 8 partition categories are present and valid."""
    expected_categories = {
        "LIVE_FRAMES",
        "PERSON_DETECTIONS",
        "OBJECT_CLASSIFICATIONS",
        "ENTRY_EXIT_LOGS",
        "MATERIAL_TRANSFERS",
        "BASELINE_INVENTORIES",
        "ALERT_RECORDS",
        "BILL_DOCUMENT",
    }
    assert set(PARTITIONS.keys()) == expected_categories


def test_save_and_verify_partitioned_snapshot(tmp_path, monkeypatch):
    """Verify saving snapshot into partition calculates SHA-256 and records exact event binding."""
    monkeypatch.setattr("src.services.snapshot_archive_service.SNAPSHOTS_ROOT", str(tmp_path))

    # Create synthetic test frame
    test_img = np.zeros((100, 100, 3), dtype=np.uint8)
    cv2.rectangle(test_img, (10, 10), (90, 90), (0, 255, 0), -1)

    # Save under BILL_DOCUMENT
    snap = SnapshotArchiveService.save_partitioned_snapshot(
        category="BILL_DOCUMENT",
        image=test_img,
        camera_id="CAM-SCANNER-01",
        event_id="EVT-20261014-001",
        movement_id="MOV-20261014-001",
    )

    assert snap["category"] == "BILL_DOCUMENT"
    assert snap["partition"] == "bill_documents"
    assert snap["cameraId"] == "CAM-SCANNER-01"
    assert snap["eventId"] == "EVT-20261014-001"
    assert snap["movementId"] == "MOV-20261014-001"
    assert os.path.exists(snap["filePath"])

    # Verify SHA-256 checksum
    with open(snap["filePath"], "rb") as f:
        data = f.read()
        expected_hash = hashlib.sha256(data).hexdigest()
    assert snap["sha256"] == expected_hash


def test_strict_evidence_rule_prohibits_person_and_live_frames():
    """Verify person detections and live frames CANNOT be used as material movement evidence."""
    # Attempting to use PERSON_DETECTIONS as material evidence must fail
    with pytest.raises(ValueError) as exc1:
        SnapshotArchiveService.validate_evidence_policy("PERSON_DETECTIONS", purpose="MATERIAL_EVIDENCE")
    assert "STRICT EVIDENCE VIOLATION" in str(exc1.value)

    # Attempting to use LIVE_FRAMES as invoice attachment must fail
    with pytest.raises(ValueError) as exc2:
        SnapshotArchiveService.validate_evidence_policy("LIVE_FRAMES", purpose="INVOICE_ATTACHMENT")
    assert "STRICT EVIDENCE VIOLATION" in str(exc2.value)

    # MATERIAL_TRANSFERS must be permitted without exception
    SnapshotArchiveService.validate_evidence_policy("MATERIAL_TRANSFERS", purpose="MATERIAL_EVIDENCE")

    # BILL_DOCUMENT must be permitted without exception
    SnapshotArchiveService.validate_evidence_policy("BILL_DOCUMENT", purpose="INVOICE_ATTACHMENT")
