"""Snapshot Retention & Storage Cleanup Service

Enforces Section 18 of the V8 Master Prompt Addendum:
- 45-day rolling retention policy for on-disk surveillance snapshot images.
- Purges raw and annotated image files older than 45 days (or SNAPSHOT_RETENTION_DAYS).
- Strictly preserves database ledger, audit trail, and ExitEvent metadata intact.
- Runs periodically in the background with safe error handling and reclaimed byte logging.
"""

import os
import time
import logging
import asyncio
from typing import Dict, Any, Optional

logger = logging.getLogger("secops.services.retention")

DEFAULT_RETENTION_DAYS = int(os.getenv("SNAPSHOT_RETENTION_DAYS", "45"))
CLEANUP_INTERVAL_HOURS = float(os.getenv("SNAPSHOT_CLEANUP_INTERVAL_HOURS", "24.0"))
SNAPSHOTS_DIR = os.getenv("SNAPSHOTS_DIR", "snapshots")


def purge_expired_snapshots(
    max_age_days: int = DEFAULT_RETENTION_DAYS,
    snapshot_dir: str = SNAPSHOTS_DIR,
) -> Dict[str, Any]:
    """Scans snapshot directory and unlinks image files older than max_age_days.
    
    Database records and ledger entries remain intact.
    """
    if not os.path.exists(snapshot_dir):
        return {"scanned": 0, "purged": 0, "bytesReclaimed": 0, "status": "DIRECTORY_NOT_FOUND"}

    cutoff_epoch = time.time() - (max_age_days * 86400.0)
    scanned_count = 0
    purged_count = 0
    bytes_reclaimed = 0
    errors = []

    try:
        for root, _, files in os.walk(snapshot_dir):
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in (".jpg", ".jpeg", ".png", ".webp"):
                    continue

                fpath = os.path.join(root, fname)
                scanned_count += 1
                try:
                    stat = os.stat(fpath)
                    # Use mtime (last modified time) for age calculation
                    if stat.st_mtime < cutoff_epoch:
                        file_sz = stat.st_size
                        os.remove(fpath)
                        purged_count += 1
                        bytes_reclaimed += file_sz
                except Exception as ex:
                    errors.append(f"{fname}: {str(ex)}")

        mb_reclaimed = round(bytes_reclaimed / (1024 * 1024), 2)
        if purged_count > 0:
            logger.info(
                "Snapshot retention purge complete: %d expired image(s) purged, %.2f MB reclaimed (cutoff: %d days).",
                purged_count,
                mb_reclaimed,
                max_age_days,
            )
        else:
            logger.debug(
                "Snapshot retention check: %d file(s) scanned, 0 expired (retention window: %d days).",
                scanned_count,
                max_age_days,
            )

        return {
            "status": "SUCCESS",
            "scanned": scanned_count,
            "purged": purged_count,
            "bytesReclaimed": bytes_reclaimed,
            "mbReclaimed": mb_reclaimed,
            "maxAgeDays": max_age_days,
            "errors": errors[:5],
        }
    except Exception as e:
        logger.error("Failed executing snapshot retention purge: %s", e)
        return {
            "status": "ERROR",
            "error": str(e),
            "scanned": scanned_count,
            "purged": purged_count,
            "bytesReclaimed": bytes_reclaimed,
        }


async def periodic_retention_worker(
    max_age_days: int = DEFAULT_RETENTION_DAYS,
    interval_hours: float = CLEANUP_INTERVAL_HOURS,
    snapshot_dir: str = SNAPSHOTS_DIR,
) -> None:
    """Background task executing rolling snapshot retention purges."""
    logger.info(
        "Starting background snapshot retention cleanup worker (policy: %d days, interval: %.1fh).",
        max_age_days,
        interval_hours,
    )
    # Initial pause of 60 seconds on boot to avoid CPU spikes during startup
    await asyncio.sleep(60.0)

    while True:
        try:
            await asyncio.to_thread(purge_expired_snapshots, max_age_days, snapshot_dir)
        except asyncio.CancelledError:
            logger.info("Snapshot retention cleanup worker stopped.")
            break
        except Exception as err:
            logger.error("Error in snapshot retention worker cycle: %s", err)

        try:
            await asyncio.sleep(interval_hours * 3600.0)
        except asyncio.CancelledError:
            break

