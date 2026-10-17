"""Real-Time Dynamic Person Posture Classification & Smoothing Engine

Classifies person kinematic posture state dynamically from visual data:
- Primary: Skeletal keypoint geometry (torso inclination, knee/hip flexion)
- Fallback: Aspect ratio dynamics relative to track baseline + normalized centroid velocity
- Velocity: Normalized by person bounding box height per second
- Temporal smoothing: Circular vote buffer per track ID to eliminate frame-to-frame flicker

Posture states:
- 'Standing'
- 'Sitting'
- 'Walking'
- 'Crouching/Bending'
- 'Lying'
- 'Unknown'
"""

import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import numpy as np

from src.core.config import settings


class PostureState:
    STANDING = "Standing"
    SITTING = "Sitting"
    WALKING = "Walking"
    CROUCHING = "Crouching/Bending"
    LYING = "Lying"
    UNKNOWN = "Unknown"


@dataclass
class PostureResult:
    posture: str
    confidence: float
    raw_posture: str
    velocity_heights_per_sec: float
    aspect_ratio: float
    is_static_false_positive: bool = False


class PostureClassifier:
    """Classifies human posture dynamically from pose geometry and tracklet motion kinematics."""

    # History per camera: track_id -> deque of recent posture predictions (window size from config)
    _history: Dict[str, Dict[Any, deque]] = {}
    _track_baselines: Dict[str, Dict[Any, float]] = {}  # track_id -> max upright aspect ratio
    _track_positions: Dict[str, Dict[Any, List[Tuple[float, float, float]]]] = {}  # track_id -> [(x_mid, y_mid, timestamp)]
    _track_first_seen: Dict[str, Dict[Any, float]] = {}  # track_id -> initial timestamp
    _track_initial_pos: Dict[str, Dict[Any, Tuple[float, float]]] = {}  # track_id -> (initial_cx, initial_cy)

    @classmethod
    def get_smoothing_window(cls) -> int:
        return getattr(settings.detection, "posture_smoothing_window", 5)

    @classmethod
    def classify_posture(
        cls,
        person_bbox: List[int],
        camera_id: str = "default",
        track_id: Optional[Any] = None,
        keypoints: Optional[Dict[str, Tuple[int, int]]] = None,
        frame_h: int = 1080,
        frame_w: int = 1920,
        timestamp: Optional[float] = None,
    ) -> PostureResult:
        """Determines the true physical posture of a detected person box."""
        now = timestamp or time.time()
        bx, by, bw, bh = person_bbox
        w = max(1.0, float(bw))
        h = max(1.0, float(bh))
        aspect_ratio = round(h / w, 3)

        # 1. Update track baseline aspect ratio (track's personal maximum upright ratio)
        cam_baselines = cls._track_baselines.setdefault(camera_id, {})
        cam_positions = cls._track_positions.setdefault(camera_id, {})
        cam_history = cls._history.setdefault(camera_id, {})

        tid = track_id if track_id is not None else "ephemeral"
        if tid not in cam_baselines:
            cam_baselines[tid] = aspect_ratio
        else:
            # Baseline is maximum observed upright aspect ratio, decaying very slowly
            if aspect_ratio > cam_baselines[tid]:
                cam_baselines[tid] = aspect_ratio

        standing_baseline = max(2.2, cam_baselines[tid])

        # 2. Compute normalized velocity (heights of person moved per second)
        pos_list = cam_positions.setdefault(tid, [])
        cur_cx = bx + w * 0.5
        cur_cy = by + h * 0.5
        pos_list.append((cur_cx, cur_cy, now))

        # Keep last 10 position records (approx 1 second)
        if len(pos_list) > 10:
            pos_list.pop(0)

        norm_velocity = 0.0
        if len(pos_list) >= 2:
            prev_cx, prev_cy, prev_t = pos_list[0]
            dt = max(0.05, now - prev_t)
            pixel_dist = math.hypot(cur_cx - prev_cx, cur_cy - prev_cy)
            # Normalize displacement by current box height and elapsed time
            norm_velocity = round((pixel_dist / h) / dt, 3)

        # 3. Analyze posture from keypoints if available
        raw_posture = "Unknown"
        raw_conf = 0.75

        if keypoints and "neck" in keypoints and "mid_hip" in keypoints:
            neck_x, neck_y = keypoints["neck"]
            hip_x, hip_y = keypoints["mid_hip"]
            torso_dx = abs(neck_x - hip_x)
            torso_dy = max(1, hip_y - neck_y)
            torso_angle_deg = math.degrees(math.atan2(torso_dx, torso_dy))

            has_knees = "left_knee" in keypoints or "right_knee" in keypoints
            has_ankles = "left_ankle" in keypoints or "right_ankle" in keypoints

            # Lying check: horizontal torso
            if torso_angle_deg > 65.0 or (w > h * 1.35):
                raw_posture = "Lying"
                raw_conf = 0.90
            elif torso_angle_deg > 38.0 or aspect_ratio < 1.45:
                raw_posture = "Crouching/Bending"
                raw_conf = 0.88
            elif aspect_ratio < (standing_baseline * 0.70) or aspect_ratio < 1.85:
                raw_posture = "Sitting"
                raw_conf = 0.91
            elif norm_velocity > 0.18:
                raw_posture = "Walking"
                raw_conf = 0.89
            else:
                raw_posture = "Standing"
                raw_conf = 0.92
        else:
            # 4. Fallback kinematic evaluation from bounding box dynamics
            if w > h * 1.30:
                raw_posture = "Lying"
                raw_conf = 0.85
            elif aspect_ratio <= 1.35:
                raw_posture = "Crouching/Bending"
                raw_conf = 0.82
            elif aspect_ratio < (standing_baseline * 0.72) or aspect_ratio <= 1.85:
                # Compression of person box without horizontal lying orientation indicates seated position
                raw_posture = "Sitting"
                raw_conf = 0.88
            elif norm_velocity >= 0.18:
                raw_posture = "Walking"
                raw_conf = 0.87
            else:
                raw_posture = "Standing"
                raw_conf = 0.90

        # 5. Temporal Smoothing (majority voting across the sliding window)
        window_size = max(1, cls.get_smoothing_window())
        vote_buffer = cam_history.setdefault(tid, deque(maxlen=window_size))
        vote_buffer.append(raw_posture)

        # Count votes
        votes: Dict[str, int] = {}
        for p in vote_buffer:
            votes[p] = votes.get(p, 0) + 1

        smoothed_posture = max(votes.items(), key=lambda item: item[1])[0]
        consensus_ratio = votes[smoothed_posture] / float(len(vote_buffer))
        final_conf = round(min(0.98, max(0.60, raw_conf * (0.8 + 0.2 * consensus_ratio))), 2)

        # Static object suppression: track duration >= 30s with near-zero drift (< 8% person height)
        cam_first_seen = cls._track_first_seen.setdefault(camera_id, {})
        cam_init_pos = cls._track_initial_pos.setdefault(camera_id, {})
        if tid not in cam_first_seen:
            cam_first_seen[tid] = now
            cam_init_pos[tid] = (cur_cx, cur_cy)

        track_duration = now - cam_first_seen[tid]
        init_cx, init_cy = cam_init_pos[tid]
        net_drift = math.hypot(cur_cx - init_cx, cur_cy - init_cy)

        is_static_fp = False
        if track_duration >= 30.0 and net_drift < (h * 0.08):
            # A seated person is legitimate; standing/unknown motionless for >30s is a mannequin or wall poster
            if smoothed_posture != "Sitting":
                is_static_fp = True

        return PostureResult(
            posture=smoothed_posture,
            confidence=final_conf,
            raw_posture=raw_posture,
            velocity_heights_per_sec=norm_velocity,
            aspect_ratio=aspect_ratio,
            is_static_false_positive=is_static_fp,
        )

    @classmethod
    def cleanup_track(cls, camera_id: str, track_id: Any) -> None:
        """Removes tracklet posture buffers when track is terminated."""
        if camera_id in cls._history and track_id in cls._history[camera_id]:
            del cls._history[camera_id][track_id]
        if camera_id in cls._track_baselines and track_id in cls._track_baselines[camera_id]:
            del cls._track_baselines[camera_id][track_id]
        if camera_id in cls._track_positions and track_id in cls._track_positions[camera_id]:
            del cls._track_positions[camera_id][track_id]
        if camera_id in cls._track_first_seen and track_id in cls._track_first_seen[camera_id]:
            del cls._track_first_seen[camera_id][track_id]
        if camera_id in cls._track_initial_pos and track_id in cls._track_initial_pos[camera_id]:
            del cls._track_initial_pos[camera_id][track_id]
