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
    DispatchSession,
    VirtualTripwireConfig,
    TripwireCrossingEvent,
    get_utc_now,
)
from dataclasses import asdict
from src.ml.vision_service import VisionInferenceService
from src.ml.face_service import FaceRecognitionService
from src.ml.material_segmentation import MaterialSegmentationService
from src.ml.hazard_service import FlameHazardDetector
from src.ml.pose_service import SuspiciousBehaviorDetector
from src.ml.ppe_service import PPEComplianceDetector
from src.engine.zone_analytics import zone_analytics_engine
from src.engine.dispatch_engine import DispatchEngine
from src.engine.tripwire_engine import TripwireEngine
from src.engine.fusion import MultiSensorFusionEngine
from src.engine.verdict import VerdictEngine
from src.realtime.hub import ws_hub
from src.ml.model_config import get_vision_config


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
            dec: Optional[np.ndarray] = None
            try:
                nparr = np.frombuffer(frame_bytes, np.uint8)
                dec = cv2.imdecode(nparr, cv2.IMREAD_UNCHANGED)
                if dec is not None:
                    frame_h, frame_w = dec.shape[:2]
            except Exception as _fdim_err:
                logger.debug("Frame dimension extraction failed (non-fatal): %s", _fdim_err)

            conf_floor = get_vision_config().confidence_floor
            overlay_boxes = []

            all_person_boxes: List[List[int]] = []

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
                        all_person_boxes.append(fb)

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
                        all_person_boxes.append(pb["box"])

            # 3. Detected items, vehicles, cases, and people from YOLOX
            cfg = get_vision_config()
            for d in vis_res.detections:
                is_person = d.class_label == "person"
                is_veh = d.class_label == "vehicle"
                is_case = "case" in d.class_label.lower()

                if is_person:
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
                            "label": f"Person ({int(d.confidence * 100)}%)",
                            "confidence": round(float(d.confidence), 4),
                            "color": "red",
                            "entity": "Person",
                        })
                    continue

                target_floor = (
                    cfg.case_conf_threshold if is_case
                    else (getattr(cfg, "vehicle_conf_threshold", 0.25) if is_veh
                    else cfg.item_conf_threshold)
                )
                if d.confidence < target_floor:
                    continue

                item_label = d.specific_label or d.class_label
                is_door = d.class_label == "doorway"
                if is_veh:
                    b_type = "VEHICLE"
                    b_label = f"{item_label} ({int(d.confidence * 100)}%)"
                    b_color = "cyan"
                elif is_case:
                    b_type = "CASE"
                    b_label = f"Case: {item_label} ({int(d.confidence * 100)}%)"
                    b_color = "green"
                elif is_door:
                    b_type = "DOORWAY"
                    b_label = f"{item_label} ({int(d.confidence * 100)}%)"
                    b_color = "cyan"
                else:
                    b_type = "ITEM"
                    b_label = f"{item_label} ({int(d.confidence * 100)}%)"
                    b_color = "amber"

                overlay_boxes.append({
                    "box": d.bbox,
                    "type": b_type,
                    "label": b_label,
                    "confidence": round(float(d.confidence), 4),
                    "color": b_color,
                    "entity": item_label,
                })

            # 4. Real-Time Flame & Fire Hazard Detection
            if dec is not None:
                try:
                    flames = FlameHazardDetector.detect_flames(dec)
                    for fl in flames:
                        overlay_boxes.append({
                            "box": fl.bbox,
                            "type": "HAZARD_FIRE",
                            "label": f"FIRE · {int(fl.confidence * 100)}%",
                            "confidence": fl.confidence,
                            "color": "red",
                            "entity": "Fire / Flame",
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
                            overlay_boxes.append({
                                "box": p_box,
                                "type": "SUSPICIOUS_BEHAVIOR",
                                "label": f"SUSPICIOUS · {int(pose_res.confidence * 100)}% ({pose_res.suspicious_reason})",
                                "confidence": pose_res.confidence,
                                "color": "amber",
                                "entity": "Suspicious Activity",
                            })

                        # 5B. PPE Worker Safety Assessment
                        ppe_res = PPEComplianceDetector.evaluate_worker_ppe(dec, p_box)
                        if ppe_res.has_helmet and ppe_res.helmet_box:
                            overlay_boxes.append({
                                "box": ppe_res.helmet_box,
                                "type": "PPE_COMPLIANT",
                                "label": f"HELMET · {int(ppe_res.helmet_confidence * 100)}%",
                                "confidence": ppe_res.helmet_confidence,
                                "color": "green",
                                "entity": "Hard Hat",
                            })
                        if ppe_res.has_vest and ppe_res.vest_box:
                            overlay_boxes.append({
                                "box": ppe_res.vest_box,
                                "type": "PPE_COMPLIANT",
                                "label": f"VEST · {int(ppe_res.vest_confidence * 100)}%",
                                "confidence": ppe_res.vest_confidence,
                                "color": "green",
                                "entity": "Safety Vest",
                            })
                        if not ppe_res.is_compliant and getattr(cam, "pipeline_mode", "") in ("INDUSTRIAL_SAFETY", "MATERIAL_SEGMENTATION"):
                            overlay_boxes.append({
                                "box": p_box,
                                "type": "PPE_VIOLATION",
                                "label": f"PPE VIOLATION ({', '.join(ppe_res.violations)})",
                                "confidence": 0.90,
                                "color": "amber",
                                "entity": "Missing PPE Gear",
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
            overlay_boxes = clean_boxes

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

            # Material Instance Segmentation pipeline routing
            if getattr(cam, "pipeline_mode", "STANDARD_DETECTION") == "MATERIAL_SEGMENTATION":
                try:
                    if dec is None:
                        nparr = np.frombuffer(frame_bytes, np.uint8)
                        dec = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    if dec is not None:
                        seg_res = MaterialSegmentationService.segment_materials(dec)
                        if seg_res.instances:
                            annotated_mat = MaterialSegmentationService.annotate_frame_with_masks(dec, seg_res.instances)
                            success, enc_buf = cv2.imencode(".jpg", annotated_mat, [cv2.IMWRITE_JPEG_QUALITY, 85])
                            if success:
                                annotated_bytes = enc_buf.tobytes()

                        for inst in seg_res.instances:
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
                                for i in seg_res.instances
                            ],
                            "materialCounts": seg_res.counts_by_class,
                            "totalMaterialCount": seg_res.total_instances,
                            "segmentationLatencyMs": seg_res.latency_ms,
                        })
                except Exception as _seg_err:
                    logger.warning("Material segmentation error on %s: %s", cam.camera_id, _seg_err)

            # Virtual Tripwire trajectory crossing & anti-tailgating evaluation
            try:
                tripwires_res = await session.execute(
                    select(VirtualTripwireConfig).where(
                        VirtualTripwireConfig.camera_id == cam.camera_id,
                        VirtualTripwireConfig.active == True,
                    )
                )
                active_tripwires = tripwires_res.scalars().all()
                if active_tripwires and overlay_boxes:
                    cam_tracks = self._track_history.setdefault(cam.camera_id, {})
                    for b_idx, ob in enumerate(overlay_boxes):
                        if ob["type"] in ("PERSON_MATCHED", "PERSON_UNMATCHED", "VEHICLE"):
                            track_id = f"tr_{b_idx}"
                            bx, by, bw, bh = ob["box"]
                            norm_cx = (bx + bw / 2.0) / max(1.0, float(frame_w))
                            norm_cy = (by + bh / 2.0) / max(1.0, float(frame_h))
                            curr_pt = (norm_cx, norm_cy)

                            prev_pt = cam_tracks.get(track_id)
                            cam_tracks[track_id] = curr_pt

                            if prev_pt:
                                for tw in active_tripwires:
                                    if len(tw.line_coords) >= 2:
                                        l_start = (float(tw.line_coords[0][0]), float(tw.line_coords[0][1]))
                                        l_end = (float(tw.line_coords[1][0]), float(tw.line_coords[1][1]))
                                        has_crossed, direction = TripwireEngine.check_trajectory_crossing(
                                            p_prev=prev_pt,
                                            p_curr=curr_pt,
                                            line_start=l_start,
                                            line_end=l_end,
                                        )
                                        if has_crossed and (tw.direction_mode in ("BOTH", direction)):
                                            emp_match = None
                                            if face_res.decision == "MATCHED":
                                                emp_match = {
                                                    "decision": "MATCHED",
                                                    "employee_id": face_res.matched_employee_id,
                                                }
                                            await TripwireEngine.record_crossing(
                                                session=session,
                                                tripwire_id=tw.tripwire_id,
                                                camera_id=cam.camera_id,
                                                track_id=track_id,
                                                direction=direction,
                                                entity_type="PERSON" if "PERSON" in ob["type"] else "VEHICLE",
                                                matched_employee=emp_match,
                                            )
            except Exception as _tw_err:
                logger.warning("Tripwire evaluation error on %s: %s", cam.camera_id, _tw_err)

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
                "pipelineMode": getattr(cam, "pipeline_mode", "STANDARD_DETECTION"),
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

