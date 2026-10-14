"""Eight-Partition Snapshot Storage & Evidence Traceability Service

Enforces Section 8 of the SEC-OPS V8 Master Prompt & User Revisions:
- Eight explicit partition categories:
  1. LIVE_FRAMES
  2. PERSON_DETECTIONS
  3. OBJECT_CLASSIFICATIONS
  4. ENTRY_EXIT_LOGS
  5. MATERIAL_TRANSFERS
  6. BASELINE_INVENTORIES
  7. ALERT_RECORDS
  8. BILL_DOCUMENT
- Strict evidence rule: Live and person snapshots must NEVER be recorded as material evidence or attached to invoice transactions.
- Cryptographic SHA-256 integrity hash on all stored snapshots.
- Exact binding: Every snapshot links to exact camera_id, event_id, and movement_id.
"""

import os
import cv2
import uuid
import hashlib
import logging
import numpy as np
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone

logger = logging.getLogger("secops.snapshots")

SNAPSHOTS_ROOT = os.getenv("SNAPSHOTS_DIR", "snapshots")

PARTITIONS = {
    "LIVE_FRAMES": "live_frames",
    "PERSON_DETECTIONS": "person_detections",
    "OBJECT_CLASSIFICATIONS": "object_classifications",
    "ENTRY_EXIT_LOGS": "entry_exit_logs",
    "MATERIAL_TRANSFERS": "material_transfers",
    "BASELINE_INVENTORIES": "baseline_inventories",
    "ALERT_RECORDS": "alert_records",
    "BILL_DOCUMENT": "bill_documents",
}

# Categories strictly prohibited from being used as physical material evidence
PROHIBITED_FOR_MATERIAL_EVIDENCE = {"LIVE_FRAMES", "PERSON_DETECTIONS"}


class SnapshotArchiveService:
    """Manages verified 8-partition snapshot persistence and strict evidence binding."""

    @classmethod
    def get_partition_dir(cls, category: str) -> str:
        """Resolves folder path for category, ensuring directory exists."""
        cat_key = category.strip().upper()
        if cat_key not in PARTITIONS:
            raise ValueError(f"Invalid snapshot category '{category}'. Must be one of {list(PARTITIONS.keys())}")
        folder = os.path.join(SNAPSHOTS_ROOT, PARTITIONS[cat_key])
        os.makedirs(folder, exist_ok=True)
        return folder

    @classmethod
    def validate_evidence_policy(cls, category: str, purpose: str = "MATERIAL_EVIDENCE") -> None:
        """Guarantees live or person snapshots are never attached as material movement or billing evidence."""
        cat_key = category.strip().upper()
        if purpose in ("MATERIAL_EVIDENCE", "INVOICE_ATTACHMENT", "MATERIAL_MOVEMENT"):
            if cat_key in PROHIBITED_FOR_MATERIAL_EVIDENCE:
                raise ValueError(
                    f"STRICT EVIDENCE VIOLATION: '{cat_key}' snapshots cannot be used as {purpose}."
                )

    @classmethod
    def save_partitioned_snapshot(
        cls,
        category: str,
        image: np.ndarray,
        camera_id: str,
        event_id: Optional[str] = None,
        movement_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Saves an image into its designated partition with cryptographic SHA-256 checksum."""
        cat_key = category.strip().upper()
        target_dir = cls.get_partition_dir(cat_key)

        # Encode image to JPEG
        success, buffer = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        if not success:
            raise RuntimeError("Failed to encode frame to JPEG for snapshot archive.")

        img_bytes = buffer.tobytes()
        sha256_hash = hashlib.sha256(img_bytes).hexdigest()

        # Generate unique, collision-free filename
        date_prefix = datetime.now(timezone.utc).strftime("%Y%m%d")
        snap_id = f"SNAP-{date_prefix}-{uuid.uuid4().hex[:10]}"
        clean_cam = camera_id.replace(":", "_").replace("/", "_").replace("\\", "_")
        filename = f"{clean_cam}_{snap_id}.jpg"
        file_path = os.path.join(target_dir, filename)

        with open(file_path, "wb") as f:
            f.write(img_bytes)

        rel_url = f"/snapshots/{PARTITIONS[cat_key]}/{filename}"
        logger.debug("Archived snapshot %s under %s (hash: %s...)", filename, cat_key, sha256_hash[:8])

        return {
            "snapshotId": snap_id,
            "category": cat_key,
            "partition": PARTITIONS[cat_key],
            "url": rel_url,
            "filePath": file_path,
            "sha256": sha256_hash,
            "cameraId": camera_id,
            "eventId": event_id,
            "movementId": movement_id,
            "capturedAt": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }
