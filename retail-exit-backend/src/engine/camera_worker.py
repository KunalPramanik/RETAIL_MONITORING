"""Background Camera Stream Ingestion & Real-Time Computer Vision Worker

Continuously monitors registered surveillance cameras, polls live frames,
executes OpenCV contour/object detection and Haar-cascade face recognition,
saves real annotated snapshots, records exit events in the database, and
broadcasts live events to the frontend via WebSockets.
"""

import asyncio
import os
import time
import random
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import httpx
import cv2
import numpy as np
from sqlalchemy import select, and_

from src.db.session import AsyncSessionLocal
from src.db.models import (
    Camera,
    Lane,
    ExitEvent,
    ExitEventLineItem,
    VisionDetection,
    FaceMatchAttempt,
    Alert,
    Employee,
    Product,
    ThresholdConfig,
    get_utc_now,
)
from src.ml.vision_service import VisionInferenceService
from src.ml.face_service import FaceRecognitionService
from src.engine.fusion import MultiSensorFusionEngine
from src.engine.verdict import VerdictEngine
from src.realtime.hub import ws_hub

logger = logging.getLogger("secops.camera_worker")


class CameraIngestionWorker:
    """Orchestrates live frame polling, object/face inference, and event generation."""

    def __init__(self, poll_interval_sec: float = 3.0):
        self.poll_interval_sec = poll_interval_sec
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self._last_frames: Dict[str, np.ndarray] = {}
        self._last_event_time: Dict[str, float] = {}
        self._last_detections: Dict[str, Dict[str, Any]] = {}

    def start(self):
        """Starts the background camera ingestion worker."""
        if not self.is_running:
            self.is_running = True
            self._task = asyncio.create_task(self._run_loop())
            logger.info("CameraIngestionWorker started (poll interval: %.1fs).", self.poll_interval_sec)

    async def stop(self):
        """Stops the background camera ingestion worker and awaits task completion."""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.debug("Error awaiting camera worker cancellation: %s", e)
            self._task = None
        logger.info("CameraIngestionWorker stopped.")

    async def _run_loop(self):
        """Continuous polling loop across all active cameras."""
        while self.is_running:
            try:
                await self.poll_all_cameras()
                await asyncio.sleep(self.poll_interval_sec)
            except asyncio.CancelledError:
                break
            except Exception as e:
                if not self.is_running:
                    break
                err_msg = str(e).lower()
                if "no active connection" in err_msg or "closed" in err_msg:
                    break
                logger.error("Unexpected error in CameraIngestionWorker loop: %s", e, exc_info=True)
                try:
                    await asyncio.sleep(self.poll_interval_sec)
                except asyncio.CancelledError:
                    break

    async def poll_all_cameras(self):
        """Polls frames from each registered camera."""
        if not self.is_running:
            return
        try:
            async with AsyncSessionLocal() as session:
                stmt = select(Camera).where(
                    and_(
                        Camera.removed_at.is_(None),
                        Camera.status.in_(["ONLINE", "PENDING_SETUP", "OFFLINE"]),
                    )
                )
                res = await session.execute(stmt)
                cameras = res.scalars().all()

                for cam in cameras:
                    if not self.is_running:
                        break
                    await self.poll_single_camera(cam, session)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            if not self.is_running:
                return
            err_msg = str(e).lower()
            if "no active connection" in err_msg or "closed" in err_msg:
                return
            raise

    async def poll_single_camera(self, cam: Camera, session) -> Optional[bytes]:
        """Fetches a frame from the camera, updates heartbeat, and triggers inference on motion."""
        ip = cam.ip_address
        if not ip:
            return None

        # Attempt frame capture via RTSP stream or HTTP endpoints
        from src.api.cameras import capture_camera_frame_sync

        frame_bytes, source_desc, latency_ms = await asyncio.to_thread(
            capture_camera_frame_sync,
            str(cam.ip_address),
            str(cam.rtsp_path or ""),
            str(cam.credentials_ref or ""),
            str(cam.sub_stream_path or ""),
            2.0,
            str(cam.stream_url or "") if cam.stream_url else None,
        )

        if not frame_bytes:
            return None

        # Update camera heartbeat and status to ONLINE
        now = get_utc_now()
        cam.last_heartbeat_at = now
        cam.status = "ONLINE"
        cam.offline_since = None

        # Real-Time CV & Biometric Detection for Live Preview
        annotated_bytes = frame_bytes
        detection_data = {
            "cameraId": cam.camera_id,
            "laneId": cam.lane_id,
            "casesDetected": 0,
            "unitsDetected": 0,
            "carrierName": "UNVERIFIED",
            "faceDecision": "NO_MATCH",
            "confidence": 95.0,
            "boxesCount": 0,
            "timestamp": now.isoformat(),
        }

        try:
            prod_res = await session.execute(select(Product))
            products = prod_res.scalars().all()
            catalog = [
                {"product_id": p.product_id, "sku_code": p.sku_code, "pack_size": p.pack_size}
                for p in products
            ]
            emp_res = await session.execute(select(Employee).where(Employee.active_flag == True))
            employees = emp_res.scalars().all()
            roster = [
                {"employee_id": e.employee_id, "name": e.name, "face_embedding": e.face_embedding}
                for e in employees
            ]

            vis_res, obj_bytes = VisionInferenceService.analyze_frame_bytes(frame_bytes, catalog_products=catalog)
            face_res, final_bytes, face_boxes = FaceRecognitionService.detect_and_match_faces(
                frame_bytes=obj_bytes or frame_bytes,
                enrolled_employees=roster,
                prior_detections_count=len(vis_res.detections),
                cases_detected=vis_res.cases_detected,
                units_detected=vis_res.vision_count,
                raw_frame_bytes=frame_bytes,
            )
            annotated_bytes = final_bytes or obj_bytes or frame_bytes

            carrier_label = face_res.employee_name if face_res.matched_employee_id else "UNVERIFIED"
            detection_data.update({
                "casesDetected": vis_res.cases_detected,
                "unitsDetected": vis_res.vision_count,
                "carrierName": carrier_label,
                "faceDecision": face_res.decision,
                "confidence": round(vis_res.vision_confidence * 100, 1) if vis_res.vision_confidence else 95.0,
                "boxesCount": len(vis_res.detections) + len(face_boxes),
            })
        except Exception as e:
            logger.warning("Preview CV annotation error on %s: %s", cam.camera_id, e)

        self._last_detections[cam.camera_id] = detection_data

        os.makedirs("snapshots", exist_ok=True)
        preview_path = os.path.join("snapshots", f"preview_{cam.camera_id}.jpg")
        try:
            with open(preview_path, "wb") as f:
                f.write(annotated_bytes)
        except Exception as e:
            logger.warning("Could not write preview snapshot: %s", e)

        await session.commit()

        # Motion detection to automatically generate exit events
        should_trigger = self._check_motion(cam.camera_id, frame_bytes)
        if should_trigger:
            await self.process_camera_frame(
                cam=cam,
                frame_bytes=frame_bytes,
                session=session,
                trigger_reason="MOTION_TRAVERSAL",
            )

        return annotated_bytes

    def get_latest_detection(self, camera_id: str) -> Dict[str, Any]:
        """Returns the latest real-time CV detection metadata for the given camera."""
        return self._last_detections.get(camera_id, {
            "cameraId": camera_id,
            "casesDetected": 0,
            "unitsDetected": 0,
            "carrierName": "UNVERIFIED",
            "faceDecision": "NO_MATCH",
            "confidence": 95.0,
            "boxesCount": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def _check_motion(self, camera_id: str, frame_bytes: bytes) -> bool:
        """Determines if significant motion / traversal occurred between consecutive frames."""
        try:
            nparr = np.frombuffer(frame_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return False

            small = cv2.resize(img, (320, 180))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)

            prev = self._last_frames.get(camera_id)
            self._last_frames[camera_id] = gray

            if prev is None:
                return False

            delta = cv2.absdiff(prev, gray)
            thresh = cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)[1]
            motion_pixels = cv2.countNonZero(thresh)

            # Throttle events to at most once per 6 seconds per camera
            now_ts = time.time()
            last_event = self._last_event_time.get(camera_id, 0)
            if motion_pixels > 3500 and (now_ts - last_event) > 6.0:
                self._last_event_time[camera_id] = now_ts
                logger.info("Significant motion detected on %s (%d px). Triggering exit event.", camera_id, motion_pixels)
                return True
        except Exception as e:
            logger.warning("Motion check error on %s: %s", camera_id, e)

        return False

    async def process_camera_frame(
        self,
        cam: Camera,
        frame_bytes: bytes,
        session,
        trigger_reason: str = "MANUAL_SCAN",
    ) -> ExitEvent:
        """Runs full computer vision + face recognition + fusion pipeline and commits event to DB."""
        now = get_utc_now()
        event_num = random.randint(1000, 9999)
        event_id = f"EVT-2026-{event_num}"
        lane_id = cam.lane_id or "UNASSIGNED"

        # 1. Fetch Products & Active Employees
        prod_res = await session.execute(select(Product))
        products = prod_res.scalars().all()
        catalog = [
            {"product_id": p.product_id, "sku_code": p.sku_code, "pack_size": p.pack_size}
            for p in products
        ]

        emp_res = await session.execute(select(Employee).where(Employee.active_flag == True))
        employees = emp_res.scalars().all()
        roster = [
            {"employee_id": e.employee_id, "name": e.name, "face_embedding": e.face_embedding}
            for e in employees
        ]

        # 2. Run Real OpenCV Object Detection
        vision_result, annotated_bytes = VisionInferenceService.analyze_frame_bytes(
            frame_bytes=frame_bytes,
            catalog_products=catalog,
        )

        # 3. Run Real OpenCV Face Recognition on the annotated frame
        face_result, final_annotated_bytes, face_boxes = FaceRecognitionService.detect_and_match_faces(
            frame_bytes=annotated_bytes,
            enrolled_employees=roster,
            prior_detections_count=len(vision_result.detections),
            cases_detected=vision_result.cases_detected,
            units_detected=vision_result.vision_count,
            raw_frame_bytes=frame_bytes,
        )

        # 4. Multi-Sensor Consensus Fusion (Degrades cleanly to Vision count when RFID/Scale absent)
        fusion_result = MultiSensorFusionEngine.fuse(
            vision_count=vision_result.vision_count,
            vision_confidence=vision_result.vision_confidence,
            rfid_count=None,
            weight_estimated_units=None,
        )

        # 5. Deterministic Verdict Evaluation
        declared_units = fusion_result.consensus_units
        threshold_res = await session.execute(select(ThresholdConfig).limit(1))
        threshold_cfg = threshold_res.scalar_one_or_none()

        verdict_result = VerdictEngine.evaluate(
            consensus_units=fusion_result.consensus_units,
            declared_units=declared_units,
            unit_tolerance=threshold_cfg.unit_tolerance if threshold_cfg else 0,
            pct_tolerance=threshold_cfg.pct_tolerance if threshold_cfg else 0.0,
            low_severity_threshold=threshold_cfg.low_severity_threshold if threshold_cfg else 1,
            med_severity_threshold=threshold_cfg.med_severity_threshold if threshold_cfg else 3,
            high_severity_threshold=threshold_cfg.high_severity_threshold if threshold_cfg else 6,
        )

        # 6. Save REAL Annotated Snapshot Image
        os.makedirs("snapshots", exist_ok=True)
        snapshot_filename = f"{lane_id.lower()}_{event_id}.jpg"
        snapshot_filepath = os.path.join("snapshots", snapshot_filename)
        save_bytes = final_annotated_bytes or annotated_bytes or frame_bytes
        try:
            with open(snapshot_filepath, "wb") as f:
                f.write(save_bytes)
        except Exception as e:
            logger.error("Failed to save event snapshot: %s", e)

        snapshot_url = f"/snapshots/{snapshot_filename}"

        # 7. Write ExitEvent Row
        event = ExitEvent(
            event_id=event_id,
            ts=now,
            lane_id=lane_id,
            employee_id=face_result.matched_employee_id,
            employee_match_confidence=face_result.similarity if face_result.matched_employee_id else None,
            cases_detected=vision_result.cases_detected,
            units_detected=vision_result.vision_count,
            vision_count=vision_result.vision_count,
            vision_confidence=vision_result.vision_confidence,
            rfid_count=None,
            weight_kg=0.0,
            weight_estimated_units=None,
            consensus_units=fusion_result.consensus_units,
            consensus_method=fusion_result.consensus_method,
            invoice_id=None,
            declared_units=declared_units,
            delta_units=verdict_result.delta_units,
            verdict=verdict_result.verdict,
            severity=verdict_result.severity,
            snapshot_url=snapshot_url,
            notes=f"Trigger: {trigger_reason}. {verdict_result.reason}. Face: {face_result.decision}.",
        )
        session.add(event)
        await session.flush()

        # 8. Record Real Vision Detections
        for d in vision_result.detections:
            det = VisionDetection(
                event_id=event_id,
                camera_id=cam.camera_id,
                frame_ts=now,
                model_version=vision_result.model_version,
                class_label=d.class_label,
                confidence=d.confidence,
                bbox=d.bbox,
                product_id=d.product_id,
            )
            session.add(det)

        # 9. Record Real Face Match Attempt
        face_attempt = FaceMatchAttempt(
            event_id=event_id,
            matched_employee_id=face_result.matched_employee_id,
            similarity=round(face_result.similarity, 4),
            model_version=face_result.model_version,
            decision=face_result.decision,
            created_at=now,
        )
        session.add(face_attempt)

        # 10. Record Alert if Discrepancy
        alert_payload = None
        if verdict_result.severity in ("MEDIUM", "HIGH"):
            alert_type = "OVER_CARRY" if verdict_result.delta_units > 0 else (
                "UNDER_DECLARE" if verdict_result.delta_units < 0 else "SENSOR_DISAGREEMENT"
            )
            alert = Alert(
                alert_id=f"ALT-2026-{random.randint(1000, 9999)}",
                camera_id=cam.camera_id,
                event_id=event_id,
                alert_type=alert_type,
                severity=verdict_result.severity if verdict_result.severity in ("LOW", "MEDIUM", "HIGH") else "MEDIUM",
                delta_units=verdict_result.delta_units,
                status="OPEN",
                created_at=now,
            )
            session.add(alert)
            await session.flush()
            alert_payload = {
                "alertId": alert.alert_id,
                "laneId": lane_id,
                "cameraId": alert.camera_id,
                "eventId": alert.event_id,
                "severity": alert.severity,
                "alertType": alert.alert_type,
                "status": alert.status,
                "deltaUnits": alert.delta_units,
                "createdAt": alert.created_at.isoformat(),
            }

        await session.commit()

        # 11. Broadcast over WebSocket to connected Consoles
        event_payload = {
            "eventId": event.event_id,
            "timestamp": event.ts.isoformat(),
            "laneId": event.lane_id,
            "employeeId": event.employee_id,
            "casesDetected": event.cases_detected,
            "unitsDetected": event.units_detected,
            "visionCount": event.vision_count,
            "rfidCount": event.rfid_count,
            "weightKg": event.weight_kg,
            "consensusUnits": event.consensus_units,
            "consensusMethod": event.consensus_method,
            "invoiceId": event.invoice_id,
            "declaredUnits": event.declared_units,
            "deltaUnits": event.delta_units,
            "verdict": event.verdict,
            "severity": event.severity,
            "snapshotUrl": event.snapshot_url,
            "notes": event.notes,
            "lineItems": [],
        }
        await ws_hub.broadcast_event("new_event", event_payload)
        if alert_payload:
            await ws_hub.broadcast_event("new_alert", alert_payload)

        logger.info("Created real ExitEvent %s on %s (Units: %d, Verdict: %s)", event_id, lane_id, event.units_detected, event.verdict)
        return event


# Global worker singleton
camera_worker = CameraIngestionWorker(poll_interval_sec=3.0)

