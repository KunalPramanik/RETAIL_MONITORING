"""Face Recognition & Biometric Authentication Service

Performs 1:N biometric identification using InsightFace / ArcFace 512-dimensional metric embeddings.
Features:
1. InsightFace ArcFace Deep-Learning Feature Extractor (buffalo_s model zoo)
2. SCRFD Deep-Learning Face Detector with 5 Facial Keypoints
3. Real 512-d L2-Normalized Metric Embeddings
4. Multi-Frame Temporal Voting & Cosine Similarity Matching
5. Dynamic Confidence Decision Routing ('MATCHED', 'LOW_CONFIDENCE', 'NO_MATCH')
"""

import os
import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union, Tuple
from insightface.app import FaceAnalysis
from src.ml.level3_liveness.liveness_service import LivenessDetectionService, LivenessResult
from src.ml.model_config import get_vision_config


@dataclass
class FaceMatchResult:
    matched_employee_id: Optional[str]
    employee_name: Optional[str]
    similarity: float
    decision: str                # 'MATCHED' | 'NO_MATCH' | 'LOW_CONFIDENCE'
    model_version: str
    unauthorized_alert_needed: bool
    frames_evaluated: int = 1
    liveness_score: float = 1.0
    liveness_decision: str = "LIVE"   # 'LIVE' | 'STATIC_PHOTO' | 'SPOOF' | 'NO_FACE'
    static_detections: List[Dict[str, Any]] = field(default_factory=list)
    live_person_boxes: List[Dict[str, Any]] = field(default_factory=list)


