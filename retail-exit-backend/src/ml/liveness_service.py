"""Anti-Spoofing & Liveness Detection Service

Distinguishes between live human faces and static 2D representations
(wall portraits, printed photos, digital screens, posters) using:
1. 3D Facial Depth Relief & Mesh Curvature (InsightFace 1k3d68 Z-variance)
2. Eye-Blink & EAR (Eye Aspect Ratio) Dynamic Tracking (landmark_2d_106 / 3d_68)
3. Facial Micro-Movement & Temporal Drift (Multi-frame optical jitter analysis)
4. Chrominance & Skin Diffusion (YCbCr / HSV diffuse reflection vs CMYK print)
5. Specular Gradient & Texture Spectrum (Local Binary Patterns & Laplacian variance)
"""

import time
import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from collections import deque
from src.ml.model_config import get_vision_config


@dataclass
class LivenessResult:
    is_live: bool
    liveness_score: float              # 0.0 (Definite Spoof) to 1.0 (Definite Live)
    spoof_type: Optional[str]          # 'STATIC_PHOTO' | 'WALL_PORTRAIT' | 'SCREEN_SPOOF' | 'PRINT_ATTACK' | None
    depth_score: float                 # 3D facial relief score
    z_std: float                       # 3D landmark Z-depth standard deviation (mm)
    z_span: float                      # 3D landmark Z-depth range (mm)
    texture_score: float               # Natural skin gradient vs flat/halftone texture
    chroma_score: float                # Subsurface skin chrominance consistency
    motion_score: float                # Temporal micro-displacement across frames
    blink_detected: bool               # Whether an active blink cycle was detected
    ear: float                         # Current Eye Aspect Ratio
    confidence: float                  # Model detection confidence
    reason: str                        # Forensic diagnostic rationale
    static_classification: Optional[str] = None
    static_confidence: float = 0.0
    static_friendly_label: Optional[str] = None


class TemporalFaceTrack:
    """Tracks a single detected face over time for temporal micro-movement and blink detection."""

    MAX_HISTORY = 15

    def __init__(self, track_id: int, initial_bbox: List[int]):
        self.track_id = track_id
        self.bbox = initial_bbox
        self.centroids: deque = deque(maxlen=self.MAX_HISTORY)
        self.landmarks_history: deque = deque(maxlen=self.MAX_HISTORY)
        self.ear_history: deque = deque(maxlen=self.MAX_HISTORY)
        self.timestamps: deque = deque(maxlen=self.MAX_HISTORY)
        self.blink_count: int = 0
        self.frames_tracked: int = 0
        self._in_blink: bool = False

    def update(self, bbox: List[int], landmarks: Optional[np.ndarray], ear: float, ts: float):
        self.bbox = bbox
        self.frames_tracked += 1
        x1, y1, x2, y2 = bbox
        cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        self.centroids.append((cx, cy))
        self.timestamps.append(ts)
        self.ear_history.append(ear)

        if landmarks is not None:
            self.landmarks_history.append(np.array(landmarks, dtype=np.float32))

        # Blink state machine: EAR drops below 0.20, then rises above 0.26
        if ear < 0.20 and not self._in_blink:
            self._in_blink = True
        elif ear > 0.26 and self._in_blink:
            self._in_blink = False
            self.blink_count += 1

    def compute_motion_score(self) -> Tuple[float, float]:
        """Computes average inter-frame landmark displacement (pixels) and motion score."""
        if len(self.landmarks_history) < 2:
            return 0.5, 0.0

        displacements = []
        for i in range(1, len(self.landmarks_history)):
            lm_prev = self.landmarks_history[i - 1]
            lm_curr = self.landmarks_history[i]
            # Mean Euclidean landmark drift between consecutive observations
            diff = np.linalg.norm(lm_curr[:, :2] - lm_prev[:, :2], axis=1).mean()
            displacements.append(diff)

        avg_disp = float(np.mean(displacements)) if displacements else 0.0

        # Static objects (paintings, posters, wall pictures) drift < 0.6px
        # Live humans naturally drift >= 1.2px due to physiological micro-movements
        if avg_disp < 0.6:
            motion_score = 0.1
        elif avg_disp < 1.2:
            motion_score = 0.5
        else:
            motion_score = min(1.0, 0.6 + (avg_disp / 5.0))

        # Bonus for detected blink
        if self.blink_count > 0:
            motion_score = min(1.0, motion_score + 0.3)

        return float(motion_score), float(avg_disp)


