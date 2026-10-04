"""Background Camera Stream Ingestion & Real-Time Computer Vision Worker

Continuously monitors registered surveillance cameras, polls live frames,
executes OpenCV contour/object detection and Haar-cascade face recognition,
saves real annotated snapshots, records exit events in the database, and
broadcasts live events to the frontend via WebSockets.
"""

import asyncio
import os
import time
import math
import logging
from typing import Optional, Dict, Any, List, Tuple
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
    DispatchSession,
    VirtualTripwireConfig,
    TripwireCrossingEvent,
    get_utc_now,
)
from dataclasses import asdict
from src.ml.level1_detection.vision_service import VisionInferenceService
from src.services.vision_detection.frame_renderer import FrameRenderer
from src.ml.face_recognition.face_service import FaceRecognitionService
from src.ml.material_segmentation import MaterialSegmentationService
from src.ml.hazard_service import FlameHazardDetector
from src.ml.pose_service import SuspiciousBehaviorDetector
from src.ml.ppe_service import PPEComplianceDetector
from src.engine.zone_analytics import zone_analytics_engine
from src.engine.dispatch_engine import DispatchEngine
from src.engine.tripwire_engine import TripwireEngine
from src.engine.fusion import MultiSensorFusionEngine
from src.engine.verdict import VerdictEngine
from src.ml.universal_taxonomy_service import UniversalTaxonomyService
from src.engine.frame_analysis_report import FrameAnalysisReportGenerator
from src.realtime.hub import ws_hub
from src.ml.model_config import get_vision_config
from src.ml.level5_tracking.tracker_service import intra_camera_tracker
from src.ml.level3_liveness.static_image_service import quarantine_enclosed_visual_content


logger = logging.getLogger("secops.camera_worker")


