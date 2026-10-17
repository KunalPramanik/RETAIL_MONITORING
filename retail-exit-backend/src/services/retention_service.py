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
    protected_basenames: Optional[set[str]] = None,
) -> Dict[str, Any]:
    """Scans snapshot directory and unlinks image files older than max_age_days.
    
    Protects snapshots linked to open Alert records or ExitEvent.legal_hold == True.
    Database records and ledger entries remain intact.
    """
    if not os.path.exists(snapshot_dir):
        return {"scanned": 0, "purged": 0, "protected": 0, "bytesReclaimed": 0, "status": "DIRECTORY_NOT_FOUND"}

    cutoff_epoch = time.time() - (max_age_days * 86400.0)
    scanned_count = 0
    purged_count = 0
    protected_count = 0
    bytes_reclaimed = 0
    errors = []

    clean_protected = {os.path.basename(p).strip().lower() for p in (protected_basenames or set()) if p}

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
                        # Check legal hold / active alert exemption
                        if fname.lower() in clean_protected:
                            protected_count += 1
                            logger.info("Preserving snapshot %s under legal hold / active investigation", fname)
                            continue

                        file_sz = stat.st_size
                        os.remove(fpath)
                        purged_count += 1
                        bytes_reclaimed += file_sz
                except Exception as ex:
                    errors.append(f"{fname}: {str(ex)}")

        mb_reclaimed = round(bytes_reclaimed / (1024 * 1024), 2)
        if purged_count > 0:
            logger.info(
                "Snapshot retention purge complete: %d expired image(s) purged, %d protected, %.2f MB reclaimed (cutoff: %d days).",
                purged_count,
                protected_count,
                mb_reclaimed,
                max_age_days,
            )
        else:
            logger.debug(
                "Snapshot retention check: %d file(s) scanned, 0 expired, %d protected (retention window: %d days).",
                scanned_count,
                protected_count,
                max_age_days,
            )

        return {
            "status": "SUCCESS",
            "scanned": scanned_count,
            "purged": purged_count,
            "protected": protected_count,
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
            "protected": protected_count,
            "bytesReclaimed": bytes_reclaimed,
        }


async def get_protected_snapshot_urls(session) -> set[str]:
    """Retrieves basenames of snapshots that MUST be preserved during retention purges.
    
    Protected sources:
    1. ExitEvent records with legal_hold == True
    2. ExitEvent records linked to open or acknowledged Alert records (status != 'RESOLVED')
    3. Quarantined MaterialDefectEvent records
    """
    from sqlalchemy import select
    protected: set[str] = set()
    try:
        from src.db.models import ExitEvent, Alert, MaterialDefectEvent

        # 1. ExitEvents with active legal hold
        stmt_legal = select(ExitEvent.snapshot_url).where(
            (ExitEvent.legal_hold == True) & (ExitEvent.snapshot_url.isnot(None))
        )
        res_legal = await session.execute(stmt_legal)
        for url in res_legal.scalars().all():
            if url:
                protected.add(os.path.basename(str(url)).strip().lower())

        # 2. ExitEvents linked to open or acknowledged alerts
        stmt_alerts = (
            select(ExitEvent.snapshot_url)
            .join(Alert, Alert.event_id == ExitEvent.event_id)
            .where((Alert.status != "RESOLVED") & (ExitEvent.snapshot_url.isnot(None)))
        )
        res_alerts = await session.execute(stmt_alerts)
        for url in res_alerts.scalars().all():
            if url:
                protected.add(os.path.basename(str(url)).strip().lower())

        # 3. Quarantined defect evidence
        try:
            stmt_defects = select(MaterialDefectEvent.snapshot_url).where(
                (MaterialDefectEvent.status == "QUARANTINED") & (MaterialDefectEvent.snapshot_url.isnot(None))
            )
            res_defects = await session.execute(stmt_defects)
            for url in res_defects.scalars().all():
                if url:
                    protected.add(os.path.basename(str(url)).strip().lower())
        except Exception:
            pass

    except Exception as query_err:
        logger.warning("Failed querying protected snapshots from database: %s", query_err)

    return protected


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
            protected_files = set()
            try:
                from src.db.session import AsyncSessionLocal
                async with AsyncSessionLocal() as session:
                    protected_files = await get_protected_snapshot_urls(session)
            except Exception as db_err:
                logger.debug("Database protected snapshot discovery skipped: %s", db_err)

            await asyncio.to_thread(purge_expired_snapshots, max_age_days, snapshot_dir, protected_files)
        except asyncio.CancelledError:
            logger.info("Snapshot retention cleanup worker stopped.")
            break
        except Exception as err:
            logger.error("Error in snapshot retention worker cycle: %s", err)

        try:
            await asyncio.sleep(interval_hours * 3600.0)
        except asyncio.CancelledError:
            break