class LivenessDetectionService:
    """Production Multi-Factor Anti-Spoofing & Liveness Engine."""

    # Thresholds
    LIVENESS_PASS_THRESHOLD = 0.50
    MIN_REAL_Z_STD = 15.0       # Living 3D human faces have z_std >= 18mm (nose to cheeks/ears)
    BLINK_EAR_THRESHOLD = 0.20

    # Camera track stores: {camera_id: {track_id: TemporalFaceTrack}}
    _trackers: Dict[str, Dict[int, TemporalFaceTrack]] = {}
    _next_track_id: int = 1

    @staticmethod
    def _sigmoid(x: float) -> float:
        return float(1.0 / (1.0 + np.exp(-x)))

    @classmethod
    def calculate_ear(cls, eye_landmarks: np.ndarray) -> float:
        """Calculates Eye Aspect Ratio (EAR) from 6 2D/3D eye keypoints.

        Points order: [outer, top1, top2, inner, bottom2, bottom1]
        EAR = (||p2 - p6|| + ||p3 - p5||) / (2 * ||p1 - p4||)
        """
        if eye_landmarks is None or len(eye_landmarks) < 6:
            return 0.30

        p = eye_landmarks[:, :2]
        A = float(np.linalg.norm(p[1] - p[5]))
        B = float(np.linalg.norm(p[2] - p[4]))
        C = float(np.linalg.norm(p[0] - p[3]))
        return float((A + B) / (2.0 * max(1e-6, C)))

    @classmethod
    def _evaluate_depth(cls, face: Any) -> Tuple[float, float, float]:
        """Evaluates 3D facial relief and mesh curvature using 68 3D landmarks."""
        if not hasattr(face, "landmark_3d_68") or face.landmark_3d_68 is None:
            return 0.35, 0.0, 0.0

        z = face.landmark_3d_68[:, 2]
        z_std = float(z.std())
        z_span = float(z.max() - z.min())

        # Flat surfaces (posters, wall pictures, smartphone screen photos) have z_std < 12mm
        # Living human faces in surveillance views have z_std >= 20mm
        if z_std < 12.0:
            depth_score = max(0.02, float(z_std / 25.0))
        elif z_std < cls.MIN_REAL_Z_STD:
            depth_score = 0.25 + 0.25 * ((z_std - 12.0) / (cls.MIN_REAL_Z_STD - 12.0))
        else:
            # High 3D relief
            depth_score = min(1.0, 0.70 + 0.30 * min(1.0, (z_std - cls.MIN_REAL_Z_STD) / 20.0))

        return float(depth_score), float(z_std), float(z_span)

    @classmethod
    def _evaluate_texture(cls, img: np.ndarray, bbox: List[int]) -> float:
        """Evaluates skin texture gradient vs halftone dots, Moiré, or flat paper."""
        h_img, w_img = img.shape[:2]
        x1, y1, x2, y2 = bbox
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w_img, x2), min(h_img, y2)

        crop = img[y1:y2, x1:x2]
        if crop.size == 0 or crop.shape[0] < 12 or crop.shape[1] < 12:
            return 0.20

        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        # Extremely low lap_var (< 20) indicates blurry photo / blank wall
        # Extremely high lap_var (> 2500) indicates digital screen Moiré / halftone print
        # Natural human skin faces typically range 60 - 800
        if lap_var < 25:
            return 0.15
        elif lap_var > 2200:
            return 0.30
        elif 60 <= lap_var <= 900:
            return 0.90
        else:
            return 0.65

    @classmethod
    def _evaluate_chroma(cls, img: np.ndarray, bbox: List[int]) -> float:
        """Evaluates human skin chrominance consistency in YCbCr space."""
        h_img, w_img = img.shape[:2]
        x1, y1, x2, y2 = bbox
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w_img, x2), min(h_img, y2)

        crop = img[y1:y2, x1:x2]
        if crop.size == 0 or crop.shape[0] < 10 or crop.shape[1] < 10:
            return 0.10

        ycbcr = cv2.cvtColor(crop, cv2.COLOR_BGR2YCrCb)
        cr = ycbcr[:, :, 1]
        cb = ycbcr[:, :, 2]

        # Biological human skin range across all tones: Cr in [133, 173], Cb in [77, 127]
        skin_mask = (cr >= 133) & (cr <= 173) & (cb >= 77) & (cb <= 127)
        skin_ratio = float(np.mean(skin_mask))

        # Real skin typically covers >= 40% of the face bounding box (excluding eyes/hair)
        if skin_ratio < 0.15:
            return 0.10
        elif skin_ratio > 0.40:
            return min(1.0, 0.6 + (skin_ratio * 0.4))
        else:
            return float(skin_ratio / 0.40 * 0.6)

    @classmethod
    def evaluate_face(
        cls,
        img: np.ndarray,
        face: Any,
        camera_id: Optional[str] = None,
        track_id: Optional[int] = None,
    ) -> LivenessResult:
        """Evaluates multi-factor anti-spoofing and liveness metrics for a single face."""
        x1, y1, x2, y2 = [int(v) for v in face.bbox]
        bbox = [x1, y1, x2, y2]
        fw = max(1.0, x2 - x1)
        fh = max(1.0, y2 - y1)
        det_score = float(getattr(face, "det_score", 0.0))

        # 1. 3D Facial Depth Relief
        depth_score, z_std, z_span = cls._evaluate_depth(face)

        # 2. Scale & Geometry in Surveillance Perspective
        # Real persons standing in exit lanes have face width >= 50px
        # Distant miniature picture frames on walls are typically 18 - 40px
        scale_score = float(np.clip((fw - 25.0) / (70.0 - 25.0), 0.0, 1.0))

        # 3. Texture & Frequency Spectrum
        texture_score = cls._evaluate_texture(img, bbox)

        # 4. Chrominance / Skin Diffusion
        chroma_score = cls._evaluate_chroma(img, bbox)

        # 5. Eye Aspect Ratio (EAR)
        current_ear = 0.30
        blink_detected = False
        if hasattr(face, "landmark_3d_68") and face.landmark_3d_68 is not None:
            lm = face.landmark_3d_68
            ear_l = cls.calculate_ear(lm[36:42])
            ear_r = cls.calculate_ear(lm[42:48])
            current_ear = (ear_l + ear_r) / 2.0

        # 6. Multi-Frame Temporal Tracking (if camera_id is provided)
        motion_score = 0.50
        cam_id = camera_id or "default"
        if cam_id not in cls._trackers:
            cls._trackers[cam_id] = {}

        matched_track = None
        now_ts = time.time()
        cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0

        # Match existing track by spatial proximity
        for tid, trk in cls._trackers[cam_id].items():
            tcx, tcy = trk.centroids[-1] if trk.centroids else (0, 0)
            if np.hypot(cx - tcx, cy - tcy) < 50:
                matched_track = trk
                break

        if matched_track is None:
            cls._next_track_id += 1
            new_track = TemporalFaceTrack(cls._next_track_id, bbox)
            cls._trackers[cam_id][cls._next_track_id] = new_track
            matched_track = new_track

        lm_2d = face.landmark_3d_68[:, :2] if hasattr(face, "landmark_3d_68") and face.landmark_3d_68 is not None else None
        matched_track.update(bbox, lm_2d, current_ear, now_ts)

        if matched_track.frames_tracked >= 3:
            motion_score, avg_disp = matched_track.compute_motion_score()
            blink_detected = matched_track.blink_count > 0

        # Clean old tracks (inactive > 10s)
        stale_tids = [tid for tid, trk in cls._trackers[cam_id].items() if (now_ts - trk.timestamps[-1]) > 10.0]
        for tid in stale_tids:
            del cls._trackers[cam_id][tid]

        # Multi-Factor Weighted Consensus Score
        # Passive components: Depth (35%), Scale (20%), Texture (15%), Chroma (15%), Temporal Motion (15%)
        raw_liveness = (
            0.35 * depth_score
            + 0.20 * scale_score
            + 0.15 * texture_score
            + 0.15 * chroma_score
            + 0.15 * motion_score
        )

        # Hard gating rules:
        # Rule A: Flat 2D depth variance (< min_real_z_std, e.g. 15mm) indicates printed/screen spoof.
        # Living human faces maintain natural 3D curvature and relief even when stationary.
        # Stillness alone (sitting still) must NEVER flip a genuine 3D face to STATIC_PHOTO.
        cfg = get_vision_config()
        min_z = cfg.min_real_z_std
        pass_thresh = cfg.liveness_pass_threshold

        if z_std < min_z:
            raw_liveness = min(raw_liveness, 0.42)
            spoof_type = "WALL_PORTRAIT" if fw < 45 else "STATIC_PHOTO"
            reason = f"Flat 2D surface detected (Z-relief {z_std:.1f}mm < {min_z:.1f}mm)"
        elif raw_liveness < pass_thresh:
            spoof_type = "STATIC_PHOTO"
            reason = f"Insufficient liveness consensus score ({raw_liveness:.2f} < {pass_thresh:.2f})"
        else:
            spoof_type = None
            reason = "Live human confirmed via 3D depth relief and dynamic physiological characteristics"

        is_live = bool(raw_liveness >= pass_thresh and spoof_type is None)

        static_class = None
        static_conf = 0.0
        static_label = None
        if not is_live:
            from src.ml.static_image_service import StaticImageClassifier
            static_res = StaticImageClassifier.classify_image_region(
                full_image=img,
                bbox=bbox,
                liveness_score=round(raw_liveness, 3),
                has_face_geometry=True,
            )
            static_class = static_res.classification
            static_conf = static_res.confidence
            static_label = static_res.friendly_label

        return LivenessResult(
            is_live=is_live,
            liveness_score=round(raw_liveness, 3),
            spoof_type=spoof_type,
            depth_score=round(depth_score, 3),
            z_std=round(z_std, 1),
            z_span=round(z_span, 1),
            texture_score=round(texture_score, 3),
            chroma_score=round(chroma_score, 3),
            motion_score=round(motion_score, 3),
            blink_detected=blink_detected,
            ear=round(current_ear, 3),
            confidence=round(det_score, 3),
            reason=reason,
            static_classification=static_class,
            static_confidence=static_conf,
            static_friendly_label=static_label,
        )