class FaceRecognitionService:
    # InsightFace ArcFace 512-dimensional deep-learning embedding model
    MODEL_VERSION = "insightface-arcface-buffalo_s-512d"
    EMBEDDING_DIM = 512
    MATCH_THRESHOLD = 0.65
    LOW_CONFIDENCE_THRESHOLD = 0.45
    THRESHOLD_MATCHED = MATCH_THRESHOLD
    THRESHOLD_LOW_CONF = LOW_CONFIDENCE_THRESHOLD

    _app: Optional[FaceAnalysis] = None

    @classmethod
    def get_app(cls) -> FaceAnalysis:
        if cls._app is None:
            app = FaceAnalysis(
                name="buffalo_s",
                allowed_modules=["detection", "recognition", "genderage", "landmark_3d_68"],
                providers=["CPUExecutionProvider"],
            )
            app.prepare(ctx_id=0, det_thresh=0.06, det_size=(640, 640))
            cls._app = app
        return cls._app

    @staticmethod
    def _normalize(vec: np.ndarray) -> np.ndarray:
        """Applies L2 unit vector normalization."""
        norm = np.linalg.norm(vec)
        if norm > 1e-6:
            return vec / norm
        return vec

    @classmethod
    def cosine_similarity(cls, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Computes cosine similarity between two 512-d feature vectors."""
        v1 = cls._normalize(np.asarray(vec1, dtype=np.float32))
        v2 = cls._normalize(np.asarray(vec2, dtype=np.float32))
        return float(np.dot(v1, v2))

    @classmethod
    def extract_face_embedding(cls, frame_bytes: bytes) -> Optional[List[float]]:
        """Extracts a real 512-d ArcFace embedding from a single face image."""
        nparr = np.frombuffer(frame_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return None

        app = cls.get_app()
        faces = app.get(img)
        if not faces:
            return None

        # Return the embedding of the most prominent face
        faces.sort(key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]), reverse=True)
        normed = cls._normalize(faces[0].embedding.astype(np.float32))
        return normed.tolist()

    @classmethod
    def match_carrier(
        cls,
        probe_embedding: Union[List[float], List[List[float]]],
        enrolled_employees: List[Dict[str, Any]],
        match_threshold: Optional[float] = None,
        is_ir_mode: bool = False,
    ) -> FaceMatchResult:
        """Runs 1:N cosine similarity search with multi-frame temporal voting across active roster."""
        threshold = match_threshold or cls.MATCH_THRESHOLD

        if not probe_embedding or not enrolled_employees:
            return FaceMatchResult(
                matched_employee_id=None,
                employee_name=None,
                similarity=0.0,
                decision="LOW_CONFIDENCE_IR" if is_ir_mode else "NO_MATCH",
                model_version=cls.MODEL_VERSION,
                unauthorized_alert_needed=False if is_ir_mode else True,
                frames_evaluated=0,
            )

        # Handle both single vector and multi-frame sequence
        frames: List[np.ndarray] = []
        if isinstance(probe_embedding[0], (int, float)):
            frames.append(cls._normalize(np.array(probe_embedding, dtype=np.float32)))
        else:
            for f in probe_embedding:
                frames.append(cls._normalize(np.array(f, dtype=np.float32)))

        best_score = -1.0
        best_employee = None

        # Compare against stored employee 512-d embeddings
        for emp in enrolled_employees:
            stored_emb = emp.get("face_embedding")
            if not stored_emb:
                continue

            stored_vecs = []
            if isinstance(stored_emb[0], (int, float)):
                stored_vecs.append(cls._normalize(np.array(stored_emb, dtype=np.float32)))
            else:
                for sv in stored_emb:
                    stored_vecs.append(cls._normalize(np.array(sv, dtype=np.float32)))

            # Multi-frame temporal evaluation
            frame_scores = []
            for frame_vec in frames:
                max_frame_sim = max(float(np.dot(frame_vec, s_vec)) for s_vec in stored_vecs)
                frame_scores.append(max_frame_sim)

            if frame_scores:
                frame_scores.sort(reverse=True)
                if frame_scores[0] >= threshold:
                    emp_similarity = frame_scores[0]
                elif len(frame_scores) > 1:
                    emp_similarity = (0.75 * frame_scores[0]) + (0.25 * frame_scores[len(frame_scores) // 2])
                else:
                    emp_similarity = frame_scores[0]
            else:
                emp_similarity = 0.0

            if emp_similarity > best_score:
                best_score = emp_similarity
                best_employee = emp

        best_score = max(0.0, min(1.0, best_score))

        # IR Night Vision degradation handling
        if is_ir_mode:
            if best_score >= threshold and best_employee:
                return FaceMatchResult(
                    matched_employee_id=best_employee.get("employee_id"),
                    employee_name=best_employee.get("name"),
                    similarity=round(best_score, 4),
                    decision="MATCHED",
                    model_version=cls.MODEL_VERSION,
                    unauthorized_alert_needed=False,
                    frames_evaluated=len(frames),
                )
            else:
                return FaceMatchResult(
                    matched_employee_id=best_employee.get("employee_id") if best_employee else None,
                    employee_name=best_employee.get("name") if best_employee else "Unidentified (IR Mode)",
                    similarity=round(best_score, 4),
                    decision="LOW_CONFIDENCE_IR",
                    model_version=cls.MODEL_VERSION,
                    unauthorized_alert_needed=False,
                    frames_evaluated=len(frames),
                )

        if best_score >= threshold and best_employee:
            return FaceMatchResult(
                matched_employee_id=best_employee.get("employee_id"),
                employee_name=best_employee.get("name"),
                similarity=round(best_score, 4),
                decision="MATCHED",
                model_version=cls.MODEL_VERSION,
                unauthorized_alert_needed=False,
                frames_evaluated=len(frames),
            )
        elif best_score >= cls.LOW_CONFIDENCE_THRESHOLD and best_employee:
            return FaceMatchResult(
                matched_employee_id=best_employee.get("employee_id"),
                employee_name=best_employee.get("name"),
                similarity=round(best_score, 4),
                decision="LOW_CONFIDENCE",
                model_version=cls.MODEL_VERSION,
                unauthorized_alert_needed=False,
                frames_evaluated=len(frames),
            )
        else:
            return FaceMatchResult(
                matched_employee_id=None,
                employee_name=None,
                similarity=round(best_score, 4),
                decision="NO_MATCH",
                model_version=cls.MODEL_VERSION,
                unauthorized_alert_needed=True,
                frames_evaluated=len(frames),
            )

    @classmethod
    def detect_and_match_faces(
        cls,
        frame_bytes: bytes,
        enrolled_employees: List[Dict[str, Any]],
        match_threshold: Optional[float] = None,
        prior_detections_count: int = 0,
        cases_detected: int = 0,
        units_detected: int = 0,
        raw_frame_bytes: Optional[bytes] = None,
        camera_id: Optional[str] = None,
        filter_static: bool = True,
        container_boxes: Optional[List[List[int]]] = None,
    ) -> Tuple[FaceMatchResult, Optional[bytes], List[List[int]]]:
        """Detects faces using InsightFace SCRFD and verifies liveness before ArcFace 512-d extraction."""
        nparr = np.frombuffer(frame_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            return (
                FaceMatchResult(
                    matched_employee_id=None,
                    employee_name=None,
                    similarity=0.0,
                    decision="NO_MATCH",
                    model_version=cls.MODEL_VERSION,
                    unauthorized_alert_needed=False,
                    frames_evaluated=0,
                    liveness_score=0.0,
                    liveness_decision="NO_FACE",
                ),
                None,
                [],
            )

        detected_boxes: List[List[int]] = []
        probe_embeddings: List[List[float]] = []
        box_annotations: List[Tuple[List[int], str, Tuple[int, int, int]]] = []
        static_detections: List[Dict[str, Any]] = []
        live_person_boxes: List[Dict[str, Any]] = []
        best_liveness_score = 0.0
        any_static_detected = False

        try:
            # If pristine unannotated frame bytes are available, run SCRFD on clean pixels
            if raw_frame_bytes:
                raw_nparr = np.frombuffer(raw_frame_bytes, np.uint8)
                infer_img = cv2.imdecode(raw_nparr, cv2.IMREAD_COLOR)
                if infer_img is None:
                    infer_img = img
            else:
                infer_img = img

            app = cls.get_app()
            faces = app.get(infer_img)
            faces.sort(key=lambda f: getattr(f, "det_score", 0.0), reverse=True)

            orig_h, orig_w = img.shape[:2]
            kept_faces: List[Tuple[Any, str, Tuple[int, int, int], LivenessResult]] = []
            for face in faces:
                x1, y1, x2, y2 = face.bbox.astype(int).tolist()
                det_score = getattr(face, "det_score", 0.0)
                w_face = x2 - x1
                h_face = y2 - y1

                # Minimum size filter: ignore sub-pixel artifact noise (<18px)
                if w_face < 18 or h_face < 18:
                    continue
                # Filter ceiling noise using dynamic configuration thresholds
                cfg = get_vision_config()
                if y1 < getattr(cfg, "face_min_y_offset", 25) and (y2 - y1) < getattr(cfg, "face_min_height", 30):
                    continue
                face_gate = get_vision_config().face_candidate_min_score
                if det_score < face_gate:
                    continue

                cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                too_close = False
                for (kf, _, _, _) in kept_faces:
                    kx1, ky1, kx2, ky2 = kf.bbox.astype(int).tolist()
                    kcx, kcy = (kx1 + kx2) / 2.0, (ky1 + ky2) / 2.0
                    w_inter = max(0, min(x2, kx2) - max(x1, kx1))
                    h_inter = max(0, min(y2, ky2) - max(y1, ky1))
                    area_inter = w_inter * h_inter
                    area1 = (x2 - x1) * (y2 - y1)
                    area2 = (kx2 - kx1) * (ky2 - ky1)
                    iou = area_inter / float(area1 + area2 - area_inter + 1e-6)
                    # Suppress vertical ghost duplicates on chest/collar while preserving distinct persons
                    if iou > 0.40 or (abs(cx - kcx) < 40 and abs(cy - kcy) < 70) or np.hypot(cx - kcx, cy - kcy) < 55:
                        too_close = True
                        break

                if not too_close:
                    face_xywh = [int(x1), int(y1), int(w_face), int(h_face)]

                    # Check if face is enclosed within a display container (wall picture, monitor screen, smartphone)
                    is_enclosed_in_container = False
                    if container_boxes:
                        from src.ml.level3_liveness.static_image_service import quarantine_enclosed_visual_content
                        enclosed = quarantine_enclosed_visual_content(
                            [face_xywh],
                            container_boxes,
                            containment_threshold=0.65,
                            candidate_format="xywh",
                            container_format="xywh",
                        )
                        if enclosed:
                            is_enclosed_in_container = True

                    if is_enclosed_in_container:
                        any_static_detected = True
                        static_item = {
                            "box": face_xywh,
                            "classification": "PERSON_PHOTO",
                            "confidence": float(det_score),
                            "friendly_label": "Static: Display Content / Portrait",
                            "liveness_score": 0.05,
                            "suppressed_alert": True,
                        }
                        static_detections.append(static_item)
                        lbl = "Static: Display Content / Portrait"
                        color = (140, 140, 140)
                        quarantined_liveness = LivenessResult(
                            is_live=False,
                            liveness_score=0.05,
                            spoof_type="STATIC_PHOTO",
                            confidence=float(det_score),
                            reason="Enclosed within detected display/picture container",
                            static_classification="PERSON_PHOTO",
                            static_confidence=float(det_score),
                            static_friendly_label=lbl,
                        )
                        kept_faces.append((face, lbl, color, quarantined_liveness))
                    else:
                        # Multi-Factor Anti-Spoofing & Liveness Evaluation
                        liveness = LivenessDetectionService.evaluate_face(
                            img=infer_img,
                            face=face,
                            camera_id=camera_id,
                        )
                        best_liveness_score = max(best_liveness_score, liveness.liveness_score)

                        if not liveness.is_live:
                            any_static_detected = True
                            static_item = {
                                "box": face_xywh,
                                "classification": liveness.static_classification or "UNCLASSIFIED_STATIC",
                                "confidence": liveness.static_confidence if liveness.static_confidence > 0 else det_score,
                                "friendly_label": liveness.static_friendly_label or f"Static: Image ({int(det_score * 100)}%)",
                                "liveness_score": liveness.liveness_score,
                                "suppressed_alert": True,
                            }
                            static_detections.append(static_item)
                            lbl = liveness.static_friendly_label or f"Static: Image ({int(det_score * 100)}%)"
                            color = (140, 140, 140)
                        else:
                            # Genuine living human detected
                            gender = getattr(face, "gender", 1)
                            gender_str = "MAN" if gender == 1 else "WOMAN"
                            conf_pct = int(det_score * 100)
                            lbl = f"LIVE {gender_str} {conf_pct}%"
                            color = (0, 255, 120) if gender == 1 else (255, 100, 255)
                            live_person_boxes.append({
                                "box": face_xywh,
                                "gender": gender_str,
                                "confidence": float(det_score),
                                "label": lbl,
                            })

                        kept_faces.append((face, lbl, color, liveness))

            for (face, def_lbl, col, liveness) in kept_faces:
                x1, y1, x2, y2 = face.bbox.astype(int).tolist()
                w = max(1, x2 - x1)
                h = max(1, y2 - y1)
                box = [int(x1), int(y1), int(w), int(h)]
                box_annotations.append((box, def_lbl, col))

                # Only living individuals are admitted into exit events and employee matching
                if liveness.is_live:
                    detected_boxes.append(box)
                    if hasattr(face, "embedding") and face.embedding is not None:
                        emb = cls._normalize(face.embedding.astype(np.float32))
                        probe_embeddings.append(emb.tolist())
        except Exception:
            pass

        # Match against enrolled roster
        is_ir_frame = False
        if img is not None:
            if len(img.shape) == 2:
                is_ir_frame = True
            elif len(img.shape) == 3 and img.shape[2] == 3:
                hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
                if float(np.mean(hsv[:, :, 1])) < 12.0:
                    is_ir_frame = True

        if probe_embeddings and enrolled_employees:
            match_res = cls.match_carrier(
                probe_embedding=probe_embeddings,
                enrolled_employees=enrolled_employees,
                match_threshold=match_threshold,
                is_ir_mode=is_ir_frame,
            )
            match_res.liveness_score = best_liveness_score
            match_res.liveness_decision = "LIVE"
        else:
            match_res = FaceMatchResult(
                matched_employee_id=None,
                employee_name=None,
                similarity=0.0,
                decision="NO_MATCH",
                model_version=cls.MODEL_VERSION,
                unauthorized_alert_needed=False,
                frames_evaluated=1 if probe_embeddings else 0,
                liveness_score=best_liveness_score if any_static_detected or probe_embeddings else 0.0,
                liveness_decision="LIVE" if probe_embeddings else ("STATIC_PHOTO" if any_static_detected else "NO_FACE"),
            )

        match_res.static_detections = static_detections
        match_res.live_person_boxes = live_person_boxes

        annotated_bytes = frame_bytes

        return match_res, annotated_bytes, detected_boxes
