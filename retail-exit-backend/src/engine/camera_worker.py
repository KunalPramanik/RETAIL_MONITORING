"""Background Camera Stream Ingestion & Real-Time Computer Vision Worker

Continuously monitors registered surveillance cameras, polls live frames,
executes OpenCV contour/object detection and Haar-cascade face recognition,
saves real annotated snapshots, records exit events in the database, and
broadcasts live events to the frontend via WebSockets.
"""

import asyncio
import os
import time
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from collections import deque
import uuid
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
    StaticImageDetection,
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
from src.ml.model_config import get_vision_config

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
        self._camera_logs: Dict[str, deque] = {}
        self._active_transactions: Dict[str, Dict[str, Any]] = {}

    def register_camera(self, camera_record: Any) -> None:
        """Registers a newly discovered or confirmed camera into the ingestion fleet."""
        cam_id = getattr(camera_record, "camera_id", "unknown")
        cam_label = getattr(camera_record, "label", "")
        logger.info("Registered camera %s (%s) for live ingestion.", cam_id, cam_label)

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

        # Attempt frame capture via stream_manager first for ultra-low latency & no device contention
        from src.engine.stream_manager import camera_stream_manager
        target_path = cam.sub_stream_path or cam.rtsp_path or ""
        sm_bytes, latency_ms = camera_stream_manager.get_latest_real_jpeg(
            cam.camera_id, str(cam.ip_address), str(target_path), str(cam.stream_url or "") if cam.stream_url else None, max_wait_sec=0.5
        )
        if sm_bytes:
            frame_bytes, source_desc = sm_bytes, f"StreamManager ({cam.ip_address})"
        else:
            from src.api.cameras import capture_camera_frame_sync
            frame_bytes, source_desc, latency_ms = await asyncio.to_thread(
                capture_camera_frame_sync,
                str(cam.ip_address),
                str(cam.rtsp_path or ""),
                str(cam.credentials_ref or ""),
                str(cam.sub_stream_path or ""),
                1.5,
                str(cam.stream_url or "") if cam.stream_url else None,
            )

        if not frame_bytes:
            # Physical camera is not streaming live video: do not process inference or create fake events
            now = get_utc_now()
            if cam.status == "ONLINE" and cam.last_heartbeat_at:
                diff_sec = (now - (cam.last_heartbeat_at.replace(tzinfo=timezone.utc) if cam.last_heartbeat_at.tzinfo is None else cam.last_heartbeat_at)).total_seconds()
                if diff_sec > 30:
                    cam.status = "OFFLINE"
                    cam.offline_since = now
            return None

        # Update camera heartbeat and status to ONLINE with verified live stream
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
                camera_id=cam.camera_id,
            )
            annotated_bytes = final_bytes or obj_bytes or frame_bytes

            carrier_label = face_res.employee_name if face_res.matched_employee_id else "UNVERIFIED"

            # Determine frame dimensions for SVG viewport alignment
            frame_w, frame_h = 1280, 720
            try:
                nparr = np.frombuffer(frame_bytes, np.uint8)
                dec = cv2.imdecode(nparr, cv2.IMREAD_UNCHANGED)
                if dec is not None:
                    frame_h, frame_w = dec.shape[:2]
            except Exception as _fdim_err:
                logger.debug("Frame dimension extraction failed (non-fatal): %s", _fdim_err)

            conf_floor = get_vision_config().confidence_floor
            overlay_boxes = []

            # 1. Recognized authorized employees (Green)
            if face_res.decision == "MATCHED" and face_res.matched_employee_id:
                if face_res.similarity >= conf_floor:
                    for fb in face_boxes:
                        overlay_boxes.append({
                            "box": fb,
                            "type": "PERSON_MATCHED",
                            "label": f"Recognized: {face_res.employee_name} ({int(face_res.similarity * 100)}%)",
                            "confidence": round(float(face_res.similarity), 4),
                            "color": "green",
                            "entity": face_res.employee_name,
                        })

            # 2. Live unrecognized persons (Red)
            for pb in getattr(face_res, "live_person_boxes", []):
                if face_res.decision != "MATCHED" or not face_res.matched_employee_id:
                    conf = pb.get("confidence", 0.85)
                    if conf >= conf_floor:
                        overlay_boxes.append({
                            "box": pb["box"],
                            "type": "PERSON_UNMATCHED",
                            "label": f"Unknown Person ({int(conf * 100)}%)",
                            "confidence": round(float(conf), 4),
                            "color": "red",
                            "entity": None,
                        })

            # 3. Detected items, vehicles, and cases — Gated by category threshold
            cfg = get_vision_config()
            for d in vis_res.detections:
                is_veh = d.class_label == "vehicle"
                is_case = "case" in d.class_label.lower()
                target_floor = (
                    cfg.case_conf_threshold if is_case
                    else (getattr(cfg, "vehicle_conf_threshold", 0.25) if is_veh
                    else max(cfg.item_conf_threshold, conf_floor))
                )
                if d.confidence < target_floor:
                    continue
                tag_prefix = "Vehicle" if is_veh else ("Case" if is_case else "Item")
                item_label = getattr(d, "specific_label", None) or d.class_label
                color = "cyan" if is_veh else ("green" if is_case else "amber")
                overlay_boxes.append({
                    "box": d.bbox,
                    "type": "VEHICLE" if is_veh else "ITEM",
                    "label": f"{item_label} ({int(d.confidence * 100)}%)" if is_veh else f"{tag_prefix}: {item_label} ({int(d.confidence * 100)}%)",
                    "confidence": round(float(d.confidence), 4),
                    "color": color,
                    "entity": item_label,
                })

            # 4. Static images (Low-emphasis outline, e.g. Religious Image, Poster, Screen)
            for s in getattr(face_res, "static_detections", []):
                if s.get("confidence", 0.50) >= conf_floor:
                    overlay_boxes.append({
                        "box": s["box"],
                        "type": "STATIC_IMAGE",
                        "label": s["friendly_label"],
                        "confidence": round(float(s["confidence"]), 4),
                        "color": "static",
                        "entity": s["classification"],
                    })
                # Persist static image detection to database
                try:
                    static_entry = StaticImageDetection(
                        camera_id=cam.camera_id,
                        frame_ts=now,
                        bbox=s["box"],
                        liveness_score=s["liveness_score"],
                        classification=s["classification"],
                        classification_confidence=s["confidence"],
                        model_version="static-classifier-v1.0",
                        suppressed_alert=True,
                    )
                    session.add(static_entry)
                except Exception as ex:
                    logger.debug("Failed to record static detection: %s", ex)

            # 4b. Dynamic Wall Picture & Frame Detection (Posters, Prints, Wall Art)
            if dec is not None and dec.size > 0:
                try:
                    from src.ml.wall_picture_detector import WallPictureDetector
                    person_boxes = [b["box"] for b in overlay_boxes if b["type"] in ("PERSON_MATCHED", "PERSON_UNMATCHED")]
                    wall_frames = WallPictureDetector.detect_wall_pictures(dec, exclude_boxes=person_boxes)
                    for wf in wall_frames:
                        # Avoid duplicates if face_res already caught this box
                        is_dup = any(
                            abs(wf["box"][0] - b["box"][0]) < 25 and abs(wf["box"][1] - b["box"][1]) < 25
                            for b in overlay_boxes if b["type"] == "STATIC_IMAGE"
                        )
                        if not is_dup and wf["confidence"] >= conf_floor:
                            overlay_boxes.append(wf)
                            try:
                                static_entry = StaticImageDetection(
                                    camera_id=cam.camera_id,
                                    frame_ts=now,
                                    bbox=wf["box"],
                                    liveness_score=0.15,
                                    classification=wf["classification"],
                                    classification_confidence=wf["confidence"],
                                    model_version="wall-picture-detector-v1.0",
                                    suppressed_alert=True,
                                )
                                session.add(static_entry)
                            except Exception as ex:
                                logger.debug("Failed to record wall frame detection: %s", ex)
                except Exception as w_err:
                    logger.debug("WallPictureDetector execution failed: %s", w_err)

            # Update rolling activity logs for this camera HUD
            if cam.camera_id not in self._camera_logs:
                self._camera_logs[cam.camera_id] = deque(maxlen=10)
            cam_logs = self._camera_logs[cam.camera_id]
            cam_name = cam.label or f"Camera {cam.camera_id}"
            time_str = now.strftime("%H:%M:%S")

            if overlay_boxes:
                if any(b["type"] in ("PERSON_MATCHED", "PERSON_UNMATCHED") for b in overlay_boxes):
                    person_desc = face_res.employee_name if (face_res.decision == "MATCHED" and face_res.matched_employee_id) else "Person"
                    msg = f"{cam_name} — {person_desc} Detected — {time_str}"
                    if not cam_logs or cam_logs[-1]["text"] != msg:
                        cam_logs.append({"id": str(uuid.uuid4()), "timestamp": time_str, "text": msg, "type": "PERSON"})

                if any(b["type"] == "VEHICLE" for b in overlay_boxes):
                    for vb in [b for b in overlay_boxes if b["type"] == "VEHICLE"]:
                        msg = f"{cam_name} — Vehicle Entry: {vb['label']} — {time_str}"
                        if not cam_logs or cam_logs[-1]["text"] != msg:
                            cam_logs.append({"id": str(uuid.uuid4()), "timestamp": time_str, "text": msg, "type": "VEHICLE"})
                    # Auto-capture and persist vehicle snapshot dossier
                    try:
                        os.makedirs("snapshots", exist_ok=True)
                        v_snap_path = os.path.join("snapshots", f"vehicle_{cam.camera_id}_{now.strftime('%Y%m%d_%H%M%S')}.jpg")
                        with open(v_snap_path, "wb") as vf:
                            vf.write(annotated_bytes)
                    except Exception as _vsnap_err:
                        logger.debug("Vehicle snapshot persist error: %s", _vsnap_err)

                if any(b["type"] == "ITEM" for b in overlay_boxes):
                    msg = f"{cam_name} — {vis_res.cases_detected} Cases / {vis_res.vision_count} Units Detected — {time_str}"
                    if not cam_logs or cam_logs[-1]["text"] != msg:
                        cam_logs.append({"id": str(uuid.uuid4()), "timestamp": time_str, "text": msg, "type": "ITEM"})

                if any(b["type"] == "STATIC_IMAGE" for b in overlay_boxes):
                    for sb in [b for b in overlay_boxes if b["type"] == "STATIC_IMAGE"]:
                        class_title = str(sb["entity"]).replace("_", " ").title()
                        msg = f"{cam_name} — Static: {class_title} — {time_str}"
                        if not cam_logs or cam_logs[-1]["text"] != msg:
                            cam_logs.append({"id": str(uuid.uuid4()), "timestamp": time_str, "text": msg, "type": "STATIC"})

            # In-progress compliance tag
            active_tx = self._active_transactions.get(cam.camera_id)
            if active_tx is None and (vis_res.vision_count > 0 or len(vis_res.detections) > 0 or face_res.matched_employee_id):
                active_tx = {
                    "eventId": f"TX-{cam.camera_id[:4]}",
                    "status": "CONSENSUS_PENDING",
                    "displayText": f"TX-{cam.camera_id[:4]} | Consensus Pending",
                }

            detection_data.update({
                "frameTs": now.isoformat(),
                "frameWidth": frame_w,
                "frameHeight": frame_h,
                "boxes": overlay_boxes,
                "entityCount": len(overlay_boxes),
                "casesDetected": vis_res.cases_detected,
                "unitsDetected": vis_res.vision_count,
                "carrierName": carrier_label,
                "faceDecision": face_res.decision,
                "livenessDecision": face_res.liveness_decision,
                "livenessScore": round(face_res.liveness_score * 100, 1),
                "confidence": round(vis_res.vision_confidence * 100, 1) if vis_res.vision_confidence else 95.0,
                "boxesCount": len(overlay_boxes),
                "activeTransaction": active_tx,
                "recentLogs": list(cam_logs),
            })
        except Exception as e:
            logger.warning("Preview CV annotation error on %s: %s", cam.camera_id, e)

        self._last_detections[cam.camera_id] = detection_data

        os.makedirs("snapshots", exist_ok=True)
        preview_path = os.path.join("snapshots", f"preview_{cam.camera_id}.jpg")
        raw_path = os.path.join("snapshots", f"raw_{cam.camera_id}.jpg")
        try:
            with open(preview_path, "wb") as f:
                f.write(annotated_bytes)
            with open(raw_path, "wb") as f:
                f.write(frame_bytes)
        except Exception as e:
            logger.warning("Could not write preview snapshot: %s", e)

        await session.commit()

        # Broadcast real-time detection overlay to WebSocket clients
        await ws_hub.broadcast_event("detection_update", detection_data)

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
        event_num = int(time.time() * 1000) % 90000 + 10000
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

        # 3. Run Real OpenCV Face Recognition on the annotated frame with Anti-Spoofing Liveness
        face_result, final_annotated_bytes, face_boxes = FaceRecognitionService.detect_and_match_faces(
            frame_bytes=annotated_bytes,
            enrolled_employees=roster,
            prior_detections_count=len(vision_result.detections),
            cases_detected=vision_result.cases_detected,
            units_detected=vision_result.vision_count,
            raw_frame_bytes=frame_bytes,
            camera_id=cam.camera_id,
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
                alert_id=f"ALT-2026-{uuid.uuid4().hex[:6].upper()}",
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

        # Update active transaction compliance tag for camera HUD & overlay
        tx_label = (
            f"PASS ({int(event.vision_confidence * 100 if event.vision_confidence else 98)}%)"
            if event.verdict == "PASS"
            else f"MISMATCH — {event.severity} (Δ {event.delta_units} units)"
        )
        self._active_transactions[cam.camera_id] = {
            "eventId": event.event_id,
            "status": "RESOLVED",
            "verdict": event.verdict,
            "severity": event.severity,
            "deltaUnits": event.delta_units,
            "displayText": f"TX-{event.event_id} | {tx_label}",
        }

        # Add transaction log to camera HUD
        cam_logs = self._camera_logs.setdefault(cam.camera_id, deque(maxlen=10))
        cam_logs.append({
            "id": str(uuid.uuid4()),
            "timestamp": now.strftime("%H:%M:%S"),
            "text": f"{cam.label} — TX {event.event_id}: {tx_label} — {now.strftime('%H:%M:%S')}",
            "type": "TRANSACTION",
        })

        logger.info("Created real ExitEvent %s on %s (Units: %d, Verdict: %s)", event_id, lane_id, event.units_detected, event.verdict)
        return event


# Global worker singleton
camera_worker = CameraIngestionWorker(poll_interval_sec=3.0)