class CameraIngestionWorker:
    """Orchestrates live frame polling, object/face inference, and event generation."""

    def __init__(self, poll_interval_sec: float = 0.5):
        self.poll_interval_sec = poll_interval_sec
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self._last_frames: Dict[str, np.ndarray] = {}
        self._last_event_time: Dict[str, float] = {}
        self._last_detections: Dict[str, Dict[str, Any]] = {}
        self._camera_logs: Dict[str, deque] = {}
        self._active_transactions: Dict[str, Dict[str, Any]] = {}
        self._track_history: Dict[str, Dict[str, Tuple[float, float]]] = {}
        self._cached_catalog: List[Dict[str, Any]] = []
        self._cached_catalog_ts: float = 0.0
        self._cached_roster: List[Dict[str, Any]] = []
        self._cached_roster_ts: float = 0.0
        self._last_raw_frames: Dict[str, bytes] = {}
        self._last_annotated_frames: Dict[str, bytes] = {}
        self._last_hazard_alert_ts: Dict[Tuple[str, str], float] = {}

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
            cam.camera_id, str(cam.ip_address), str(target_path), str(cam.stream_url or "") if cam.stream_url else None, max_wait_sec=0.15
        )
        if sm_bytes:
            frame_bytes, source_desc = sm_bytes, f"StreamManager ({cam.ip_address})"
        else:
            clean_ip_str = str(cam.ip_address or "").strip()
            clean_url_str = str(cam.stream_url or "").strip()
            is_local = clean_ip_str in ("0", "1", "2", "webcam") or clean_url_str in ("0", "1", "2")
            if is_local:
                # Local webcams on Windows are exclusive-access; stream_manager is capturing. Do not freeze loop with duplicate VideoCapture
                frame_bytes = None
            else:
                from src.api.cameras import capture_camera_frame_sync
                frame_bytes, source_desc, latency_ms = await asyncio.to_thread(
                    capture_camera_frame_sync,
                    str(cam.ip_address),
                    str(cam.rtsp_path or ""),
                    str(cam.credentials_ref or ""),
                    str(cam.sub_stream_path or ""),
                    1.2,
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
            # Stream gap logging for active industrial dispatch sessions
            if cam.lane_id:
                try:
                    await DispatchEngine.record_stream_gap(
                        session=session,
                        dock_lane_id=cam.lane_id,
                        gap_seconds=self.poll_interval_sec,
                    )
                except Exception as _gap_err:
                    logger.debug("Dispatch stream gap recording error: %s", _gap_err)
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
            now_epoch = time.time()
            if not self._cached_catalog or (now_epoch - self._cached_catalog_ts > 15.0):
                prod_res = await session.execute(select(Product))
                products = prod_res.scalars().all()
                self._cached_catalog = [
                    {"product_id": p.product_id, "sku_code": p.sku_code, "pack_size": p.pack_size}
                    for p in products
                ]
                self._cached_catalog_ts = now_epoch
            catalog = self._cached_catalog

            if not self._cached_roster or (now_epoch - self._cached_roster_ts > 15.0):
                emp_res = await session.execute(select(Employee).where(Employee.active_flag == True))
                employees = emp_res.scalars().all()
                self._cached_roster = [
                    {"employee_id": e.employee_id, "name": e.name, "face_embedding": e.face_embedding}
                    for e in employees
                ]
                self._cached_roster_ts = now_epoch
            roster = self._cached_roster

            vis_res, obj_bytes = await asyncio.to_thread(
                VisionInferenceService.analyze_frame_bytes, 
                frame_bytes, 
                catalog_products=catalog,
                roi_polygon=cam.roi_polygon,
                ignored_classes=cam.ignored_classes,
                camera_id=cam.camera_id
            )

            # Pre-extract display containers (wall pictures, screens, monitors, laptops, phones) for content-in-content quarantine
            display_containers = []
            for d in vis_res.detections:
                label_lower = (d.specific_label or d.class_label or "").lower()
                if any(k in label_lower for k in ("picture", "poster", "screen", "monitor", "display", "tv", "cell phone", "phone", "smartphone")):
                    display_containers.append(d.bbox)

            face_res, final_bytes, face_boxes = await asyncio.to_thread(
                FaceRecognitionService.detect_and_match_faces,
                frame_bytes=obj_bytes or frame_bytes,
                enrolled_employees=roster,
                prior_detections_count=len(vis_res.detections),
                cases_detected=vis_res.cases_detected,
                units_detected=vis_res.vision_count,
                raw_frame_bytes=frame_bytes,
                camera_id=cam.camera_id,
                container_boxes=display_containers,
            )
            
            # Issue 1: Single Source of Truth for Rendering
            try:
                import cv2
                import numpy as np
                nparr = np.frombuffer(frame_bytes, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                draw_boxes = []
                for d in vis_res.detections:
                    bx, by, bw, bh = d.bbox
                    disp_label = (d.specific_label or d.class_label).upper()
                    conf_pct = int(d.confidence * 100)
                    
                    if d.class_label == "person":
                        color = (0, 255, 180)
                    elif d.class_label == "case_full":
                        color = (0, 230, 115)
                    elif d.class_label == "vehicle":
                        color = (255, 190, 0)
                    elif d.class_label in ("doorway", "wall_picture", "bookshelf") or d.is_environment_only:
                        color = (255, 200, 0)
                    else:
                        color = (0, 165, 255)
                        
                    draw_boxes.append({
                        'bbox': [bx, by, bw, bh],
                        'label': f"{disp_label} {conf_pct}%",
                        'color': color
                    })
                    
                for fb in face_boxes:
                    draw_boxes.append({
                        'bbox': [fb[0], fb[1], fb[2], fb[3]],
                        'label': 'FACE',
                        'color': (255, 100, 100)
                    })
                    
                total_cases = sum(1 for d in vis_res.detections if d.class_label == "case_full")
                total_units = sum(d.pack_size for d in vis_res.detections if d.class_label in ("case_full", "single_unit", "vehicle"))
                
                status_banner = f"SURVEILLANCE CV // DETECTIONS: {len(vis_res.detections) + len(face_boxes)} (CASES:{total_cases} UNITS:{total_units})"
                
                img = FrameRenderer.draw_overlay(img, draw_boxes, status_banner, vis_res.latency_ms)
                _, encoded_jpg = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                annotated_bytes = encoded_jpg.tobytes()
            except Exception as _render_err:
                logger.error("Render Error: %s", _render_err)
                annotated_bytes = final_bytes or obj_bytes or frame_bytes

            carrier_label = face_res.employee_name if face_res.matched_employee_id else "UNVERIFIED"

            # Determine frame dimensions for SVG viewport alignment
            frame_w, frame_h = 1280, 720
            dec: Optional[np.ndarray] = None
            try:
                nparr = np.frombuffer(frame_bytes, np.uint8)
                dec = cv2.imdecode(nparr, cv2.IMREAD_UNCHANGED)
                if dec is not None:
                    frame_h, frame_w = dec.shape[:2]
            except Exception as _fdim_err:
                logger.debug("Frame dimension extraction failed (non-fatal): %s", _fdim_err)

            cfg = get_vision_config()
            conf_floor = cfg.confidence_floor
            overlay_boxes = []

            all_person_boxes: List[List[int]] = []

            # 1. Recognized authorized employees (Green - Confirmed Match)
            if face_res.decision == "MATCHED" and face_res.matched_employee_id:
                if face_res.similarity >= conf_floor:
                    for fb in face_boxes:
                        fx, fy, fw, fh = fb
                        pb_x = max(0, fx - int(fw * 0.35))
                        pb_y = max(0, fy - int(fh * 0.15))
                        pb_w = min(frame_w - pb_x, int(fw * 1.70))
                        pb_h = min(frame_h - pb_y, int(fh * 2.20))
                        all_person_boxes.append([pb_x, pb_y, pb_w, pb_h])
                        overlay_boxes.append({
                            "box": [pb_x, pb_y, pb_w, pb_h],
                            "type": "PERSON_MATCHED",
                            "label": f"Known: {face_res.employee_name}",
                            "confidence": round(float(face_res.similarity), 4),
                            "color": "green",
                            "entity": face_res.employee_name,
                            "identity_status": "CONFIRMED_MATCH",
                            "employee_id": face_res.matched_employee_id,
                            "sub_label": f"Verified: {face_res.employee_name}",
                            "detection_state": "CONFIRMED",
                        })

            # 2. Live unrecognized persons (Cyan / Neutral, NOT alarming Red!)
            for pb in getattr(face_res, "live_person_boxes", []):
                if face_res.decision != "MATCHED" or not face_res.matched_employee_id:
                    conf = pb.get("confidence", 0.85)
                    if conf >= conf_floor:
                        fx, fy, fw, fh = pb["box"]
                        pb_x = max(0, fx - int(fw * 0.35))
                        pb_y = max(0, fy - int(fh * 0.15))
                        pb_w = min(frame_w - pb_x, int(fw * 1.70))
                        pb_h = min(frame_h - pb_y, int(fh * 2.20))
                        all_person_boxes.append([pb_x, pb_y, pb_w, pb_h])
                        overlay_boxes.append({
                            "box": [pb_x, pb_y, pb_w, pb_h],
                            "type": "PERSON_UNMATCHED",
                            "label": "Unknown Person",
                            "confidence": round(float(conf), 4),
                            "color": "cyan",
                            "entity": "Unknown Person",
                            "identity_status": "NO_MATCH",
                            "sub_label": "Match: No confirmed database match",
                            "detection_state": "CONFIRMED",
                        })

            # 3. Detected items, vehicles, cases, environmental fixtures, and people from YOLOX
            cfg = get_vision_config()
            for d in vis_res.detections:
                is_person = d.class_label == "person"
                is_veh = d.class_label == "vehicle"
                is_case = "case" in d.class_label.lower()

                if is_person:
                    # Content-in-content quarantine: suppress person detection if enclosed inside a display/picture container
                    if display_containers:
                        if quarantine_enclosed_visual_content([d.bbox], display_containers, containment_threshold=0.65):
                            continue

                    # Only append verified vertical human bodies to body-level trackers (not face crops or horizontal slices)
                    if d.bbox[3] >= 1.25 * d.bbox[2] and d.bbox[3] >= 140:
                        all_person_boxes.append(d.bbox)
                    # Check if face recognition already identified or tracked this person
                    has_face_overlap = False
                    for ob in overlay_boxes:
                        if ob["type"] in ("PERSON_MATCHED", "PERSON_UNMATCHED"):
                            fx, fy, fw, fh = ob["box"]
                            fcx, fcy = fx + fw / 2.0, fy + fh / 2.0
                            if (d.bbox[0] - 25 <= fcx <= d.bbox[0] + d.bbox[2] + 25 and
                                d.bbox[1] - 25 <= fcy <= d.bbox[1] + d.bbox[3] + 25):
                                has_face_overlap = True
                                break
                    # Only append person body box if face was NOT visible / occluded
                    if not has_face_overlap and d.confidence >= cfg.person_conf_threshold:
                        overlay_boxes.append({
                            "box": d.bbox,
                            "type": "PERSON_UNMATCHED",
                            "label": "Unknown Person",
                            "confidence": round(float(d.confidence), 4),
                            "color": "cyan",
                            "entity": "Unknown Person",
                            "identity_status": "NO_MATCH",
                            "sub_label": "Match: No confirmed database match",
                            "detection_state": "CONFIRMED",
                        })
                    continue

                target_floor = (
                    cfg.case_conf_threshold if is_case
                    else (getattr(cfg, "vehicle_conf_threshold", 0.25) if is_veh
                    else cfg.item_conf_threshold)
                )
                # Live confirmation floor: single retail items require >= 0.50 to prevent 38-39% noisy proposals
                live_item_floor = 0.50 if (not is_veh and not is_case and d.class_label == "single_unit" and d.is_inventory_relevant) else target_floor
                if d.confidence < live_item_floor:
                    continue

                # Content-in-content quarantine: suppress single retail items enclosed within display/picture containers
                if display_containers and not is_veh and not is_case and d.class_label == "single_unit":
                    if quarantine_enclosed_visual_content([d.bbox], display_containers, containment_threshold=0.60):
                        continue

                item_label = d.specific_label or d.class_label
                item_lower = item_label.lower()
                is_door = d.class_label == "doorway" or "doorway" in item_lower
                is_screen = any(k in item_lower for k in ("screen", "monitor", "display", "tv"))
                is_laptop = "laptop" in item_lower
                is_watch = "watch" in item_lower
                is_bookshelf = (
                    d.class_label == "bookshelf" or
                    any(k in item_lower for k in ("bookshelf", "book shelf", "shelving", "bookcase", "shelf", "rack"))
                )
                is_book = ("book" in item_lower or "binder" in item_lower) and not is_bookshelf
                # Physical scale filter: a retail handheld book cannot exceed 40% frame width, 45% frame height, or 15% frame area
                if is_book:
                    bw, bh = d.bbox[2], d.bbox[3]
                    if bw > 0.40 * frame_w or bh > 0.45 * frame_h or (bw * bh) > 0.15 * (frame_w * frame_h):
                        is_book = False
                        is_bookshelf = True

                is_phone = any(k in item_lower for k in ("phone", "smartphone", "cell phone"))
                is_wall_picture = d.class_label == "wall_picture" or any(k in item_lower for k in ("picture", "poster", "wall art", "framed"))
                if is_wall_picture:
                    # Environmental wall art/pictures are suppressed from live retail item overlays to eliminate false positives
                    continue

                is_clock = "clock" in item_lower
                is_bottle = "bottle" in item_lower
                is_keyboard = "keyboard" in item_lower
                is_mouse = "mouse" in item_lower

                # WristWatch candidate cannot overlap beverage bottles or cups (protects bottle cap)
                if is_watch:
                    overlaps_bottle = False
                    for ob in overlay_boxes:
                        if ob.get("type") in ("BOTTLE", "CUP", "CAN") or "bottle" in ob.get("entity", "").lower():
                            bx, by, bw, bh = ob["box"]
                            wx, wy, ww, wh = d.bbox
                            if (bx - 5 <= wx <= bx + bw + 5) and (by - 5 <= wy <= by + bh + 5):
                                overlaps_bottle = True
                                break
                    if overlaps_bottle:
                        continue

                if is_veh:
                    b_type = "VEHICLE"
                    b_label = item_label
                    b_color = "cyan"
                elif is_case:
                    b_type = "CASE"
                    b_label = f"Case: {item_label}"
                    b_color = "green"
                elif is_door:
                    b_type = "DOORWAY"
                    b_label = item_label
                    b_color = "cyan"
                elif is_screen:
                    b_type = "DESKTOP_SCREEN"
                    b_label = "Desktop Screen"
                    b_color = "cyan"
                elif is_laptop:
                    b_type = "LAPTOP"
                    b_label = "Laptop"
                    b_color = "cyan"
                elif is_watch:
                    b_type = "WRISTWATCH"
                    b_label = "WristWatch"
                    b_color = "amber"
                elif is_bookshelf:
                    b_type = "BOOKSHELF"
                    b_label = "Bookshelf"
                    b_color = "cyan"
                elif is_book:
                    b_type = "BOOK"
                    b_label = "Book"
                    b_color = "amber"
                elif is_phone:
                    b_type = "SMARTPHONE"
                    b_label = "Smartphone"
                    b_color = "cyan"
                elif is_clock:
                    b_type = "CLOCK"
                    b_label = "Clock"
                    b_color = "cyan"
                elif is_bottle:
                    b_type = "BOTTLE"
                    b_label = "Bottle"
                    b_color = "amber"
                elif is_keyboard:
                    b_type = "KEYBOARD"
                    b_label = "Keyboard"
                    b_color = "cyan"
                elif is_mouse:
                    b_type = "MOUSE"
                    b_label = "Mouse"
                    b_color = "cyan"
                else:
                    b_type = "ITEM"
                    b_label = item_label
                    b_color = "amber"

                # Check if item (such as a wristwatch) is worn by or associated with a person
                item_relation = getattr(d, "relation", None)
                parent_tid = getattr(d, "parent_track_id", None)
                if not item_relation and all_person_boxes:
                    icx = d.bbox[0] + d.bbox[2] / 2.0
                    icy = d.bbox[1] + d.bbox[3] / 2.0
                    for p_idx, pb in enumerate(all_person_boxes):
                        if (pb[0] - 25 <= icx <= pb[0] + pb[2] + 25) and (pb[1] <= icy <= pb[1] + pb[3] + 25):
                            item_relation = "worn_by" if is_watch else "carried_by"
                            parent_tid = f"person_{p_idx + 1}"
                            break

                overlay_boxes.append({
                    "box": d.bbox,
                    "type": b_type,
                    "label": b_label,
                    "confidence": round(float(d.confidence), 4),
                    "color": b_color,
                    "entity": item_label,
                    "detection_state": "CONFIRMED",
                    "relation": item_relation or "standalone",
                    "parent_track_id": parent_tid,
                    "wearable": is_watch,
                    "is_environment_only": d.is_environment_only,
                    "is_inventory_relevant": d.is_inventory_relevant,
                })

            # 4. Real-Time Flame & Fire Hazard Detection
            if dec is not None:
                try:
                    flames = FlameHazardDetector.detect_flames(dec)
                    for fl in flames:
                        is_confirmed = fl.confidence >= cfg.fire_confirmed_threshold
                        lbl = f"FIRE Ã‚Â· {int(fl.confidence * 100)}%" if is_confirmed else f"FLAME ANOMALY Ã‚Â· {int(fl.confidence * 100)}%"
                        overlay_boxes.append({
                            "box": fl.bbox,
                            "type": "HAZARD_FIRE",
                            "label": lbl,
                            "confidence": fl.confidence,
                            "color": "red" if is_confirmed else "amber",
                            "entity": "Fire / Flame",
                        })
                        alert_key = (cam.camera_id, "FIRE_HAZARD")
                        last_ts = self._last_hazard_alert_ts.get(alert_key, 0.0)
                        now_monotonic = time.time()
                        if (now_monotonic - last_ts) >= 10.0 and fl.confidence >= cfg.fire_hazard_floor:
                            self._last_hazard_alert_ts[alert_key] = now_monotonic
                            severity = "HIGH" if is_confirmed else "MEDIUM"
                            fire_alert = Alert(
                                alert_id=f"ALT-FIRE-{uuid.uuid4().hex[:6].upper()}",
                                camera_id=cam.camera_id,
                                alert_type="FIRE_HAZARD",
                                severity=severity,
                                delta_units=0,
                                status="OPEN",
                                created_at=now,
                                resolution_note=f"Flame detected with {int(fl.confidence * 100)}% confidence.",
                            )
                            session.add(fire_alert)
                            await session.flush()
                            await ws_hub.broadcast_event("new_alert", {
                                "alertId": fire_alert.alert_id,
                                "cameraId": cam.camera_id,
                                "alertType": fire_alert.alert_type,
                                "severity": fire_alert.severity,
                                "timestamp": now.isoformat(),
                            })
                except Exception as _flame_err:
                    logger.debug("Flame detector error: %s", _flame_err)

            # 5. Pose Estimation, Suspicious Behavior & PPE Compliance
            if dec is not None and all_person_boxes:
                for p_box in all_person_boxes:
                    try:
                        # 5A. Suspicious behavior & keypoint analysis
                        pose_res = SuspiciousBehaviorDetector.estimate_pose_and_behavior(dec, p_box)
                        if pose_res.is_suspicious:
                            is_confirmed = pose_res.confidence >= cfg.suspicious_confirmed_threshold
                            lbl = (
                                f"SUSPICIOUS Ã‚Â· {int(pose_res.confidence * 100)}% ({pose_res.suspicious_reason})"
                                if is_confirmed
                                else f"POSSIBLE ANOMALY Ã‚Â· {int(pose_res.confidence * 100)}% ({pose_res.suspicious_reason})"
                            )
                            overlay_boxes.append({
                                "box": p_box,
                                "type": "SUSPICIOUS_BEHAVIOR",
                                "label": lbl,
                                "confidence": pose_res.confidence,
                                "color": "red" if is_confirmed else "amber",
                                "entity": "Suspicious Activity",
                            })
                            alert_key = (cam.camera_id, "SUSPICIOUS_BEHAVIOR")
                            last_ts = self._last_hazard_alert_ts.get(alert_key, 0.0)
                            now_monotonic = time.time()
                            if (now_monotonic - last_ts) >= 15.0 and is_confirmed:
                                self._last_hazard_alert_ts[alert_key] = now_monotonic
                                sus_alert = Alert(
                                    alert_id=f"ALT-SUS-{uuid.uuid4().hex[:6].upper()}",
                                    camera_id=cam.camera_id,
                                    alert_type="SUSPICIOUS_BEHAVIOR",
                                    severity="HIGH",
                                    delta_units=0,
                                    status="OPEN",
                                    created_at=now,
                                    resolution_note=f"Suspicious posture detected: {pose_res.suspicious_reason} ({int(pose_res.confidence * 100)}%).",
                                )
                                session.add(sus_alert)
                                await session.flush()
                                await ws_hub.broadcast_event("new_alert", {
                                    "alertId": sus_alert.alert_id,
                                    "cameraId": cam.camera_id,
                                    "alertType": sus_alert.alert_type,
                                    "severity": sus_alert.severity,
                                    "timestamp": now.isoformat(),
                                })

                        # 5B. Wrist watch detection from pose keypoints
                        if pose_res.keypoints:
                            from src.ml.level2_classification.fixture_classifier import SceneObjectDetector
                            wrist_watches = SceneObjectDetector.detect_wrist_watches(
                                dec,
                                wrist_keypoints=pose_res.keypoints,
                                person_boxes=[p_box],
                                exclude_boxes=[ob["box"] for ob in overlay_boxes],
                            )
                            for ww in wrist_watches:
                                wb = ww["bbox"]
                                if not any(abs(wb[0] - ob["box"][0]) < 25 and abs(wb[1] - ob["box"][1]) < 25 for ob in overlay_boxes if ob["type"] in ("ITEM", "WRISTWATCH")):
                                    overlay_boxes.append({
                                        "box": wb,
                                        "type": "WRISTWATCH",
                                        "label": f"WristWatch ({int(ww['confidence'] * 100)}%)",
                                        "confidence": round(float(ww["confidence"]), 4),
                                        "color": "amber",
                                        "entity": "WristWatch",
                                        "relation": "worn_by",
                                        "parent_track_id": f"person_{p_box[0]}_{p_box[1]}",
                                        "wearable": True,
                                        "detection_state": "CONFIRMED",
                                        "is_environment_only": False,
                                        "is_inventory_relevant": True,
                                    })

                        # 5C. PPE Worker Safety Assessment (Only in Industrial / Safety mode)
                        is_industrial_cam = getattr(cam, "pipeline_mode", "") in ("INDUSTRIAL_SAFETY", "MATERIAL_SEGMENTATION", "PPE_COMPLIANCE")
                        if is_industrial_cam:
                            ppe_res = PPEComplianceDetector.evaluate_worker_ppe(dec, p_box)
                            if ppe_res.has_helmet and ppe_res.helmet_box:
                                overlay_boxes.append({
                                    "box": ppe_res.helmet_box,
                                    "type": "PPE_COMPLIANT",
                                    "label": f"HELMET Ã‚Â· {int(ppe_res.helmet_confidence * 100)}%",
                                    "confidence": ppe_res.helmet_confidence,
                                    "color": "green",
                                    "entity": "Hard Hat",
                                })
                            if ppe_res.has_vest and ppe_res.vest_box:
                                overlay_boxes.append({
                                    "box": ppe_res.vest_box,
                                    "type": "PPE_COMPLIANT",
                                    "label": f"VEST Ã‚Â· {int(ppe_res.vest_confidence * 100)}%",
                                    "confidence": ppe_res.vest_confidence,
                                    "color": "green",
                                    "entity": "Safety Vest",
                                })
                            if not ppe_res.is_compliant:
                                overlay_boxes.append({
                                    "box": p_box,
                                    "type": "PPE_VIOLATION",
                                    "label": f"PPE VIOLATION ({', '.join(ppe_res.violations)})",
                                    "confidence": 0.90,
                                    "color": "amber",
                                    "entity": "Missing PPE Gear",
                                })
                                alert_key = (cam.camera_id, "PPE_VIOLATION")
                                last_ts = self._last_hazard_alert_ts.get(alert_key, 0.0)
                                now_monotonic = time.time()
                                if (now_monotonic - last_ts) >= 15.0:
                                    self._last_hazard_alert_ts[alert_key] = now_monotonic
                                    ppe_alert = Alert(
                                        alert_id=f"ALT-PPE-{uuid.uuid4().hex[:6].upper()}",
                                        camera_id=cam.camera_id,
                                        alert_type="PPE_VIOLATION",
                                        severity="MEDIUM",
                                        delta_units=0,
                                        status="OPEN",
                                        created_at=now,
                                        resolution_note=f"PPE Safety Violation: {', '.join(ppe_res.violations)}.",
                                    )
                                    session.add(ppe_alert)
                                    await session.flush()
                                    await ws_hub.broadcast_event("new_alert", {
                                        "alertId": ppe_alert.alert_id,
                                        "cameraId": cam.camera_id,
                                        "alertType": ppe_alert.alert_type,
                                        "severity": ppe_alert.severity,
                                        "timestamp": now.isoformat(),
                                    })
                    except Exception as _p_err:
                        logger.debug("Pose/PPE error: %s", _p_err)

            # 6. Store Occupancy & Zone Analytics Processing
            person_tracks_for_zone = []
            for idx, pb in enumerate(all_person_boxes):
                person_tracks_for_zone.append({
                    "track_id": idx + 1,
                    "bbox": pb,
                    "center": (pb[0] + pb[2] / 2.0, pb[1] + pb[3] / 2.0),
                })
            try:
                occ_snapshot = zone_analytics_engine.process_person_tracks(
                    camera_id=cam.camera_id,
                    tracks=person_tracks_for_zone,
                    frame_width=frame_w,
                    frame_height=frame_h,
                )
                detection_data.update({
                    "occupancy": occ_snapshot.current_room_occupancy,
                    "totalFootfallIn": occ_snapshot.total_footfall_in,
                    "totalFootfallOut": occ_snapshot.total_footfall_out,
                    "crowdDensity": occ_snapshot.crowd_density_level,
                    "zoneMetrics": [asdict(zm) for zm in occ_snapshot.zone_metrics],
                    "tripwireTallies": [asdict(tw) for tw in occ_snapshot.tripwires],
                    "uniqueVisitors": occ_snapshot.unique_visitors_count,
                    "trackingFidelity": occ_snapshot.tracking_fidelity_status,
                })
            except Exception as _occ_err:
                logger.debug("Occupancy zone analytics error: %s", _occ_err)

            # Deduplicate overlay boxes to eliminate cluttered overlapping tags
            def _calc_box_iou(b1, b2):
                xa = max(b1[0], b2[0])
                ya = max(b1[1], b2[1])
                xb = min(b1[0] + b1[2], b2[0] + b2[2])
                yb = min(b1[1] + b1[3], b2[1] + b2[3])
                inter = max(0, xb - xa) * max(0, yb - ya)
                denom = b1[2] * b1[3] + b2[2] * b2[3] - inter
                return inter / float(denom) if denom > 0 else 0.0

            clean_boxes = []
            for ob in sorted(overlay_boxes, key=lambda x: x.get("confidence", 0.0), reverse=True):
                if not any(_calc_box_iou(ob["box"], cb["box"]) > 0.45 and ob["type"] == cb["type"] for cb in clean_boxes):
                    clean_boxes.append(ob)

            # Foreground / Background occlusion hierarchy:
            # If a human stands in front of a background doorway, suppress the doorway box
            # so the cyan doorway line does not cross directly through the person's head/face
            person_boxes_in_overlay = [b["box"] for b in clean_boxes if "PERSON" in b["type"] or b["type"] == "SUSPICIOUS_BEHAVIOR"]
            filtered_overlay = []
            for ob in clean_boxes:
                if ob["type"] == "DOORWAY":
                    ob_box = ob["box"]
                    has_human_in_front = any(
                        (pb[0] + pb[2] / 2.0 >= ob_box[0] and pb[0] + pb[2] / 2.0 <= ob_box[0] + ob_box[2] and
                         pb[1] + pb[3] / 2.0 >= ob_box[1] and pb[1] + pb[3] / 2.0 <= ob_box[1] + ob_box[3])
                        for pb in person_boxes_in_overlay
                    )
                    if has_human_in_front:
                        continue
                filtered_overlay.append(ob)
            overlay_boxes = filtered_overlay

            # 4. Static face spoof images (Anti-spoofing photo attacks against biometric scanner)
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

            # Update rolling activity logs for this camera HUD
            if cam.camera_id not in self._camera_logs:
                self._camera_logs[cam.camera_id] = deque(maxlen=10)
            cam_logs = self._camera_logs[cam.camera_id]
            cam_name = cam.label or f"Camera {cam.camera_id}"
            time_str = now.strftime("%H:%M:%S")

            if overlay_boxes:
                if any(b["type"] in ("PERSON_MATCHED", "PERSON_UNMATCHED") for b in overlay_boxes):
                    person_desc = f"Known: {face_res.employee_name}" if (face_res.decision == "MATCHED" and face_res.matched_employee_id) else "Unknown Person"
                    msg = f"{cam_name} Ã¢â‚¬â€ {person_desc} Detected Ã¢â‚¬â€ {time_str}"
                    if not cam_logs or cam_logs[-1]["text"] != msg:
                        cam_logs.append({"id": str(uuid.uuid4()), "timestamp": time_str, "text": msg, "type": "PERSON"})

                if any(b["type"] == "VEHICLE" for b in overlay_boxes):
                    for vb in [b for b in overlay_boxes if b["type"] == "VEHICLE"]:
                        msg = f"{cam_name} Ã¢â‚¬â€ Vehicle Entry: {vb['label']} Ã¢â‚¬â€ {time_str}"
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
                    msg = f"{cam_name} Ã¢â‚¬â€ {vis_res.cases_detected} Cases / {vis_res.vision_count} Units Detected Ã¢â‚¬â€ {time_str}"
                    if not cam_logs or cam_logs[-1]["text"] != msg:
                        cam_logs.append({"id": str(uuid.uuid4()), "timestamp": time_str, "text": msg, "type": "ITEM"})

                if any(b["type"] == "STATIC_IMAGE" for b in overlay_boxes):
                    for sb in [b for b in overlay_boxes if b["type"] == "STATIC_IMAGE"]:
                        class_title = str(sb["entity"]).replace("_", " ").title()
                        msg = f"{cam_name} Ã¢â‚¬â€ Static: {class_title} Ã¢â‚¬â€ {time_str}"
                        if not cam_logs or cam_logs[-1]["text"] != msg:
                            cam_logs.append({"id": str(uuid.uuid4()), "timestamp": time_str, "text": msg, "type": "STATIC"})

            # Dynamic Material Instance Segmentation & Store Material Counting (Warehouse / Inventory pipelines)
            current_mat_instances = []
            seg_counts = {}
            is_material_mode = getattr(cam, "pipeline_mode", "STANDARD_DETECTION") in (
                "MATERIAL_SEGMENTATION", "STORE_INVENTORY", "WAREHOUSE_DISPATCH"
            )
            try:
                if is_material_mode:
                    if dec is None:
                        nparr = np.frombuffer(frame_bytes, np.uint8)
                        dec = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    if dec is not None:
                        seg_res = MaterialSegmentationService.segment_materials(
                            dec, person_boxes=person_boxes_in_overlay
                        )
                        current_mat_instances = seg_res.instances
                        seg_counts = seg_res.counts_by_class
                        if current_mat_instances:
                            if getattr(cam, "pipeline_mode", "STANDARD_DETECTION") == "MATERIAL_SEGMENTATION":
                                annotated_mat = MaterialSegmentationService.annotate_frame_with_masks(dec, current_mat_instances)
                                success, enc_buf = cv2.imencode(".jpg", annotated_mat, [cv2.IMWRITE_JPEG_QUALITY, 85])
                                if success:
                                    annotated_bytes = enc_buf.tobytes()

                            for inst in current_mat_instances:
                                overlay_boxes.append({
                                    "box": inst.bbox,
                                    "type": "MATERIAL_INSTANCE",
                                    "label": f"{inst.class_name} ({int(inst.confidence * 100)}%)",
                                    "confidence": round(float(inst.confidence), 4),
                                    "color": "cyan",
                                    "entity": inst.class_name,
                                    "polygon": inst.polygon,
                                })

                            detection_data.update({
                                "segmentedMaterials": [
                                    {
                                        "classId": i.class_id,
                                        "className": i.class_name,
                                        "confidence": i.confidence,
                                        "bbox": i.bbox,
                                        "polygon": i.polygon,
                                        "areaPixels": i.area_pixels,
                                    }
                                    for i in current_mat_instances
                                ],
                                "materialCounts": seg_counts,
                                "totalMaterialCount": seg_res.total_instances,
                                "segmentationLatencyMs": seg_res.latency_ms,
                            })

                            # Activity log for detected material inventory
                            mat_log_parts = [f"{c}x {k.split(' (')[0].split(' / ')[0]}" for k, c in seg_counts.items()]
                            mat_log_msg = f"{cam_name} Ã¢â‚¬â€ Store Inventory: {', '.join(mat_log_parts)} Ã¢â‚¬â€ {time_str}"
                            if not cam_logs or cam_logs[-1]["text"] != mat_log_msg:
                                cam_logs.append({"id": str(uuid.uuid4()), "timestamp": time_str, "text": mat_log_msg, "type": "ITEM"})
            except Exception as _seg_err:
                logger.warning("Material segmentation error on %s: %s", cam.camera_id, _seg_err)

            # Virtual Tripwire, Multi-Camera Trajectory & Person-Material Attribution
            active_carriers = []
            try:
                tripwires_res = await session.execute(
                    select(VirtualTripwireConfig).where(
                        VirtualTripwireConfig.camera_id == cam.camera_id,
                        VirtualTripwireConfig.active == True,
                    )
                )
                active_tripwires = tripwires_res.scalars().all()
                if overlay_boxes:
                    # Update intra-camera tracks for stable ID persistence and occlusion resilience
                    overlay_boxes = intra_camera_tracker.update_tracks(
                        camera_id=cam.camera_id,
                        detections=overlay_boxes,
                        timestamp=now.timestamp(),
                    )
                    cam_tracks = self._track_history.setdefault(cam.camera_id, {})
                    for b_idx, ob in enumerate(overlay_boxes):
                        if ob["type"] in ("PERSON_MATCHED", "PERSON_UNMATCHED", "VEHICLE"):
                            track_id = ob.get("track_id", f"tr_{b_idx}")
                            bx, by, bw, bh = ob["box"]
                            norm_cx = (bx + bw / 2.0) / max(1.0, float(frame_w))
                            norm_cy = (by + bh / 2.0) / max(1.0, float(frame_h))
                            curr_pt = (norm_cx, norm_cy)

                            prev_pt = cam_tracks.get(track_id)
                            cam_tracks[track_id] = curr_pt

                            # Calculate movement trajectory direction: Inbound (ENTRY) vs Outbound (EXIT)
                            person_dir = "TRAVERSAL"
                            if prev_pt:
                                dy = curr_pt[1] - prev_pt[1]
                                if dy < -0.012:
                                    person_dir = "ENTRY"
                                elif dy > 0.012:
                                    person_dir = "EXIT"

                            # If entity is a Person, associate proximate materials and track carrier attribution
                            carried_mats: Dict[str, int] = {}
                            is_person = "PERSON" in ob["type"]
                            is_known = False
                            person_name = "Unknown Person"
                            emp_id = None

                            if is_person:
                                is_known = (face_res.decision == "MATCHED" and bool(face_res.matched_employee_id))
                                person_name = face_res.employee_name if is_known else "Unknown Person"
                                emp_id = face_res.matched_employee_id if is_known else None

                                pcx = bx + bw / 2.0
                                pcy = by + bh / 2.0
                                max_dist = max(130.0, bw * 1.0)

                                for minst in current_mat_instances:
                                    mbx, mby, mbw, mbh = minst.bbox
                                    mcx = mbx + mbw / 2.0
                                    mcy = mby + mbh / 2.0
                                    dist = math.hypot(mcx - pcx, mcy - pcy)
                                    if dist <= max_dist:
                                        carried_mats[minst.class_name] = carried_mats.get(minst.class_name, 0) + 1

                            carried_mats_list = [
                                {"name": cname, "quantity": cnt, "carrier_relation": "carrying"}
                                for cname, cnt in carried_mats.items()
                            ]

                            # Tripwire crossing evaluation with anti-duplicate lock and automatic inventory flow
                            if prev_pt and active_tripwires:
                                for tw in active_tripwires:
                                    if len(tw.line_coords) >= 2:
                                        l_start = (float(tw.line_coords[0][0]), float(tw.line_coords[0][1]))
                                        l_end = (float(tw.line_coords[1][0]), float(tw.line_coords[1][1]))
                                        has_crossed, tw_direction = TripwireEngine.check_trajectory_crossing(
                                            p_prev=prev_pt,
                                            p_curr=curr_pt,
                                            line_start=l_start,
                                            line_end=l_end,
                                        )
                                        if has_crossed and (tw.direction_mode in ("BOTH", tw_direction)):
                                            person_dir = tw_direction
                                            # Anti-duplicate gate lock: prevents loitering multi-fires
                                            if TripwireEngine.should_allow_crossing(tw.tripwire_id, track_id, tw_direction):
                                                emp_match = None
                                                if face_res.decision == "MATCHED":
                                                    emp_match = {
                                                        "decision": "MATCHED",
                                                        "employee_id": face_res.matched_employee_id,
                                                        "employee_name": face_res.employee_name,
                                                    }
                                                await TripwireEngine.record_crossing(
                                                    session=session,
                                                    tripwire_id=tw.tripwire_id,
                                                    camera_id=cam.camera_id,
                                                    track_id=track_id,
                                                    direction=tw_direction,
                                                    entity_type="PERSON" if is_person else "VEHICLE",
                                                    matched_employee=emp_match,
                                                    carried_materials=carried_mats_list if is_person else None,
                                                    zone_id=getattr(tw, "zone_id", None),
                                                )

                            if is_person:
                                mat_parts = [f"{cnt}x {cname.split(' (')[0].split(' / ')[0]}" for cname, cnt in carried_mats.items()]
                                mat_desc = ", ".join(mat_parts) if mat_parts else ""

                                if carried_mats:
                                    summary_carrier = f"{person_name} [{person_dir}] ({mat_desc})"
                                    ob["label"] = summary_carrier
                                    carrier_rec = {
                                        "personName": person_name,
                                        "isKnown": is_known,
                                        "employeeId": emp_id,
                                        "direction": person_dir,
                                        "materials": carried_mats,
                                        "summary": summary_carrier,
                                        "box": ob["box"],
                                    }
                                    active_carriers.append(carrier_rec)
                                    carrier_log = f"{cam_name} Ã¢â‚¬â€ Carrier: {summary_carrier} Ã¢â‚¬â€ {time_str}"
                                    if not cam_logs or cam_logs[-1]["text"] != carrier_log:
                                        cam_logs.append({"id": str(uuid.uuid4()), "timestamp": time_str, "text": carrier_log, "type": "PERSON"})
                                else:
                                    ob["label"] = f"{person_name} [{person_dir}]"
            except Exception as _tw_err:
                logger.warning("Tripwire evaluation error on %s: %s", cam.camera_id, _tw_err)

            detection_data["activeCarriers"] = active_carriers

            # In-progress compliance tag
            active_tx = self._active_transactions.get(cam.camera_id)
            if active_tx is None and (vis_res.vision_count > 0 or len(vis_res.detections) > 0 or face_res.matched_employee_id):
                active_tx = {
                    "eventId": f"TX-{cam.camera_id[:4]}",
                    "status": "CONSENSUS_PENDING",
                    "displayText": f"TX-{cam.camera_id[:4]} | Consensus Pending",
                }

            # Universal Multi-Class Taxonomy & Standard FRAME ANALYSIS REPORT
            categorized_entities = [
                UniversalTaxonomyService.classify_detection(ob, person_boxes=person_boxes_in_overlay)
                for ob in overlay_boxes
            ]
            frame_report = FrameAnalysisReportGenerator.generate_report(
                categorized_entities=categorized_entities,
                operational_confidence=round(vis_res.vision_confidence if vis_res.vision_confidence else 0.95, 2),
            )

            detection_data.update({
                "frameTs": now.isoformat(),
                "frameWidth": frame_w,
                "frameHeight": frame_h,
                "pipelineMode": getattr(cam, "pipeline_mode", "STANDARD_DETECTION"),
                "boxes": overlay_boxes,
                "entityCount": len(overlay_boxes),
                "frameAnalysisReport": frame_report,
                "categorizedEntities": [
                    {
                        "category": e.category,
                        "canonicalLabel": e.canonical_label,
                        "rawLabel": e.raw_label,
                        "confidence": round(e.confidence, 4),
                        "bbox": e.bbox,
                        "status": e.operational_status,
                        "isSpoofed": e.is_spoofed,
                        "spoofFormat": e.spoof_format,
                        "registryReference": e.registry_reference,
                    }
                    for e in categorized_entities
                ],
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
        self._last_raw_frames[cam.camera_id] = frame_bytes
        self._last_annotated_frames[cam.camera_id] = annotated_bytes
        
        # PUSH to single source of truth stream manager
        try:
            from src.engine.stream_manager import camera_stream_manager
            sess = camera_stream_manager._streams.get(cam.camera_id)
            if sess:
                with sess.lock:
                    sess.last_annotated_frame_bytes = annotated_bytes
        except Exception as push_err:
            import logging
            logging.getLogger("secops").error(f"Failed to push annotated frame: {push_err}")
            pass

        # Persist snapshots asynchronously in background thread (zero event-loop blocking)
        def _persist_to_disk(c_id: str, raw_b: bytes, ann_b: bytes):
            try:
                os.makedirs("snapshots", exist_ok=True)
                with open(os.path.join("snapshots", f"preview_{c_id}.jpg"), "wb") as f:
                    f.write(ann_b)
                with open(os.path.join("snapshots", f"raw_{c_id}.jpg"), "wb") as f:
                    f.write(raw_b)
            except Exception as _disk_err:
                logger.debug("Disk snapshot error on %s: %s", c_id, _disk_err)

        asyncio.create_task(asyncio.to_thread(_persist_to_disk, cam.camera_id, frame_bytes, annotated_bytes))

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

    def get_latest_frame_bytes(self, camera_id: str, raw: bool = True) -> Optional[bytes]:
        """Returns the latest captured frame bytes from memory cache (0ms latency, zero disk I/O)."""
        if raw:
            return self._last_raw_frames.get(camera_id) or self._last_annotated_frames.get(camera_id)
        return self._last_annotated_frames.get(camera_id) or self._last_raw_frames.get(camera_id)

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
            roi_polygon=cam.roi_polygon,
            ignored_classes=cam.ignored_classes,
                camera_id=cam.camera_id
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

        # 7. Write ExitEvent Row (Identity confidence floor: >= 0.65 and decision == MATCHED)
        is_verified_employee = (
            face_result.decision == "MATCHED"
            and face_result.matched_employee_id is not None
            and float(face_result.similarity or 0.0) >= 0.65
        )
        resolved_emp_id = face_result.matched_employee_id if is_verified_employee else None
        resolved_emp_conf = face_result.similarity if is_verified_employee else None

        event = ExitEvent(
            event_id=event_id,
            ts=now,
            lane_id=lane_id,
            employee_id=resolved_emp_id,
            employee_match_confidence=resolved_emp_conf,
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

        # 8b. Real Store Material Counting & ExitEventLineItem Attribution
        carrier_name = (
            face_result.employee_name
            if (face_result.decision == "MATCHED" and face_result.matched_employee_id and float(face_result.similarity or 0.0) >= 0.65)
            else "UNKNOWN_PERSON"
        )
        event_line_items = []
        try:
            nparr = np.frombuffer(frame_bytes, np.uint8)
            dec_mat = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if dec_mat is not None:
                mat_seg_res = MaterialSegmentationService.segment_materials(dec_mat)
                if mat_seg_res.instances:
                    existing_prods = {p.name.lower(): p for p in products}
                    existing_by_sku = {p.sku_code.upper(): p for p in products}

                    sku_map = {
                        "Cement Bag (50kg)": ("MAT-CEM-50KG", "Building Materials", 1, 9.50, 95.00),
                        "Bundled Iron Rods / Rebar": ("MAT-ROD-REBAR", "Building Materials", 1, 24.00, 240.00),
                        "Brick Stack / Paver Pallet": ("MAT-BRK-RED", "Building Materials", 1, 0.85, 425.00),
                        "Heavy Corrugated Master Carton": ("MAT-BOX-HEAVY", "Packaging", 1, 4.20, 42.00),
                        "Industrial Wooden Pallet": ("MAT-PLT-WOOD", "Logistics", 1, 18.50, 185.00),
                        "Ceramic Tiles / Tile Box": ("MAT-TIL-CERAMIC", "Building Materials", 1, 15.00, 150.00),
                        "Corrugated Aluminum Sheets & Tin Panels": ("MAT-ALU-TIN", "Building Materials", 1, 28.00, 280.00),
                    }

                    for mat_name, count in mat_seg_res.counts_by_class.items():
                        target_prod = existing_prods.get(mat_name.lower())
                        if not target_prod:
                            sku_info = sku_map.get(mat_name)
                            if sku_info:
                                sku_code, category, pack_size, u_price, c_price = sku_info
                                target_prod = existing_by_sku.get(sku_code)
                                if not target_prod:
                                    target_prod = Product(
                                        product_id=str(uuid.uuid4()),
                                        sku_code=sku_code,
                                        name=mat_name,
                                        category=category,
                                        pack_size=pack_size,
                                        unit_price=u_price,
                                        case_price=c_price,
                                        created_at=now,
                                    )
                                    session.add(target_prod)
                                    await session.flush()
                                    existing_by_sku[sku_code] = target_prod
                                    existing_prods[mat_name.lower()] = target_prod

                        if target_prod:
                            line_item = ExitEventLineItem(
                                line_item_id=str(uuid.uuid4()),
                                event_id=event_id,
                                product_id=target_prod.product_id,
                                cases_qty=count,
                                units_qty=count * (target_prod.pack_size or 1),
                            )
                            session.add(line_item)
                            event_line_items.append({
                                "lineItemId": line_item.line_item_id,
                                "productId": target_prod.product_id,
                                "skuCode": target_prod.sku_code,
                                "name": target_prod.name,
                                "casesQty": line_item.cases_qty,
                                "unitsQty": line_item.units_qty,
                            })

                    dir_tag = "EXIT" if "EXIT" in trigger_reason.upper() else "ENTRY"
                    carrier_name = face_result.employee_name if (face_result.decision == "MATCHED" and face_result.matched_employee_id and float(face_result.similarity or 0.0) >= 0.65) else "UNKNOWN_PERSON"
                    mat_desc = ", ".join([f"{c}x {n}" for n, c in mat_seg_res.counts_by_class.items()])
                    event.notes = f"[{dir_tag}] Carrier: {carrier_name}. Handled: {mat_desc}. Trigger: {trigger_reason}."
        except Exception as _mat_err:
            logger.warning("Material line items generation error: %s", _mat_err)

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
            carrier_str = carrier_name
            alert = Alert(
                alert_id=f"ALT-2026-{uuid.uuid4().hex[:6].upper()}",
                camera_id=cam.camera_id,
                event_id=event_id,
                alert_type=alert_type,
                severity=verdict_result.severity if verdict_result.severity in ("LOW", "MEDIUM", "HIGH") else "MEDIUM",
                delta_units=verdict_result.delta_units,
                status="OPEN",
                resolution_note=f"Discrepancy [{alert_type}]: {verdict_result.delta_units} units variance. Carrier: {carrier_str}.",
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
            "lineItems": event_line_items,
        }
        await ws_hub.broadcast_event("new_event", event_payload)
        if alert_payload:
            await ws_hub.broadcast_event("new_alert", alert_payload)

        # Update active transaction compliance tag for camera HUD & overlay
        tx_label = (
            f"PASS ({int(event.vision_confidence * 100 if event.vision_confidence else 98)}%)"
            if event.verdict == "PASS"
            else f"MISMATCH Ã¢â‚¬â€ {event.severity} (ÃŽâ€ {event.delta_units} units)"
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
            "text": f"{cam.label} Ã¢â‚¬â€ TX {event.event_id}: {tx_label} Ã¢â‚¬â€ {now.strftime('%H:%M:%S')}",
            "type": "TRANSACTION",
        })

        logger.info("Created real ExitEvent %s on %s (Units: %d, Verdict: %s)", event_id, lane_id, event.units_detected, event.verdict)
        return event


# Global worker singleton
camera_worker = CameraIngestionWorker(poll_interval_sec=3.0)

